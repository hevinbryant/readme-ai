"""Command-line interface for readme-ai."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax

from .analyzer import LocalAnalyzer
from .fetcher import GitHubFetcher
from .generator import ReadmeGenerator

console = Console()


# ── CLI root ───────────────────────────────────────────────────────────────────

@click.group()
@click.version_option(package_name="readme-ai")
def main() -> None:
    """readme-ai — Generate professional README files with AI.

    Supports GitHub URLs and local directory paths.
    """


# ── generate command ───────────────────────────────────────────────────────────

@main.command("generate")
@click.argument("source")
@click.option(
    "--provider", "-p",
    default="openai",
    type=click.Choice(["openai", "anthropic", "ollama"], case_sensitive=False),
    show_default=True,
    help="LLM provider.",
)
@click.option(
    "--model", "-m",
    default=None,
    help=(
        "Model name. Defaults: gpt-4o (openai), "
        "claude-sonnet-4-20250514 (anthropic), llama3 (ollama)."
    ),
)
@click.option(
    "--output", "-o",
    default="README.md",
    show_default=True,
    help="Output file path.",
)
@click.option(
    "--lang", "-l",
    default="en",
    type=click.Choice(["en", "zh"], case_sensitive=False),
    show_default=True,
    help="Language for the generated README.",
)
@click.option(
    "--token", "-t",
    default=None,
    envvar="GITHUB_TOKEN",
    help="GitHub personal-access token (raises rate limit from 60 → 5000 req/hr).",
)
@click.option(
    "--preview/--no-preview",
    default=True,
    help="Print a preview of the first 20 lines after generation.",
)
def generate(
    source: str,
    provider: str,
    model: str | None,
    output: str,
    lang: str,
    token: str | None,
    preview: bool,
) -> None:
    """Generate a README for SOURCE (GitHub URL or local path).

    \b
    Examples:
      readme-ai generate https://github.com/pallets/flask
      readme-ai generate ./my-project --provider anthropic
      readme-ai generate https://github.com/user/repo --lang zh -o README.zh.md
    """
    # ── Resolve API key ────────────────────────────────────────────────────────
    api_key = _resolve_api_key(provider)

    # ── Analyze / fetch ────────────────────────────────────────────────────────
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("🔍  Analyzing repository …", total=None)

        try:
            if _is_github_url(source):
                fetcher = GitHubFetcher(github_token=token)
                repo_info = fetcher.fetch(source)
            else:
                local = Path(source).expanduser().resolve()
                if not local.exists():
                    console.print(
                        f"[bold red]✗[/] Path not found: {local}", highlight=False
                    )
                    sys.exit(1)
                analyzer = LocalAnalyzer(local)
                repo_info = analyzer.analyze()
        except Exception as exc:
            console.print(f"[bold red]✗[/] {exc}")
            sys.exit(1)

        progress.update(task, description=f"🤖  Calling {provider} ({model or 'default'}) …")

        # ── Generate ───────────────────────────────────────────────────────────
        try:
            generator = ReadmeGenerator(
                provider=provider, model=model, api_key=api_key
            )
            readme = generator.generate(repo_info, language=lang)
        except Exception as exc:
            console.print(f"[bold red]✗[/] Generation failed: {exc}")
            sys.exit(1)

        progress.update(task, description="💾  Writing output …")

        # ── Write ──────────────────────────────────────────────────────────────
        out = Path(output)
        out.write_text(readme, encoding="utf-8")

    # ── Success output ─────────────────────────────────────────────────────────
    console.print()
    console.print(
        Panel(
            f"[bold green]✓ README generated![/]\n\n"
            f"  Repo      : [cyan]{repo_info.name}[/]\n"
            f"  Language  : [cyan]{repo_info.language}[/]\n"
            f"  Provider  : [cyan]{provider}[/]\n"
            f"  Output    : [bold cyan]{out.resolve()}[/]",
            title="readme-ai",
            expand=False,
        )
    )

    if preview:
        lines = readme.split("\n")[:20]
        console.print("\n[dim]── Preview (first 20 lines) " + "─" * 40 + "[/]")
        console.print(Syntax("\n".join(lines), "markdown", theme="monokai"))
        console.print("[dim]" + "─" * 60 + "[/]\n")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _is_github_url(source: str) -> bool:
    s = source.lower()
    return s.startswith("https://github.com") or s.startswith("github.com") or \
           s.startswith("git@github.com")


def _resolve_api_key(provider: str) -> str | None:
    if provider == "openai":
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            console.print(
                "[bold red]✗[/] OPENAI_API_KEY is not set.\n"
                "  Run: [yellow]export OPENAI_API_KEY=sk-...[/]"
            )
            sys.exit(1)
        return key
    if provider == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            console.print(
                "[bold red]✗[/] ANTHROPIC_API_KEY is not set.\n"
                "  Run: [yellow]export ANTHROPIC_API_KEY=sk-ant-...[/]"
            )
            sys.exit(1)
        return key
    # Ollama – no key needed
    return None
