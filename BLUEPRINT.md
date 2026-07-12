# voicemeet-pro — Bauplan

> Premium lokale Sprach- & Meeting-Notizen. Alle Pro-Features (PDF/DOCX/MD-Export, Session Memory, Meeting-Summary mit Datum/Uhrzeit/Teilnehmern), null Kosten, komplett lokal. Inspiriert von Meetily Community Edition + OpenSuperWhisper — aber als eigenständiges, leichtgewichtiges Tool gebaut, nicht als Fork des schweren Tauri/Rust-Stacks.

---

## 1. Kontext-Brief (für frischen Agent, kalt startbar)

**Was das Projekt ist:** Ein macOS-Tool (Python, Menubar + CLI), das zwei Modi vereint:

1. **Meeting-Modus** — nimmt Mikrofon + System-Audio auf, transkribiert live (Whisper small, Apple-Silicon-optimiert), generiert am Ende eine strukturierte Summary (Header: Datum, Uhrzeit, Dauer, Teilnehmer, besprochene Themen → dann Transkript) und exportiert 1-Klick als PDF / DOCX / Markdown. Sessions werden in einer lokalen SQLite-DB gespeichert (Session Memory) — durchsuchbar, wieder ladbar.
2. **Diktat-Begleiter** (später) — arbeitet alongside OpenSuperWhisper (das du via Option+Space schon nutzt) und übernimmt dessen Transkript-Output für Export/Memory.

**Warum es existiert:** Granola, WhisperFlow, OpenSuperWhisper-Pro und Meetily PRO kosten alle Geld für genau diese Features. Meetily Community Edition hat Live-Transkription + Ollama-Summary gratis, parkt aber Export (PDF/DOCX/MD), Session Memory und Auto-Meeting-Detection hinter PRO. Wir bauen die fehlenden 10% gratis, lokal, MIT-lizenziert → starkes Github-Repo.

**Was es NICHT ist:** Kein Fork des Meetily-Tauri/Rust-Stacks (zu schwer zum Bauen). Kein Cloud-Service. Keine Bezahl-Funktionen. Kein Ersatz für OpenSuperWhispers Diktat-Everywhere — eine Ergänzung mit Fokus auf Meetings + Export + Memory.

**Lizenz:** MIT.

---

## 2. Ziele & Non-Goals

**Ziele**
- Live-Transkription mit Whisper `small` Modell, echtzeitnah auf Apple Silicon.
- Meeting-Recording: Mikrofon + System-Audio gleichzeitig (System-Audio via BlackHole oder ScreenCaptureKit).
- Strukturierte Summary mit Header (Datum, Start-/Endzeit, Dauer, erkannte Teilnehmer, Themen) + vollem Transkript.
- 1-Klick-Export: PDF, DOCX, Markdown.
- Session Memory: SQLite, alle Meetings speichern, durchsuchen, im CLI/Panel wieder öffnen.
- Lokale Summary-Generierung via Ollama (keine API-Keys, kein Cloud).
- Menubar-App (rumps) + CLI für Terminal-Nerds.

**Non-Goals (v1)**
- Speaker-Diarization (v1.1 — siehe Roadmap).
- Auto-Meeting-Detection (Kalender-Integration, v1.2).
- Windows/Linux (macOS-first; Portabilität später).
- Cloud-Sync.
- Ersatz für OpenSuperWhisper Diktat-Modus.

---

## 3. Tech-Stack

| Schicht | Wahl | Begründung |
|--------|------|-----------|
| Sprache | Python 3.11+ | User hat miniconda3; schnell zu bauen, reiche Libs |
| Transkription | `mlx-whisper` (Apple Silicon) mit Fallback `faster-whisper` | MLX = nativ M-Chip, small Modell echtzeitnah |
| Modell | `mlx-community/whisper-small-mlx` | User liebt small — schnell + gut |
| Audio-Capture | `sounddevice` + `numpy` (Mik); System-Audio via `BlackHole 2ch` (virtuelles Audiogerät) | Standard, gratis; BlackHole ist etabliert |
| Summary-LLM | `ollama` Python-Client → lokales Modell (z.B. `llama3.2` oder `qwen2.5`) | User will alles lokal; Ollama läuft eh |
| Session-Storage | `sqlite3` (stdlib) | Null Abhängigkeit, robust |
| PDF-Export | `reportlab` | Reif, gratis |
| DOCX-Export | `python-docx` | Standard für Word |
| MD-Export | stdlib `json`/String-Templates | Trivial |
| Menubar-UI | `rumps` | Einfachste macOS-Menubar-Lib in Python |
| CLI | `typer` + `rich` | Schöne CLI, geringe Lernkurve |
| Hotkey | `pynput` (global) oder `Quartz` CGEventTap | Für Start/Stop-Shortcut |
| Packaging | `py2app` (später) | .app-Bundle für Distribution |

**System-Voraussetzungen (im Plan dokumentieren):**
- macOS Apple Silicon (M1+)
- Python 3.11+ (miniconda3 ok)
- `brew install blackhole-2ch` (System-Audio) — optional, Mik-only geht auch
- `ollama` installiert + Modell gezogen (`ollama pull llama3.2`)
- Whisper-Modell: wird beim ersten Run automatisch von HuggingFace geladen

---

## 4. Architektur

```
voicemeet-pro/
├── README.md
├── BLUEPRINT.md            (diese Datei)
├── AGENTS.md               (opencode-Kontext)
├── pyproject.toml          (deps + tooling)
├── .gitignore
├── src/voicemeet/
│   ├── __init__.py
│   ├── __main__.py         (CLI-Entry: python -m voicemeet)
│   ├── cli.py              (typer-CLI: record, list, export, search)
│   ├── menubar.py          (rumps-Menubar-App)
│   ├── audio/
│   │   ├── capture.py      (sounddevice Mik + BlackHole System-Audio)
│   │   └── mixer.py        (Mik+System mischen, Normalisierung)
│   ├── transcribe/
│   │   ├── engine.py       (mlx-whisper/faster-whisper-Wrapper, Streaming-Chunks)
│   │   └── vad.py          (Voice-Activity-Detection, Pausen-Erkennung)
│   ├── summarize/
│   │   └── ollama_summarizer.py  (Header + Themen + Transcript-Formatierung)
│   ├── store/
│   │   ├── models.py       (dataclasses: Session, Segment, Summary)
│   │   ├── db.py           (sqlite3-Schema + CRUD)
│   │   └── schema.sql
│   ├── export/
│   │   ├── pdf.py          (reportlab)
│   │   ├── docx.py         (python-docx)
│   │   └── markdown.py     (Template)
│   └── hotkey.py           (globaler Shortcut)
├── templates/
│   ├── summary_prompt.txt  (Ollama-Prompt für Header-Struktur)
│   └── export_template.md  (MD-Template)
├── tests/
│   ├── test_db.py
│   ├── test_export.py
│   └── test_summarizer.py  (mit Ollama-Mock)
└── scripts/
    └── setup_blackhole.sh  (Hilfsskript System-Audio)
```

**Datenfluss:**
```
Audio-Capture (Mik + System) → VAD (Segment-Pausen) → Whisper-Stream (Rolling-Chunks)
    → Segmente in SQLite (Session Memory) → live-UI-Update
    → [Stop] → Ollama Summary (Header + Themen) → Session finalisiert
    → Export-Pipeline (PDF/DOCX/MD) → Datei gespeichert + in DB verlinkt
```

---

## 5. Implementierungs-Phasen (je eigener Commit-Bereich)

Jede Phase = 1+ Commits mit klaren Messages. Agent baut sequenziell, nach jeder Phase verifizieren.

### Phase 0 — Projekt-Gerüst (Commit: `chore: scaffold project + deps`)
- `pyproject.toml` mit allen Deps (typer, rich, sounddevice, numpy, mlx-whisper, ollama, reportlab, python-docx, rumps, pynput, pytest).
- `src/voicemeet/__init__.py`, `__main__.py` (Echo "voicemeet ready").
- `.gitignore` (Python, macOS, Ollama-Modelle, Audio-Temp, SQLite-DB lokal).
- `README.md` (Skeleton: was, install, usage).
- `AGENTS.md` (opencode: how to run tests, lint, build).
- **Verifikation:** `python -m voicemeet --version` läuft ohne Fehler.

### Phase 1 — Session-Storage & Modelle (Commit: `feat: session store + data models`)
- `store/schema.sql`: Tabelle `sessions` (id, title, started_at, ended_at, duration_s, participants JSON, topics JSON, raw_audio_path, status), `segments` (id, session_id, idx, start_ms, end_ms, text, speaker_hint), `exports` (id, session_id, format, path, created_at).
- `store/models.py`: `@dataclass Session, Segment, ExportRecord`.
- `store/db.py`: `SessionStore`-Klasse mit `create_session`, `add_segment`, `finalize_session`, `get_session`, `list_sessions`, `search_sessions(q)`.
- `tests/test_db.py`: In-Memory-DB, CRUD + Suche.
- **Verifikation:** `pytest tests/test_db.py` grün.

### Phase 2 — Audio-Capture + VAD (Commit: `feat: audio capture mic + system via blackhole`)
- `audio/capture.py`: `AudioCapture` mit `start()`/`stop()`, streamt 16kHz mono int16-Blocks (Whisper-Konvention). Mik via `sounddevice`. System-Audio via BlackHole-Gerät (auto-detect name "BlackHole 2ch"); wenn nicht vorhanden → Mik-only + Warnung.
- `audio/mixer.py`: Mik + System summieren, einfache Normalisierung (Clip-Prevention).
- `transcribe/vad.py`: Energie-basierte VAD (WebRTC-VAD optional), erkennt Pausen → Segment-Grenzen.
- Tests mit synthetischem Audio-Buffer (kein echtes Mik nötig).
- **Verifikation:** `pytest` + manuell: 5s aufnehmen → WAV-File in Temp.

### Phase 3 — Transkriptions-Engine (Commit: `feat: streaming whisper transcription`)
- `transcribe/engine.py`: `Transcriber` lädt `mlx-community/whisper-small-mlx` (Fallback `faster-whisper` small). Rolling-Window-Streaming: sammelt Audio bis VAD-Pause, schickt Chunk an Whisper, hängt Text an aktuellen Segment.
- Live-Callback: `on_segment(text)` für UI-Update.
- Sprache auto-detect (oder via CLI `--lang de`).
- **Verifikation:** Manuell: `voicemeet record --test` nimmt 10s auf → gibt Text aus.

### Phase 4 — Summary-Generator (Commit: `feat: ollama meeting summary with header`)
- `summarize/ollama_summarizer.py`: ruft lokales Ollama-Modell (`llama3.2` default) mit Prompt aus `templates/summary_prompt.txt`.
- Prompt erzwingt JSON-Output: `{ "title":..., "participants":[...], "topics":[...], "summary_markdown":..., "action_items":[...] }`.
- Teilnehmer-Erkennung: Heuristik aus Transkript (z.B. "ich", Namen-Muster) — v1 simple, v1.1 via Diarization.
- Header-Builder: formatiert Datum (lokal DE), Start/End, Dauer (`HH:MM:SS`), Teilnehmer-Liste, Themen → dann Summary → dann Transkript.
- `tests/test_summarizer.py`: Mock-Ollama (`monkeypatch`), prüft Header-Struktur.
- **Verifikation:** `pytest tests/test_summarizer.py` grün.

### Phase 5 — Export-Pipeline (Commit: `feat: export pdf docx markdown`)
- `export/markdown.py`: Session → MD nach Template (Header + Summary + Transkript mit Zeitstempeln).
- `export/pdf.py`: reportlab, sauberes Layout (Titel, Metadaten-Tabelle, Summary-Block, Transkript-Tabelle).
- `export/docx.py`: python-docx, gleiche Struktur.
- CLI: `voicemeet export <session-id> --format pdf|docx|md|all`.
- Export-Pfad wird in `exports`-Tabelle gespeichert.
- `tests/test_export.py`: Erzeuge Dummy-Session → exportiere alle 3 Formate → prüfe Datei existiert + Basis-Inhalt.
- **Verifikation:** `pytest tests/test_export.py` grün; manuell 1 Dummy-Session in alle 3 Formate exportieren.

### Phase 6 — CLI (Commit: `feat: cli record list export search`)
- `cli.py` (typer):
  - `voicemeet record [--title X] [--lang de]` — startet Live-Session, Ctrl+C stoppt → Summary + Auto-Export MD.
  - `voicemeet list [--limit 20]` — rich-Tabelle aller Sessions.
  - `voicemeet show <id>` — Details einer Session.
  - `voicemeet export <id> --format all` — Export.
  - `voicemeet search <query>` — Volltext über Transkripte.
  - `voicemeet transcribe <audio-file>` — Offline-Transkription einer Datei (Meeting-Import).
- **Verifikation:** `voicemeet record` → 30s sprechen → Stop → prüfe MD-Datei in `~/.voicemeet/exports/`.

### Phase 7 — Menubar-App + Hotkey (Commit: `feat: menubar app + global hotkey`)
- `menubar.py` (rumps): Icon in Menubar, Menu: "New Meeting", "Meetings..." (Liste), "Export last as PDF", "Quit".
- `hotkey.py`: globaler Shortcut (z.B. Cmd+Shift+M) startet/stoppt Meeting aus jedem App-Fokus.
- Live-Transkript-Fenster (kleines NSWindow via rumps oder PyObjC) — optional, v1 auch nur Menubar-Indikator.
- **Verifikation:** App startet, Hotkey toggelt Recording, Menubar zeigt Status.

### Phase 8 — Polish & Github-Readiness (Commit: `docs: readme + license + demo`)
- `README.md` vollständig: Features, Screenshots/GIF, Install (brew blackhole, ollama pull, pip install), Usage, Roadmap, Contributing.
- `LICENSE` (MIT).
- `ROADMAP.md`: v1.1 Diarization, v1.2 Auto-Detect + Kalender, v1.3 Windows/Linux, v1.4 Py2app-Bundle.
- Demo-GIF aufnehmen (Placeholder im README).
- `pyproject.toml`: entry-points `voicemeet = voicemeet.cli:app`.
- **Verifikation:** `pip install -e .` → `voicemeet --help` funktioniert; Repo-Push-ready.

---

## 6. Verifikations-Strategie (Agent führt nach jeder Phase aus)

- **Unit-Tests:** `pytest tests/ -q` nach Phasen 1, 4, 5.
- **Lint/Type:** `ruff check src/` + `ruff format --check src/` (in `pyproject.toml` konfigurieren).
- **Smoke-Test:** Nach Phase 6: `voicemeet record --test 5` nimmt 5s auf, transkribiert, summiert, exportiert MD — end-to-end ohne manuelles Eingreifen.
- **Pre-Commit:** Optional `pre-commit` mit ruff + pytest (nicht zwingend für v1).

---

## 7. Commit-Konvention

Conventional Commits: `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`. Eine Phase = ein logischer Commit (oder mehrere kleine, wenn Phase gross). Agent committet nach jeder grünen Verifikation. Niemals Secrets committen (Ollama läuft lokal, keine Keys).

---

## 8. Bekannte Fallstricke (Agent beachten)

- **BlackHole-Setup** braucht einmalige macOS-Audio-MIDI-Setup (Multi-Output-Gerät). Im README + `scripts/setup_blackhole.sh` dokumentieren. Fallback: Mik-only mit Warnung.
- **MLX-Whisper** nur Apple Silicon. Auf Intel → `faster-whisper`-Branch. Im Code: Plattform-Detect.
- **Ollama muss laufen** (`ollama serve`). CLI prüft Verbindung beim Summary-Schritt und gibt klaren Hinweis wenn down.
- **rumps + py2app** können quarantän-konfliktig sein; README erklärt `xattr -d com.apple.quarantine`.
- **System-Audio ohne BlackHole** geht auf macOS nicht trivial — das ist der Grund für BlackHole. Ehrlich im README kommunizieren.

---

## 9. Github-Publishing-Checkliste (letzte Phase)

- [ ] README mit Demo-GIF
- [ ] LICENSE (MIT)
- [ ] CONTRIBUTING.md
- [ ] .gitignore sauber (keine Modelle/Audio/DB committed)
- [ ] CI: GitHub Actions `pytest + ruff` auf push/PR
- [ ] Release v0.1.0 git tag
- [ ] Topics: `whisper`, `meeting-notes`, `local-ai`, `mlx`, `ollama`, `macos`, `privacy`, `open-source`
- [ ] Description: "Premium local meeting notes — PDF/DOCX/MD export, session memory, AI summaries. Zero cost, fully local."

---

## 10. Roadmap (v1 hinaus)

- **v1.1** Speaker-Diarization (pyannote.audio oder mlx-Diarization)
- **v1.2** Auto-Meeting-Detection + Kalender-Integration (EventKit)
- **v1.3** Windows/Linux-Port (faster-whisper, sounddevice cross-platform)
- **v1.4** Py2app-Bundle + notarized Release
- **v1.5** OpenSuperWhisper-Integration (Diktat-Output abfangen für Export/Memory)
- **v2.0** Chat mit Meetings (RAG über Session-DB via lokale Embeddings)
