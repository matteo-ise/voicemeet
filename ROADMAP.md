# Roadmap

## v1.0 — Current

- [x] Live transcription (Whisper via whisper.cpp)
- [x] Speaker diarization (spectral clustering)
- [x] Ollama meeting summary with header (date, time, participants, topics)
- [x] PDF / DOCX / Markdown export
- [x] SQLite session memory (searchable, reloadable)
- [x] CLI (record, list, show, export, search, transcribe)
- [x] Menubar daemon + global hotkey (Cmd+Shift+M)
- [x] Auto meeting detection (process watch + audio VAD)
- [x] Two recording modes: room (mic + diarization) and online (mic + system audio)

## v1.1 — Speaker Intelligence

- [ ] Named speaker identification (assign names to Speaker N labels)
- [ ] pyannote.audio diarization (optional, with HF token) for higher accuracy
- [ ] Speaker voice profile persistence (remember speakers across sessions)
- [ ] Per-speaker action item assignment

## v1.2 — Calendar & Auto-Detection

- [ ] EventKit calendar integration (sync upcoming meetings)
- [ ] Pre-meeting brief (who, what was discussed last time)
- [ ] Auto-start recording when meeting begins
- [ ] Post-meeting follow-up email draft
- [ ] Granola-style meeting brief in notification

## v1.3 — Cross-Platform

- [ ] Windows support (faster-whisper fallback, sounddevice cross-platform)
- [ ] Linux support (PulseAudio instead of BlackHole)
- [ ] Platform-specific audio device detection

## v1.4 — Distribution

- [ ] py2app bundle for macOS
- [ ] Notarized release
- [ ] Homebrew tap
- [ ] Auto-update mechanism

## v1.5 — Integrations

- [ ] OpenSuperWhisper integration (capture dictation output for export/memory)
- [ ] Obsidian vault sync (export MD directly to vault)
- [ ] Notion integration (push notes to Notion)
- [ ] Linear/Asana task creation from action items

## v2.0 — Meeting Chat (RAG)

- [ ] Local embeddings (all-MiniLM-L6-v2 via sentence-transformers)
- [ ] Vector search over session transcripts
- [ ] Chat with your meetings ("What did I promise in last week's sync?")
- [ ] Cross-session topic tracking
- [ ] Meeting insights dashboard
