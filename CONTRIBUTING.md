# Contributing

Thanks for your interest in voicemeet-pro! This is a community-driven, MIT-licensed project.

## Quick Start

```bash
# Clone
git clone https://github.com/user/voicemeet-pro.git
cd voicemeet-pro

# Install with dev deps
pip install -e ".[dev]"

# For full functionality (audio, transcription, menubar)
pip install -e ".[all]"

# Run tests
pytest tests/ -q

# Lint
ruff check src/
ruff format --check src/
```

## Architecture

```
src/voicemeet/
├── audio/        — Microphone + system audio capture, VAD
├── transcribe/   — Whisper engine, VAD, speaker diarization
├── summarize/    — Ollama meeting summary
├── store/        — SQLite session storage
├── export/       — PDF, DOCX, Markdown export
├── detect/       — Auto meeting detection
├── cli.py        — Typer CLI
├── menubar.py    — rumps menubar daemon
└── hotkey.py     — Global hotkey (pynput)
```

## Conventions

- **Conventional Commits**: `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`
- **Python 3.11+**, deps in `pyproject.toml`
- **Lazy imports** for heavy deps (sounddevice, pywhispercpp, rumps, ollama)
- **No secrets, no API keys, no cloud calls** — everything runs locally
- **No telemetry/analytics** — privacy first

## Pull Request Checklist

- [ ] Tests pass: `pytest tests/ -q`
- [ ] Lint clean: `ruff check src/ && ruff format --check src/`
- [ ] Conventional commit message
- [ ] No secrets, API keys, or model files committed
- [ ] New deps documented in commit body with justification

## Adding Dependencies

Only add packages that are:
1. Established OSS (>1000 downloads/month)
2. No API keys or cloud calls required
3. Documented in the commit body with WHY they're needed

## Reporting Issues

Please include:
- macOS version and chip (M1/M2/M3/Intel)
- Python version
- `voicemeet --version` output
- Steps to reproduce
- Expected vs actual behavior
