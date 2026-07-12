# voicemeet-pro

> Premium lokale Sprach- & Meeting-Notizen. Alle Pro-Features — PDF/DOCX/Markdown-Export, Session Memory, strukturierte Meeting-Summary mit Datum/Uhrzeit/Teilnehmern — komplett lokal, null Kosten.

## Status

🚧 In Planung — siehe [`BLUEPRINT.md`](./BLUEPRINT.md) für den vollständigen Bauplan.

## Was es wird

Ein leichtgewichtiges macOS-Tool (Python, Menubar + CLI), das Meetings live transkribiert (Whisper `small`, Apple-Silicon-optimiert), am Ende eine strukturierte Summary generiert (Header mit Datum, Uhrzeit, Dauer, Teilnehmern, Themen → dann Transkript) und mit einem Klick als PDF / DOCX / Markdown exportiert. Alle Sessions landen in einer lokalen SQLite-DB — durchsuchbar, wieder ladbar.

**Inspiriert von** [Meetily](https://github.com/Zackriya-Solutions/meetily) (Community Edition) und [OpenSuperWhisper](https://github.com/AugustoEnzo/OpenSuperWhisper) — aber als eigenständiges, leichtgewichtiges Python-Tool gebaut, nicht als Fork des schweren Tauri/Rust-Stacks.

## Warum

Granola, WhisperFlow und Meetily PRO kosten alle Geld für genau diese Features. Meetily Community Edition hat Live-Transkription + Ollama-Summary gratis, parkt aber Export, Session Memory und Auto-Detection hinter PRO. `voicemeet-pro` baut die fehlenden Premium-Features gratis, lokal, MIT-lizenziert.

## Lizenz

MIT
