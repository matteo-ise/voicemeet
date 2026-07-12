# voicemeet-pro

> Premium local meeting notes — live transcription, AI summary, PDF/DOCX/MD export, session memory. Zero cost, fully local, MIT-licensed.

[![CI](https://github.com/user/voicemeet-pro/actions/workflows/ci.yml/badge.svg)](https://github.com/user/voicemeet-pro/actions)

## What it is

A macOS tool (Python, menubar + CLI) that records meetings, transcribes them live (Whisper via whisper.cpp, Apple-Silicon-optimized), separates speakers, generates a structured summary (Ollama), and exports to PDF / DOCX / Markdown. All sessions are stored in a local SQLite database — searchable and reloadable.

**Everything runs locally.** No cloud, no API keys, no telemetry. Your audio never leaves your machine.

### Two recording modes

| Mode | Use case | Audio source | Diarization |
|------|----------|-------------|-------------|
| `room` | In-person meetings, conference rooms | Microphone | Yes (spectral clustering) |
| `online` | Video calls (Zoom, Meet, Teams, Notion) | Microphone + System audio (BlackHole) | Optional |
| `auto` | Auto-detect based on running processes | Process-dependent | If room mode |

### Features

- **Live transcription** — Whisper `large-v3-turbo` via whisper.cpp, real-time streaming with VAD
- **Speaker diarization** — Spectral feature extraction + KMeans clustering, no API key needed
- **AI summary** — Structured header (date, time, duration, participants, topics) + summary + action items via Ollama
- **1-click export** — PDF (reportlab), DOCX (python-docx), Markdown
- **Session memory** — SQLite, full-text search, reload any past meeting
- **Auto meeting detection** — Watches for Zoom/Teams/Meet/Discord/Notion processes, confirms with audio VAD, sends macOS notification
- **Menubar daemon** — rumps menubar app with recording controls
- **Global hotkey** — Cmd+Shift+M toggles recording from any app

## Installation

### Prerequisites

- macOS Apple Silicon (M1+)
- Python 3.11+
- [Ollama](https://ollama.ai) installed and running

### Setup

```bash
# 1. Install voicemeet-pro
git clone https://github.com/user/voicemeet-pro.git
cd voicemeet-pro
pip install -e ".[all]"

# 2. Pull Ollama model for summaries
ollama pull llama3.2

# 3. (Optional) Install BlackHole for system audio capture
brew install blackhole-2ch
# Then set up a Multi-Output Device in Audio MIDI Setup
# See: https://github.com/ExistentialAudio/BlackHole

# 4. (Optional) Set model path if you have existing whisper models
export VOICEMEET_MODEL_PATH="/path/to/ggml-large-v3-turbo-q5_0.bin"
```

### Using existing OpenSuperWhisper models

If you already use OpenSuperWhisper, voicemeet-pro automatically detects your models in:
```
~/Library/Application Support/ru.starmel.OpenSuperWhisper/whisper-models/
```
No additional download needed.

## Usage

### CLI

```bash
# Record a meeting (Ctrl+C to stop)
voicemeet record --title "Q3 Planning" --mode room

# Record with system audio (online meeting)
voicemeet record --title "Client Call" --mode online

# Auto-stop after 30 seconds (smoke test)
voicemeet record --test 30

# Dry run (no microphone needed — tests full pipeline)
voicemeet record --dry-run --title "Test"

# List all sessions
voicemeet list

# Show session details + transcript
voicemeet show <session-id>

# Export to specific format
voicemeet export <session-id> --format pdf
voicemeet export <session-id> --format all

# Search across all transcripts
voicemeet search "quarterly budget"

# Transcribe an existing WAV file
voicemeet transcribe recording.wav --title "Imported Meeting"
```

### Menubar app

```bash
# Start menubar daemon
python -m voicemeet.menubar
```

The menubar app provides:
- **New Meeting** — Start recording
- **Start/Stop Recording** — Toggle recording
- **Recent Meetings** — Last 5 sessions
- **Export Last as PDF** — Quick export
- **Auto-Detect** — Toggle meeting auto-detection
- **Quit**

**Global hotkey:** Cmd+Shift+M toggles recording from any application.

## Configuration

| Setting | Env var | Default | Description |
|---------|---------|---------|-------------|
| Database path | `VOICEMEET_DB` | `~/.voicemeet/voicemeet.db` | SQLite database location |
| Model path | `VOICEMEET_MODEL_PATH` | Auto-detect | Path to ggml .bin whisper model |
| Export directory | — | `~/.voicemeet/exports/` | Export file output |
| Audio recordings | — | `~/.voicemeet/recordings/` | Raw audio files |

## Architecture

```
Audio Capture (mic + system) → VAD (segment detection)
    → Whisper streaming transcription → Segments in SQLite
    → Speaker diarization (spectral clustering)
    → Ollama summary (header + topics + action items)
    → Export pipeline (PDF / DOCX / Markdown)
    → Session finalized in DB
```

### Tech stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Transcription | whisper.cpp (pywhispercpp) | Reads ggml .bin models directly, Metal backend |
| Audio | sounddevice + numpy | Standard, reliable, BlackHole-compatible |
| Summary | Ollama (llama3.2) | Local, no API key, runs on Apple Silicon |
| Storage | sqlite3 (stdlib) | Zero dependency, robust |
| PDF | reportlab | Mature, high-quality output |
| DOCX | python-docx | Standard for Word documents |
| CLI | typer + rich | Beautiful terminal UI |
| Menubar | rumps | Simplest macOS menubar lib |
| Hotkey | pynput | Global keyboard shortcuts |
| Diarization | scipy + scikit-learn | No API key, no model download |

## Comparison

| Feature | voicemeet-pro | Granola | Meetily CE | OpenSuperWhisper |
|---------|:---:|:---:|:---:|:---:|
| Live transcription | Yes | Yes | Yes | No |
| Speaker diarization | Yes | Yes | No | No |
| AI summary | Yes (local) | Yes (cloud) | Yes (local) | No |
| PDF export | Yes | Pro | No | No |
| DOCX export | Yes | Pro | No | No |
| Session memory | Yes | Pro | No | No |
| Auto-detection | Yes | Pro | No | No |
| Price | Free | Free/Pro | Free | Free |
| Privacy | Fully local | Cloud | Local | Local |

## Roadmap

See [ROADMAP.md](./ROADMAP.md) for the full plan.

- **v1.1** — Named speakers, pyannote diarization
- **v1.2** — Calendar integration, pre-meeting briefs
- **v1.3** — Windows/Linux support
- **v1.4** — py2app bundle, notarized release
- **v2.0** — Chat with your meetings (RAG over session DB)

## Known limitations

- **BlackHole** required for system audio capture (online meetings). Install with `brew install blackhole-2ch`.
- **Diarization** labels speakers as "Speaker 1/2/3" — named identification is v1.1.
- **macOS only** — Windows/Linux port is v1.3.
- **rumps + py2app** may trigger quarantine. Fix with: `xattr -d com.apple.quarantine /path/to/app`

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md).

## License

MIT — see [LICENSE](./LICENSE).
