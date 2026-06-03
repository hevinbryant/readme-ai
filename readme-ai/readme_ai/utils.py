"""Shared data structures and utilities."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


EXTENSION_LANGUAGE: Dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".jsx": "JavaScript (React)",
    ".tsx": "TypeScript (React)",
    ".rs": "Rust",
    ".go": "Go",
    ".rb": "Ruby",
    ".java": "Java",
    ".kt": "Kotlin",
    ".php": "PHP",
    ".c": "C",
    ".cpp": "C++",
    ".cs": "C#",
    ".swift": "Swift",
    ".dart": "Dart",
    ".zig": "Zig",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".scala": "Scala",
    ".sh": "Shell",
    ".lua": "Lua",
    ".r": "R",
    ".jl": "Julia",
    ".vue": "Vue.js",
    ".svelte": "Svelte",
}


@dataclass
class RepoInfo:
    """All extracted information about a repository."""

    name: str
    description: str = ""
    language: str = "Unknown"
    file_tree: str = ""
    config_contents: Dict[str, str] = field(default_factory=dict)
    source_samples: Dict[str, str] = field(default_factory=dict)
    stars: int = 0
    forks: int = 0
    topics: List[str] = field(default_factory=list)
    url: str = ""

    def to_prompt_text(self) -> str:
        """Serialize repo info into a detailed text block for the AI prompt."""
        lines: List[str] = []

        lines.append(f"## Repository: {self.name}")
        if self.url:
            lines.append(f"URL: {self.url}")
        if self.description:
            lines.append(f"Existing description: {self.description}")
        lines.append(f"Primary language: {self.language}")
        if self.stars:
            lines.append(f"GitHub stars: {self.stars:,}")
        if self.forks:
            lines.append(f"GitHub forks: {self.forks:,}")
        if self.topics:
            lines.append(f"Topics / tags: {', '.join(self.topics)}")

        if self.file_tree:
            lines.append("\n## File / Directory Structure")
            lines.append("```")
            lines.append(self.file_tree)
            lines.append("```")

        if self.config_contents:
            lines.append("\n## Key Configuration Files")
            for fname, content in self.config_contents.items():
                lines.append(f"\n### {fname}")
                ext = Path(fname).suffix.lstrip(".")
                lines.append(f"```{ext if ext else 'text'}")
                lines.append(content[:3000])
                lines.append("```")

        if self.source_samples:
            lines.append("\n## Source Code Samples")
            for fname, content in self.source_samples.items():
                ext = Path(fname).suffix.lstrip(".")
                lines.append(f"\n### {fname}")
                lines.append(f"```{ext if ext else 'text'}")
                lines.append(content[:2500])
                lines.append("```")

        return "\n".join(lines)
