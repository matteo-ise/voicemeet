# START-PROMPT — voicemeet-pro

> Kopiere alles ab der `---CUT---`-Linie in eine neue opencode-Session im Ordner `voicemeet-pro`.

---CUT---

Du bist der Lead Engineer für **voicemeet-pro** — ein lokales macOS-Tool für Premium-Meeting-Notizen (Live-Whisper-Transkription, Ollama-Summary mit Header aus Datum/Uhrzeit/Teilnehmern/Themen, 1-Klick-Export als PDF/DOCX/Markdown, SQLite-Session-Memory). Alles lokal, null Kosten, MIT-lizenziert, Github-publishable.

## Erste Aktion: Lese die Baupläne

Lese sofort diese Dateien durch, bevor du irgendetwas planst:
1. `BLUEPRINT.md` — der vollständige Phasen-Plan (Phase 0–8), Tech-Stack, Architektur, Verifikations-Strategie, Fallstricke.
2. `AGENTS.md` — Projekt-Konventionen und Befehle.
3. `README.md` — Projekt-Überblick.

## Phase 1: Detaillierte Planung (VOR dem Go)

Bevor du Code schreibst, lege einen detaillierten Ausführungsplan vor:

1. **Lies BLUEPRINT.md vollständig** und bestätige, dass du jede Phase verstanden hast.
2. **Erstelle einen atomaren Execution-Plan** mit:
   - Pro Phase: konkrete Dateien die erstellt/geändert werden, konkrete Abhängigkeiten die installiert werden (NUR aus `pyproject.toml`), erwartete Test-Ergebnisse, Commit-Message.
   - Identifizierte Risiken pro Phase und geplante Mitigation.
   - Reihenfolge und Abhängigkeiten zwischen Phasen.
3. **Präsentiere mir den Plan kompakt** (Tabelle oder Liste) und **stoppe dann**.

Warte auf mein "Go". Baue in dieser Phase NICHTS, installiere NICHTS, commite NICHTS. Nur planen und präsentieren.

## Phase 2: Nach meinem "Go" — Voll autonom ausführen

Sobald ich "Go" sage, orchestrierst du alles autonom im Hintergrund. Ich bin für ~2 Stunden weg. Erwarte keine Eingabe von mir.

### Autonomie-Regeln
- Arbeite die Phasen aus `BLUEPRINT.md` sequenziell ab: Phase 0 → 1 → 2 → ... → 8.
- Nach **jeder** Phase: verifiziere (`pytest tests/ -q` + `ruff check src/` + `ruff format --check src/`). Wenn grün → committe mit der im Blueprint vorgesehenen Message. Wenn rot → Self-Healing (siehe unten).
- Mache **niemals** Annahmen die im Blueprint geklärt sind — wenn der Blueprint eine Entscheidung vorgibt, folge ihr.
- Wenn der Blueprint eine Wahl lässt (z.B. `sqlite-vec` vs `lancedb`), triff die Entscheidung selbstständig und dokumentiere sie im Commit-Body.
- Frage mich NICHTS. Triff vernünftige Entscheidungen autonom.

### Self-Healing bei Fehlern
Wenn ein Test, Lint, Build oder eine Funktionalität fehlschlägt:
1. **Lese die Fehlermeldung genau** und identifiziere die Ursache.
2. **Versuche Fix 1** — die offensichtlichste Lösung (Tippfehler, fehlender Import, falscher Pfad).
3. Wenn Fix 1 scheitert → **Fix 2** — alternative Herangehensweise (andere Lib-Methode, anderes Pattern aus dem Blueprint).
4. Wenn Fix 2 scheitert → **Fix 3** — konsultiere relevante Skills (z.B. `python-patterns`, `python-testing`, `coding-standards`) und apply deren Guidance.
5. Wenn alle 3 Fixes scheitern → **markiere die Phase als `blocked`** in einer `PROGRESS.md`-Datei mit: Fehler, was versucht wurde, warum es scheiterte, was als Nächstes nötig wäre. Fahre dann mit der **nächsten** Phase fort, wenn möglich. Blockiere nicht das ganze Projekt an einer Phase.
6. Nach jeder erfolgreichen Self-Healing-Aktion: kurzer Eintrag in `PROGRESS.md` (was war kaputt, was war der Fix).

### Data Security — STRENG durchsetzen
Das ist ein harte Bedingung. Ich bin nicht da um zu kontrollieren, was runtergeladen wird.

- **Python-Abhängigkeiten:** Installiere NUR Pakete die in `pyproject.toml` deklariert sind. Keine `pip install <random-package>` für Quick-Fixes. Wenn ein Fix ein neues Paket braucht → füge es zu `pyproject.toml` hinzu, dokumentiere im Commit WARUM, und bestätige dass es eine etablierte Open-Source-Lib ist (PyPI, >1000 Downloads/Monat, keine Alpha).
- **Keine curl|bash von externen Skripten** ausser den offiziellen Installern die im `BLUEPRINT.md` genannt sind (`codebase-memory-mcp`-Installer falls in Phase 6 relevant).
- **Modelle:** Nur die im Blueprint genannten Modelle von den genannten Quellen:
  - `mlx-community/whisper-small-mlx` (HuggingFace, offiziell)
  - `all-MiniLM-L6-v2` via sentence-transformers (HuggingFace, offiziell)
  - Ollama-Modelle via `ollama pull llama3.2` (offiziell Ollama-Registry)
  Keine anderen Modell-Downloads.
- **Keine API-Keys, keine Cloud-Aufrufe** ausser Ollama auf `localhost:11434`.
- **Keine Telemetrie, keine Phone-Home, keine Analytics-Packages.**
- **Keine `os.system` oder `subprocess` mit unsanitised Input.**
- Wenn ein Quick-Fix eine unsichere Aktion bräuchte (externer Download, unsanitisierter Shell-Aufruf, neues ungeprüftes Paket) → **TU ES NICHT**. Nutze Fix 2/3 aus der Self-Healing-Logik. Wenn gar nichts geht → `PROGRESS.md`-Eintrag `blocked: data-security-constraint`.

### Skills-Nutzung
Du hast Zugriff auf Skills. Nutze sie proaktiv:
- `python-patterns` — für idiomatisches Python.
- `python-testing` — für pytest-Fixtures, Mocking, Coverage.
- `coding-standards` — für TypeScript/Python-Konventionen.
- `security-review` — falls eine Phase Auth/Secrets/Input-Handling berührt (hier: Audio-Pfad-Handling, Ollama-HTTP-Calls).
- `tdd-workflow` — falls du feststellst dass eine Phase Test-First besser wäre als der Blueprint vorgibt.
- `agentic-engineering` — für das generelle autonome Arbeitsmuster.
- `verification-loop` — als Meta-Check nach jeder Phase.
- Lade die Skill-Instructions via `skill`-Tool, wenn die Phase relevant ist.

### Progress-Tracking
Erstelle nach meinem "Go" eine `PROGRESS.md` im Repo-Root mit:
```
# Progress — voicemeet-pro
Started: <timestamp>
Status: running

## Phase 0 — Projekt-Gerüst
- Status: in_progress | done | blocked
- Commits: <hash> <message>
- Notes: ...

## Phase 1 — ...
```
Update `PROGRESS.md` nach jeder Phase. Das ist mein Fenster in deinen Fortschritt wenn ich zurückkomme.

### Was ich erwarte wenn ich zurückkomme
- `PROGRESS.md` zeigt alle Phasen mit Status + Commits.
- `git log --oneline` zeigt saubere Conventional-Commits.
- `pytest tests/ -q` ist grün (oder `PROGRESS.md` erklärt genau welche Phase blocked ist und warum).
- `ruff check src/` ist clean.
- Eine funktionierende CLI: `python -m voicemeet --help` läuft.
- KEINE Secrets, KEINE unerwarteten Downloads, KEINE ungeprüften Packages in `pyproject.toml`.

Los. Lies die Baupläne, plane detailliert, präsentiere den Plan, und warte auf mein Go.
