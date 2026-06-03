"""Generate a README using an LLM (OpenAI, Anthropic, or Ollama)."""
from __future__ import annotations

from typing import Optional

from .utils import RepoInfo

# ── Prompt template ────────────────────────────────────────────────────────────
_SYSTEM_EN = """\
You are an expert technical writer who specialises in open-source software documentation.
Your task is to generate a professional, engaging README.md for a code repository.

Guidelines:
- Choose an appropriate emoji for the project title.
- Write a short, compelling description (2-3 sentences) that clearly explains
  what the project does and who it is for.
- Add shields.io badges for language, license (MIT), and PyPI / crates.io /
  npm version where relevant. Use placeholder badge URLs if the package is not
  yet published, e.g. `![Version](https://img.shields.io/badge/version-0.1.0-blue)`.
- List 4-6 concrete key features as bullet points.
- Provide clear Prerequisites / Requirements (runtime version, system deps).
- Write step-by-step Installation instructions.
- Include at least one real Usage example with a proper fenced code block.
- Add a Configuration section if there are env vars, config files, or CLI flags.
- Keep a short Contributing section pointing to issues / PRs.
- End with a License section (MIT).
- Use proper Markdown: headings, fenced code blocks with language hints, tables
  where appropriate. Do NOT use HTML tags.
- Output ONLY the Markdown content. No preamble, no explanation.\
"""

_SYSTEM_ZH = """\
你是一位专注于开源软件文档的资深技术写作专家。
你的任务是为一个代码仓库生成一份专业、吸引人的 README.md 文件。

写作规范：
- 为项目标题选择合适的 emoji。
- 写一段简洁有力的简介（2-3 句话），清楚说明项目的用途和目标用户。
- 添加 shields.io 徽章（编程语言、MIT 许可证、版本号等）。
  若包尚未发布，使用占位徽章，例如 `![版本](https://img.shields.io/badge/version-0.1.0-blue)`。
- 用项目符号列出 4-6 个核心功能。
- 说明前置要求 / 环境依赖（运行时版本、系统依赖等）。
- 提供分步安装说明。
- 至少给出一个真实的使用示例，并使用带语言标注的围栏代码块。
- 若存在环境变量、配置文件或 CLI 参数，添加配置说明章节。
- 保留简短的贡献指南（指向 Issues / PR）。
- 最后附上 License 章节（MIT）。
- 使用规范 Markdown：标题、代码块（附语言标注）、必要时使用表格。禁止使用 HTML 标签。
- 只输出 Markdown 内容本身，不要任何前言或解释。\
"""

_USER_TEMPLATE = """\
Generate a README.md for the following repository.

{repo_info}
"""


class ReadmeGenerator:
    """Unified README generator supporting multiple LLM backends."""

    DEFAULTS = {
        "openai": "gpt-4o",
        "anthropic": "claude-sonnet-4-20250514",
        "ollama": "llama3",
    }

    def __init__(
        self,
        provider: str = "openai",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        ollama_url: str = "http://localhost:11434",
    ) -> None:
        if provider not in self.DEFAULTS:
            raise ValueError(f"Unknown provider: {provider!r}. "
                             f"Choose from {list(self.DEFAULTS)}")
        self.provider = provider
        self.model = model or self.DEFAULTS[provider]
        self.api_key = api_key
        self.ollama_url = ollama_url

    # ── Public API ─────────────────────────────────────────────────────────────

    def generate(self, repo: RepoInfo, language: str = "en") -> str:
        """Return a README.md string for the given :class:`RepoInfo`."""
        system = _SYSTEM_ZH if language == "zh" else _SYSTEM_EN
        user = _USER_TEMPLATE.format(repo_info=repo.to_prompt_text())

        if self.provider == "openai":
            return self._openai(system, user)
        if self.provider == "anthropic":
            return self._anthropic(system, user)
        return self._ollama(system, user)

    # ── Backends ───────────────────────────────────────────────────────────────

    def _openai(self, system: str, user: str) -> str:
        try:
            from openai import OpenAI
        except ImportError as e:
            raise ImportError(
                "openai package not found. Run: pip install openai"
            ) from e

        client = OpenAI(api_key=self.api_key)
        resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.4,
            max_tokens=4096,
        )
        return (resp.choices[0].message.content or "").strip()

    def _anthropic(self, system: str, user: str) -> str:
        try:
            import anthropic
        except ImportError as e:
            raise ImportError(
                "anthropic package not found. Run: pip install anthropic"
            ) from e

        client = anthropic.Anthropic(api_key=self.api_key)
        msg = client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return msg.content[0].text.strip()

    def _ollama(self, system: str, user: str) -> str:
        """Call a local Ollama instance via its REST API."""
        try:
            import requests
        except ImportError as e:
            raise ImportError("requests package not found.") from e

        payload = {
            "model": self.model,
            "prompt": f"{system}\n\n{user}",
            "stream": False,
        }
        resp = requests.post(
            f"{self.ollama_url}/api/generate",
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
