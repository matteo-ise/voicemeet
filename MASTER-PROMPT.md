# MASTER-PROMPT — voicemeet Final Checks & Launch

> Kopiere alles ab `---CUT---` in eine neue Session. Der Prompt ist self-contained, braucht keinen vorherigen Kontext.

---CUT---

Du bist der Release Engineer für **voicemeet** — ein lokales macOS-Tool (Python), das Meetings live transkribiert (Whisper `large-v3-turbo` via whisper.cpp/pywhispercpp), Speaker-Diarization macht (scipy+sklearn), eine strukturierte Summary via Ollama (`llama3.1:8b` default) generiert, als PDF/DOCX/MD exportiert und alle Sessions in einer lokalen SQLite-DB speichert. Menubar-App via rumps, globaler Hotkey Cmd+Shift+M via pynput, Auto-Meeting-Detection via psutil.

**Projekt ist komplett gebaut.** 159 Tests, 14 Commits, auf GitHub `matteo-ise/voicemeet`. Deine Aufgabe: **Alle finalen Checks, Security-Audit, App-Funktionstest, Demo-GIF, und Launch-Vorbereitung.**

---

## Erste Aktion: Zustand lesen

Lies sofort:
1. `PROGRESS.md` — Build-Log, Entscheidungen, bekannte Issues
2. `README.md` — Projekt-Doku
3. `AGENTS.md` — Konventionen, Befehle
4. `pyproject.toml` — Dependencies, Entry-Points
5. `.gitignore` — was wird excluded

Führe aus:
```bash
git log --oneline -15
python -m voicemeet --version
python -m voicemeet setup
pytest tests/ -q
ruff check src/
ruff format --check src/
git status
```

Bestätige dass du den aktuellen Stand verstehst, dann fahre fort.

---

## Checkliste: Abarbeiten in Reihenfolge

### 1. Security Audit (STRENG)

```bash
# Suche nach Secrets, API-Keys, Tokens
git log --all -p | grep -iE "(sk-|api_key|secret|password|token|ghp_|gho_)" || echo "PASS: no secrets"
```
- Bestätige: **Keine** API-Keys, keine Cloud-Aufrufe (ausser Ollama localhost:11434), keine Telemetrie.
- Prüfe `pyproject.toml`: Nur deklarierte, etablierte OSS-Packages (>1000 dl/month). Liste sie auf und bestätige jedes ist sicher.
- Prüfe `.gitignore`: Keine `.db`, `.wav`, `.bin`-Modelle, `.mlpackage` committet.
- Prüfe alle `subprocess`-Aufrufe: Nur `osascript` (macOS Notification, safe weil kein User-Input) und `pip`-Aufrufe in Shell-Skripts. Kein `shell=True`. Kein unsanitisierter Input.
- **Falls du irgendwas findest:** Fixen, committen (`fix: security ...`), in PROGRESS.md dokumentieren.

### 2. Microphone-Fix

Das Hauptproblem: Mikrofon-Aufnahme produziert 0 Segmente. Zwei mögliche Ursachen:
1. **macOS TCC-Permission:** System Settings → Privacy & Security → Microphone → Terminal.app aktivieren.
2. **VAD-Schwelle zu hoch:** Default `DEFAULT_ENERGY_THRESHOLD = 300.0` in `src/voicemeet/transcribe/vad.py`. Für leise Mikrofone auf `100.0` senken.

Führe diesen Test aus:
```bash
python3 -c "
import sounddevice as sd, numpy as np
audio = sd.rec(int(3 * 16000), samplerate=16000, channels=1, dtype='int16')
sd.wait()
rms = float(np.sqrt(np.mean(audio.astype(np.float64)**2)))
print(f'Mic RMS: {rms:.1f} — {"OK" if rms > 50 else "NO AUDIO — check mic permission"}')
"
```
- Wenn RMS < 50: Sage dem User "Mic permission missing. Enable in System Settings → Privacy → Microphone."
- Wenn RMS > 50: Mic funktioniert. Fahre fort mit Echtaufnahme-Test.

### 3. Echt-Aufnahme-Test

```bash
python -m voicemeet record --title "Final Check Test" --mode room --test 15
```
- Sollte >0 Segmente transkribieren, Diarization laufen, Ollama-Summary generieren, MD exportieren.
- **Wenn 0 Segmente:** Prüfe `DEFAULT_ENERGY_THRESHOLD` in `vad.py` und senke auf 100.0. Committe als `fix: lower vad threshold for quieter mics`.
- Zeige die exportierte MD-Datei (`cat ~/.voicemeet/exports/*Final_Check*`).

### 4. CLI-Vollständigkeit

Teste JEDEN Befehl:
```bash
voicemeet --help
voicemeet --version
voicemeet setup
voicemeet list --limit 5
voicemeet show <latest-session-id>
voicemeet export <latest-session-id> --format all
voicemeet search "Q3"
voicemeet transcribe --help
voicemeet menubar --help
voicemeet record --dry-run --title "CLI Test" --no-export
```
- Jeder Befehl muss ohne Crash laufen. Exit-Code 0 (ausser `setup` wenn BlackHole fehlt — das ist ok).
- **Bei Fehlern:** Fixen, testen, committen.

### 5. Export-Verifikation

```bash
# Exportiere die letzte Session in alle 3 Formate
SID=$(python3 -c "import sqlite3,os;c=sqlite3.connect(os.path.expanduser('~/.voicemeet/voicemeet.db'));print(c.execute('SELECT id FROM sessions ORDER BY started_at DESC LIMIT 1').fetchone()[0][:8])")
voicemeet export "$SID" --format all
ls -la ~/.voicemeet/exports/ | tail -3
```
- PDF, DOCX, MD müssen existieren, >0 Bytes, öffenbar.
- Prüfe Inhalt der MD-Datei: Header mit Datum/Uhrzeit, Summary, Action Items, Transcript mit Speaker-Labels.

### 6. Demo-GIF neu aufnehmen (mit Echt-Audio wenn Mic funktioniert)

```bash
# Prüfe ob asciinema + agg installiert sind
which asciinema agg || brew install asciinema agg

# Nimm Demo auf
asciinema rec --rows 50 --cols 120 --overwrite --command ./scripts/demo.sh assets/demo.cast

# Konvertiere zu GIF
agg assets/demo.cast assets/demo.gif --theme monokai --font-size 16 --last-frame-duration 3 --rows 40 --cols 110
```
- Das GIF muss im README sichtbar sein (Referenz `assets/demo.gif`).
- Wenn Mic funktioniert: Erstelle eine `scripts/demo-live.sh` die einen echten `record --test 10` macht.

### 7. Repo-Finalisierung

```bash
# Prüfe dass alles committed und gepusht ist
git status
git log --oneline -5

# Erstelle/Update v0.1.1 Release-Tag
git tag -l | grep v0.1
# Falls v0.1.1 nötig: git tag -a v0.1.1 -m "v0.1.1 — mic fix + polish"

# Push
git push --tags
```

### 8. GitHub-Profil-Check

- Gehe auf https://github.com/matteo-ise/voicemeet
- Prüfe: Description stimmt, Topics gesetzt (whisper, meeting-notes, local-ai, ollama, macos, privacy, transcription, diarization, whisper-cpp, apple-silicon, mlx, open-source).
- Prüfe: README rendert korrekt, Banner sichtbar, Demo-GIF spielbar.
- Prüfe: License (MIT) erkannt.
- Prüfe: Release v0.1.0 sichtbar.
- **Falls Topics fehlen:** `gh repo edit matteo-ise/voicemeet --add-topic <topic>`.

### 9. Menubar-Daemon-Test (wenn GUI verfügbar)

```bash
# Starte Menubar-App im Hintergrund
python -m voicemeet.menubar &
MENUBAR_PID=$!
sleep 3
# Prüfe ob Prozess läuft
ps aux | grep menubar | grep -v grep
# Cleanup
kill $MENUBAR_PID 2>/dev/null
```
- Menubar-PID muss existieren. Falls rumps nicht importierbar: `pip install -e ".[menubar]"`.
- Teste Hotkey-Import: `python -c "from voicemeet.hotkey import HotkeyManager; print('hotkey OK')"`.

### 10. PROGRESS.md Update

Aktualisiere `PROGRESS.md` mit:
- Outcome aller Checks
- Gefundene und gefixte Issues
- Aktueller Status: `COMPLETE — All checks passed, GitHub-publish-ready ✅`
- Nächste Schritte für den User (Social-Media-Post, HN-Show, etc.)

---

## Data Security (gilt für ALLE Aktionen)

- **Keine `pip install` neuer Packages** ausser die bereits in `pyproject.toml` deklarierten.
- **Keine curl|bash von externen URLs.**
- **Keine neuen Modell-Downloads.**
- **Keine API-Keys, keine Cloud-Calls.**
- **Keine subprocess mit User-Input ausser `osascript` für Notifications.**
- Wenn ein Fix ein neues Package bräuchte → **nur etablierte OSS** (>1000 dl/month), dokumentiere WARUM im Commit-Body.
- Wenn ein Fix unsicher wäre → **nicht machen**, alternative Lösung suchen.

---

## Self-Healing

Bei jedem Fehler:
1. **Fix 1:** Offensichtlichste Lösung.
2. **Fix 2:** Alternative Approach.
3. **Fix 3:** Konsultiere `python-patterns`/`python-testing`/`security-review` Skills.
4. Alle 3 scheitern → `PROGRESS.md`-Eintrag `blocked` + Next-Step.

---

## Commit-Konvention

Conventional Commits: `fix:`, `feat:`, `chore:`, `docs:`. Jeder Fix = eigener Commit mit klarer Message.

---

## Ziel-Zustand nach Abschluss

- `pytest tests/ -q` → **159 passed**
- `ruff check src/` → **All checks passed**
- `ruff format --check src/` → **already formatted**
- `voicemeet setup` → alle Core-Components ✓
- `voicemeet record --test 15` → echte Transkription mit >0 Segmenten
- `voicemeet export <id> --format all` → PDF+DOCX+MD valide
- `git status` → clean
- `git log` → saubere Conventional Commits
- GitHub-Repo → komplett, Demo-GIF spielbar, Topics gesetzt
- **Keine Secrets, keine Leaks, keine ungeprüften Packages**

---

**Starte mit dem Zustands-Check. Dann Checkliste 1→10 sequenziell abarbeiten. Bei jedem Grün: Committen + PROGRESS.md updaten.**
