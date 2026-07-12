# Changelog

All notable changes to voicemeet-pro are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-07-12

### Added
- **Live transcription** — Whisper `large-v3-turbo` via whisper.cpp, real-time streaming with VAD
- **Speaker diarization** — Spectral feature extraction + KMeans clustering (no API key, no model download)
- **AI meeting summary** — Ollama-powered, structured header (date, time, duration, participants, topics) + summary + action items
- **Export pipeline** — PDF (reportlab), DOCX (python-docx), Markdown — all with speaker-attributed transcripts
- **Session memory** — SQLite-backed, full-text search, reload any past meeting
- **CLI** — 8 commands: `record`, `list`, `show`, `export`, `search`, `transcribe`, `setup`, `menubar`
- **Menubar daemon** — rumps app with recording controls, auto-detection toggle, quick export
- **Global hotkey** — Cmd+Shift+M toggles recording from any application
- **Auto meeting detection** — psutil 3-tier process watch (Zoom/Teams/Meet/Discord/Notion) + audio VAD confirmation + macOS notification
- **Two recording modes** — `room` (microphone + diarization) and `online` (microphone + system audio via BlackHole)
- **One-command installer** — `./scripts/install.sh` sets up everything including LaunchAgent for background daemon
- **OpenSuperWhisper model reuse** — auto-detects existing `ggml .bin` models, no additional download
- **Health check** — `voicemeet setup` verifies all components

### Security
- No API keys, no cloud calls (except Ollama on localhost:11434)
- No telemetry or analytics
- No external model downloads (reuses local whisper.cpp models)
- All audio stays on-device
