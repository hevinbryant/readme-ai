"""Fetch repository information from the GitHub API."""
from __future__ import annotations

import base64
import re
import time
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

import requests

from .utils import EXTENSION_LANGUAGE, RepoInfo

# ── Constants ──────────────────────────────────────────────────────────────────
GITHUB_API = "https://api.github.com"

CONFIG_PRIORITY = [
    "package.json", "pyproject.toml", "setup.py", "setup.cfg",
    "Cargo.toml", "go.mod", "Gemfile", "composer.json", "pom.xml",
    "build.gradle", "CMakeLists.txt", "requirements.txt",
    "Makefile", "Dockerfile", "docker-compose.yml", ".env.example",
]

ENTRY_POINTS = [
    "main.py", "app.py", "server.py", "__main__.py", "cli.py",
    "src/main.py", "src/app.py",
    "main.go", "cmd/main.go",
    "main.rs", "src/main.rs", "src/lib.rs",
    "main.js", "index.js", "app.js", "src/index.js", "src/app.js",
    "main.ts", "index.ts", "app.ts", "src/index.ts", "src/app.ts",
]

MAX_CONFIG_FILES = 6
MAX_SOURCE_FILES = 8
MAX_FILE_CHARS = 3000
MAX_TOTAL_CHARS = 28_000


class GitHubFetcher:
    """Fetch a public (or private, if token supplied) GitHub repo."""

    def __init__(self, github_token: Optional[str] = None) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        if github_token:
            self.session.headers["Authorization"] = f"Bearer {github_token}"

    # ── Public API ─────────────────────────────────────────────────────────────

    def fetch(self, url: str) -> RepoInfo:
        owner, repo = _parse_github_url(url)
        meta = self._get_repo_meta(owner, repo)
        tree = self._get_file_tree(owner, repo, meta.get("default_branch", "HEAD"))
        file_map = {item["path"]: item for item in tree if item["type"] == "blob"}

        config_contents = self._fetch_config_files(owner, repo, file_map)
        source_samples = self._fetch_source_files(owner, repo, file_map,
                                                   already_fetched=set(config_contents))
        file_tree_str = _render_tree(list(file_map.keys()))

        language = meta.get("language") or _detect_language_from_files(file_map)

        return RepoInfo(
            name=repo,
            description=meta.get("description") or "",
            language=language,
            file_tree=file_tree_str,
            config_contents=config_contents,
            source_samples=source_samples,
            stars=meta.get("stargazers_count", 0),
            forks=meta.get("forks_count", 0),
            topics=meta.get("topics", []),
            url=f"https://github.com/{owner}/{repo}",
        )

    # ── GitHub API helpers ─────────────────────────────────────────────────────

    def _get(self, url: str, params: Optional[dict] = None) -> dict | list:
        resp = self.session.get(url, params=params, timeout=20)
        if resp.status_code == 403:
            reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait = max(0, reset - int(time.time())) + 2
            raise RuntimeError(
                f"GitHub API rate limit reached. "
                f"Retry after ~{wait}s, or pass --token to increase limits."
            )
        if resp.status_code == 404:
            raise RuntimeError("Repository not found. Is it private? Use --token.")
        resp.raise_for_status()
        return resp.json()

    def _get_repo_meta(self, owner: str, repo: str) -> dict:
        return self._get(f"{GITHUB_API}/repos/{owner}/{repo}")  # type: ignore[return-value]

    def _get_file_tree(self, owner: str, repo: str, branch: str) -> List[dict]:
        data = self._get(
            f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{branch}",
            params={"recursive": "1"},
        )
        return data.get("tree", [])  # type: ignore[union-attr]

    def _fetch_file(self, owner: str, repo: str, path: str) -> Optional[str]:
        try:
            data = self._get(f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}")
            if isinstance(data, dict) and data.get("encoding") == "base64":
                raw = base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
                return raw[:MAX_FILE_CHARS]
        except Exception:
            pass
        return None

    def _fetch_config_files(self, owner: str, repo: str,
                             file_map: Dict[str, dict]) -> Dict[str, str]:
        result: Dict[str, str] = {}
        for name in CONFIG_PRIORITY:
            if len(result) >= MAX_CONFIG_FILES:
                break
            if name in file_map:
                content = self._fetch_file(owner, repo, name)
                if content:
                    result[name] = content
        return result

    def _fetch_source_files(self, owner: str, repo: str,
                             file_map: Dict[str, dict],
                             already_fetched: set) -> Dict[str, str]:
        result: Dict[str, str] = {}
        total = 0
        source_exts = set(EXTENSION_LANGUAGE.keys())

        # Priority 1: entry points
        for path in ENTRY_POINTS:
            if len(result) >= MAX_SOURCE_FILES or total >= MAX_TOTAL_CHARS:
                break
            if path in file_map and path not in already_fetched:
                content = self._fetch_file(owner, repo, path)
                if content:
                    result[path] = content
                    total += len(content)

        # Priority 2: remaining source files
        for path in file_map:
            if len(result) >= MAX_SOURCE_FILES or total >= MAX_TOTAL_CHARS:
                break
            if path in result or path in already_fetched:
                continue
            if Path(path).suffix not in source_exts:
                continue
            # Prefer top-level or src/ files
            parts = Path(path).parts
            if len(parts) > 3:
                continue
            content = self._fetch_file(owner, repo, path)
            if content:
                result[path] = content
                total += len(content)

        return result


# ── Utilities ──────────────────────────────────────────────────────────────────

def _parse_github_url(url: str) -> tuple[str, str]:
    """Extract (owner, repo) from any GitHub URL format."""
    url = url.strip().rstrip("/")
    if url.startswith("git@"):
        # git@github.com:owner/repo.git
        match = re.match(r"git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$", url)
        if match:
            return match.group(1), match.group(2)
    # https://github.com/owner/repo  or  github.com/owner/repo
    parsed = urlparse(url if "://" in url else "https://" + url)
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        raise ValueError(f"Cannot parse GitHub URL: {url!r}")
    return parts[0], parts[1].removesuffix(".git")


def _render_tree(paths: List[str], max_lines: int = 100) -> str:
    """Turn a flat list of file paths into a tree-like string."""
    tree: dict = {}
    for path in sorted(paths):
        node = tree
        for part in Path(path).parts:
            node = node.setdefault(part, {})

    lines: List[str] = []

    def _walk(node: dict, prefix: str) -> None:
        items = sorted(node.items(), key=lambda kv: (not kv[1], kv[0].lower()))
        for i, (name, children) in enumerate(items):
            if len(lines) >= max_lines:
                return
            is_last = i == len(items) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{name}")
            if children:
                ext = "    " if is_last else "│   "
                _walk(children, prefix + ext)

    _walk(tree, "")
    return "\n".join(lines)


def _detect_language_from_files(file_map: Dict[str, dict]) -> str:
    counts: Dict[str, int] = {}
    for path in file_map:
        ext = Path(path).suffix
        lang = EXTENSION_LANGUAGE.get(ext)
        if lang:
            counts[lang] = counts.get(lang, 0) + 1
    return max(counts, key=counts.get) if counts else "Unknown"  # type: ignore[arg-type]
