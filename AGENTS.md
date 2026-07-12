# AGENTS.md — voicemeet-pro (opencode-Kontext)

## Projekt
Premium lokale Meeting-Notizen: Live-Transkription (Whisper small, MLX), Ollama-Summary, PDF/DOCX/MD-Export, SQLite-Session-Memory. macOS-first, Apple Silicon. Siehe `BLUEPRINT.md` für den vollständigen Phasen-Plan.

## Befehle
- Tests: `pytest tests/ -q`
- Lint: `ruff check src/`
- Format prüfen: `ruff format --check src/`
- Smoke-Test (nach Phase 6): `python -m voicemeet record --test 5`
- CLI: `python -m voicemeet --help`

## Konventionen
- Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`).
- Keine Secrets/Ollama-Modelle/Audio/SQLite-DBs committen (siehe `.gitignore`).
- Python 3.11+, Deps in `pyproject.toml`.
- Eine Phase aus `BLUEPRINT.md` pro logischem Committ-Bereich; nach jeder Phase verifizieren (pytest + ruff).

## Stack
Python · mlx-whisper · sounddevice · ollama · sqlite3 · reportlab · python-docx · typer/rich · rumps
