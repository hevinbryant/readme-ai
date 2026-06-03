"""Analyze a local repository directory and extract relevant information."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from .utils import EXTENSION_LANGUAGE, RepoInfo

# ── tomllib / tomli ────────────────────────────────────────────────────────────
try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # pip install tomli
    except ImportError:
        tomllib = None  # type: ignore[assignment]

# ── Constants ──────────────────────────────────────────────────────────────────
IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    "dist", "build", ".next", ".nuxt", "coverage", ".pytest_cache",
    ".mypy_cache", "target", "vendor", ".tox", "htmlcov", ".eggs",
    ".idea", ".vscode", "out", "bin", "obj",
}

IGNORE_EXTENSIONS = {
    ".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe", ".bin",
    ".jpg", ".jpeg", ".png", ".gif", ".ico", ".webp", ".bmp",
    ".mp3", ".mp4", ".avi", ".mov", ".pdf", ".zip", ".tar",
    ".gz", ".woff", ".woff2", ".ttf", ".eot", ".map",
}

IGNORE_SUFFIXES = (".lock", ".min.js", ".min.css")

CONFIG_FILES = [
    "package.json", "pyproject.toml", "setup.py", "setup.cfg",
    "Cargo.toml", "go.mod", "Gemfile", "composer.json", "pom.xml",
    "build.gradle", "build.gradle.kts", "CMakeLists.txt",
    "requirements.txt", "Makefile", "Dockerfile",
    "docker-compose.yml", "docker-compose.yaml",
    ".env.example", "pubspec.yaml", "Package.swift",
]

# Likely entry-point files to read first (relative paths from repo root)
ENTRY_POINTS = [
    "main.py", "app.py", "server.py", "__main__.py", "cli.py",
    "src/main.py", "src/app.py",
    "main.go", "cmd/main.go",
    "main.rs", "src/main.rs", "src/lib.rs",
    "main.js", "index.js", "app.js", "server.js",
    "src/index.js", "src/app.js",
    "main.ts", "index.ts", "app.ts",
    "src/index.ts", "src/app.ts",
    "main.c", "main.cpp",
]

MAX_FILE_SIZE = 40 * 1024   # 40 KB – skip very large files
MAX_FILES_TO_READ = 12
MAX_TOTAL_CHARS = 28_000


class LocalAnalyzer:
    """Walk a local directory and produce a :class:`RepoInfo`."""

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()

    # ── Public API ─────────────────────────────────────────────────────────────

    def analyze(self) -> RepoInfo:
        config = self._read_config_files()
        sources = self._read_source_files(already_read=set(config.keys()))
        language = self._detect_language(config, sources)
        description = self._extract_description(config)

        return RepoInfo(
            name=self.path.name,
            description=description,
            language=language,
            file_tree=self._build_file_tree(),
            config_contents=config,
            source_samples=sources,
        )

    # ── File tree ──────────────────────────────────────────────────────────────

    def _build_file_tree(self, max_depth: int = 3) -> str:
        lines: List[str] = [self.path.name]
        self._walk_tree(self.path, prefix="", lines=lines,
                        max_depth=max_depth, depth=0)
        return "\n".join(lines[:120])

    def _walk_tree(self, path: Path, prefix: str,
                   lines: List[str], max_depth: int, depth: int) -> None:
        if depth >= max_depth:
            return
        try:
            entries = sorted(path.iterdir(),
                             key=lambda p: (p.is_file(), p.name.lower()))
        except PermissionError:
            return
        entries = [e for e in entries if not self._should_ignore(e)]
        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{entry.name}")
            if entry.is_dir():
                extension = "    " if is_last else "│   "
                self._walk_tree(entry, prefix + extension,
                                lines, max_depth, depth + 1)

    # ── File reading ───────────────────────────────────────────────────────────

    def _read_config_files(self) -> Dict[str, str]:
        result: Dict[str, str] = {}
        for name in CONFIG_FILES:
            fp = self.path / name
            if fp.is_file():
                content = self._safe_read(fp)
                if content is not None:
                    result[name] = content
        return result

    def _read_source_files(self, already_read: set) -> Dict[str, str]:
        result: Dict[str, str] = {}
        total = 0
        count = 0

        # Priority 1: common entry points
        for rel in ENTRY_POINTS:
            if count >= MAX_FILES_TO_READ or total >= MAX_TOTAL_CHARS:
                break
            fp = self.path / rel
            if fp.is_file() and rel not in already_read:
                content = self._safe_read(fp, limit=3000)
                if content:
                    result[rel] = content
                    total += len(content)
                    count += 1

        # Priority 2: scan source files
        source_exts = set(EXTENSION_LANGUAGE.keys())
        for fp in self._iter_sources(source_exts):
            if count >= MAX_FILES_TO_READ or total >= MAX_TOTAL_CHARS:
                break
            rel = str(fp.relative_to(self.path))
            if rel in result or rel in already_read:
                continue
            content = self._safe_read(fp, limit=2000)
            if content:
                result[rel] = content
                total += len(content)
                count += 1

        return result

    def _iter_sources(self, exts: set):
        for root, dirs, files in os.walk(self.path):
            rp = Path(root)
            dirs[:] = [d for d in dirs
                       if not self._should_ignore(rp / d)]
            for name in files:
                fp = rp / name
                if fp.suffix in exts and not self._should_ignore(fp):
                    yield fp

    def _safe_read(self, fp: Path, limit: Optional[int] = None) -> Optional[str]:
        try:
            if fp.stat().st_size > MAX_FILE_SIZE:
                return None
            text = fp.read_text(encoding="utf-8", errors="ignore")
            return text[:limit] if limit else text
        except Exception:
            return None

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _should_ignore(self, path: Path) -> bool:
        name = path.name
        if name in IGNORE_DIRS:
            return True
        # Hidden files/dirs except a few useful ones
        if name.startswith(".") and name not in {".github", ".env.example", ".gitignore"}:
            return True
        if path.is_file():
            if path.suffix in IGNORE_EXTENSIONS:
                return True
            if name.endswith(IGNORE_SUFFIXES):
                return True
        return False

    def _detect_language(self, config: Dict[str, str],
                         sources: Dict[str, str]) -> str:
        if "Cargo.toml" in config:
            return "Rust"
        if "go.mod" in config:
            return "Go"
        if "package.json" in config:
            pkg = _parse_json(config["package.json"])
            if pkg:
                all_deps = {**pkg.get("dependencies", {}),
                            **pkg.get("devDependencies", {})}
                if "typescript" in all_deps:
                    if "next" in all_deps:
                        return "TypeScript (Next.js)"
                    return "TypeScript"
                if "react" in all_deps:
                    return "JavaScript (React)"
                if "vue" in all_deps:
                    return "JavaScript (Vue)"
                if "svelte" in all_deps:
                    return "JavaScript (Svelte)"
            return "JavaScript"
        if any(k in config for k in ("pyproject.toml", "setup.py",
                                      "setup.cfg", "requirements.txt")):
            return "Python"
        if "Gemfile" in config:
            return "Ruby"
        if "composer.json" in config:
            return "PHP"
        if "pom.xml" in config or "build.gradle" in config:
            return "Java"
        if "CMakeLists.txt" in config:
            return "C++"
        if "pubspec.yaml" in config:
            return "Dart/Flutter"
        if "Package.swift" in config:
            return "Swift"

        # Fall back to extension counts
        counts: Dict[str, int] = {}
        for fname in sources:
            ext = Path(fname).suffix
            lang = EXTENSION_LANGUAGE.get(ext)
            if lang:
                counts[lang] = counts.get(lang, 0) + 1
        if counts:
            return max(counts, key=counts.get)  # type: ignore[arg-type]
        return "Unknown"

    def _extract_description(self, config: Dict[str, str]) -> str:
        if "package.json" in config:
            pkg = _parse_json(config["package.json"])
            if pkg and pkg.get("description"):
                return pkg["description"]

        if "pyproject.toml" in config and tomllib:
            try:
                data = tomllib.loads(config["pyproject.toml"])
                desc = (data.get("project", {}).get("description")
                        or data.get("tool", {}).get("poetry", {}).get("description"))
                if desc:
                    return desc
            except Exception:
                pass

        if "Cargo.toml" in config and tomllib:
            try:
                data = tomllib.loads(config["Cargo.toml"])
                desc = data.get("package", {}).get("description", "")
                if desc:
                    return desc
            except Exception:
                pass

        return ""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_json(text: str) -> Optional[dict]:
    try:
        return json.loads(text)
    except Exception:
        return None
