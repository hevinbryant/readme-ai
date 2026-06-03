# 🤖 readme-ai

![Python](https://img.shields.io/badge/python-3.9%2B-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)
![Version](https://img.shields.io/badge/version-0.1.0-orange)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)

**Automatically generate a professional `README.md` for any code repository using AI.**

Point `readme-ai` at a GitHub URL or a local folder, and it analyses your project structure, configuration files, and source code — then asks an LLM to write a complete, well-formatted README in seconds.

> ✨ This README was generated with `readme-ai` itself.

---

## Features

- 🔗 **GitHub & local support** — works with any public GitHub URL or local directory path
- 🧠 **Multi-provider** — supports OpenAI (GPT-4o), Anthropic (Claude), and Ollama (local LLMs)
- 🌍 **Multilingual** — generate in English (`--lang en`) or Chinese (`--lang zh`)
- 🔍 **Smart analysis** — auto-detects language, framework, entry points, and config files
- 🎨 **Beautiful CLI** — rich spinner, color output, and inline preview
- 📦 **pip-installable** — one command to install, one to run

---

## Requirements

- Python 3.9 or later
- An API key for your chosen provider:
  - **OpenAI** → `OPENAI_API_KEY`
  - **Anthropic** → `ANTHROPIC_API_KEY`
  - **Ollama** → no key needed (runs locally)

---

## Installation

```bash
# From PyPI (once published)
pip install readme-ai

# From source (recommended for now)
git clone https://github.com/yourusername/readme-ai.git
cd readme-ai
pip install -e .
```

Then set your API key:

```bash
# OpenAI (default)
export OPENAI_API_KEY="sk-..."

# Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."
```

---

## Usage

### Generate README for a GitHub repository

```bash
readme-ai generate https://github.com/pallets/flask
```

### Generate README for a local project

```bash
readme-ai generate ./my-project
```

### Use Anthropic Claude as the backend

```bash
readme-ai generate https://github.com/user/repo --provider anthropic
```

### Generate a Chinese README

```bash
readme-ai generate https://github.com/user/repo --lang zh -o README.zh.md
```

### Use a specific model

```bash
readme-ai generate ./my-project --provider openai --model gpt-4-turbo
```

### Full options

```
Usage: readme-ai generate [OPTIONS] SOURCE

  Generate a README for SOURCE (GitHub URL or local path).

Options:
  -p, --provider [openai|anthropic|ollama]
                                  LLM provider.  [default: openai]
  -m, --model TEXT                Model name override.
  -o, --output TEXT               Output file path.  [default: README.md]
  -l, --lang [en|zh]              README language.  [default: en]
  -t, --token TEXT                GitHub token (raises API rate limit).
  --preview / --no-preview        Print a preview after generation.
  --help                          Show this message and exit.
```

---

## How It Works

```
Source (GitHub URL / local path)
        │
        ▼
  ┌─────────────┐     ┌──────────────┐
  │  Analyzer   │  or │   Fetcher    │
  │ (local dir) │     │ (GitHub API) │
  └──────┬──────┘     └──────┬───────┘
         │                   │
         └─────────┬─────────┘
                   ▼
            RepoInfo object
        (file tree, configs,
         code samples, metadata)
                   │
                   ▼
           ┌───────────────┐
           │   Generator   │
           │ OpenAI/Claude │
           │    /Ollama    │
           └───────┬───────┘
                   │
                   ▼
              README.md ✅
```

1. **Analyze** — scans config files (`package.json`, `pyproject.toml`, `Cargo.toml`, etc.) and samples key source files to understand what the project does.
2. **Prompt** — builds a structured context document and sends it to the LLM with detailed writing guidelines.
3. **Generate** — the model writes a complete README with title, badges, features, installation steps, usage examples, and more.
4. **Save** — output is written to disk; a preview is shown in the terminal.

---

## Configuration

| Environment variable | Description                                   |
|----------------------|-----------------------------------------------|
| `OPENAI_API_KEY`     | OpenAI API key (required for `--provider openai`) |
| `ANTHROPIC_API_KEY`  | Anthropic API key (required for `--provider anthropic`) |
| `GITHUB_TOKEN`       | GitHub personal-access token (optional, increases rate limit) |

You can also store these in a `.env` file in your working directory — `readme-ai` loads it automatically via `python-dotenv`.

---

## Contributing

Contributions are welcome! Please open an issue first to discuss what you'd like to change.

```bash
# Fork the repo, then:
git clone https://github.com/yourusername/readme-ai.git
cd readme-ai
pip install -e ".[dev]"

# Run tests
pytest

# Lint & format
ruff check readme_ai/
black readme_ai/
```

Please make sure tests pass before submitting a pull request.

---

## License

[MIT](LICENSE) © readme-ai contributors
