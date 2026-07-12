# PROGRESS.md — voicemeet-pro Build-Log

## Status: IN PROGRESS

Autonome Build-Session gestartet.

## Phasen-Übersicht

| Phase | Status | Commit | Tests | Ruff | Notes |
|-------|--------|--------|-------|------|-------|
| 0 — Scaffold | 🔄 in progress | — | — | — | — |
| 1 — Session Store | ⏳ pending | — | — | — | — |
| 2 — Audio + VAD | ⏳ pending | — | — | — | — |
| 3 — Transkription | ⏳ pending | — | — | — | — |
| 4 — Diarization | ⏳ pending | — | — | — | — |
| 5 — Summary | ⏳ pending | — | — | — | — |
| 6 — Export | ⏳ pending | — | — | — | — |
| 7 — CLI | ⏳ pending | — | — | — | — |
| 8 — Auto-Detection | ⏳ pending | — | — | — | — |
| 9 — Menubar + Hotkey | ⏳ pending | — | — | — | — |
| 10 — Polish | ⏳ pending | — | — | — | — |

## Autonome Entscheidungen

1. **Engine: `pywhispercpp` statt `mlx-whisper`** — Reuse der lokalen `ggml-large-v3-turbo-*.bin` Modelle (OpenSuperWhisper), kein Download nötig, bessere Qualität als `small`. Fallback: `faster-whisper`.
2. **Diarization: spektrales Clustering (scipy+sklearn)** — Kein pyannote (braucht HF-Token = API-Key, verstösst gegen Security-Regel). Labels: "Speaker 1/2/3".
3. **Auto-Detection: psutil Prozess-Watch + Audio-VAD** — Nicht EventKit/Kalender (pyobjc-Komplex). Fängt auch Nicht-Kalender-Meetings.
4. **Zwei Aufnahme-Modi**: `--mode room` (Mik + Diarization), `--mode online` (Mik + System-Audio via BlackHole), `--mode auto` (Prozess-Watch).
5. **Deps gesplittet**: core (zuverlässig) + optional[audio,transcribe,menubar,dev] (platform-spezifisch/schwer).

## Self-Healing Log

(noch keine Einträge)
