"""CLI for voicemeet-pro — record, list, show, export, search, transcribe.

Uses typer + rich for a polished terminal experience.
All heavy deps (sounddevice, pywhispercpp, ollama) are lazy-imported
inside command functions, so --help works without them installed.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from voicemeet.export.docx import export_docx
from voicemeet.export.markdown import export_markdown
from voicemeet.export.pdf import export_pdf
from voicemeet.store.db import SessionStore
from voicemeet.store.models import Session
from voicemeet.summarize.ollama_summarizer import (
    OllamaSummarizer,
    SummaryResult,
)

app = typer.Typer(
    name="voicemeet",
    help="Premium local meeting notes — live transcription, AI summary, export.",
)
console = Console()


def get_store() -> SessionStore:
    """Create a SessionStore using VOICEMEET_DB env var or default path."""
    db_path = os.environ.get("VOICEMEET_DB", "~/.voicemeet/voicemeet.db")
    return SessionStore(db_path)


def _session_to_summary(session: Session) -> SummaryResult:
    """Reconstruct a SummaryResult from stored session data."""
    return SummaryResult(
        title=session.title or "",
        participants=session.participants,
        topics=session.topics,
        summary_markdown=session.summary_markdown or "",
    )


# ── record ────────────────────────────────────────────────


@app.command()
def record(
    title: str | None = typer.Option(None, "--title", "-t", help="Meeting title"),
    lang: str = typer.Option("auto", "--lang", "-l", help="Language code (de, en, auto)"),
    mode: str = typer.Option("room", "--mode", "-m", help="room, online, or auto"),
    test: int | None = typer.Option(None, "--test", help="Auto-stop after N seconds (smoke test)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Skip audio capture, use synthetic data"),
    no_export: bool = typer.Option(False, "--no-export", help="Skip auto-export"),
) -> None:
    """Record a meeting, transcribe, summarize, and export."""
    store = get_store()
    session = store.create_session(title=title, mode=mode)
    console.print(f"[bold green]Session started:[/] {session.id}")
    console.print(f"  Mode: {mode} | Language: {lang}")

    collected_segments: list = []

    if dry_run:
        console.print("[yellow]Dry run — using synthetic data[/]")
        from voicemeet.transcribe.engine import TranscriptionSegment

        collected_segments = [
            TranscriptionSegment(0, 5000, "Welcome to the meeting everyone.", None),
            TranscriptionSegment(5000, 10000, "Let's discuss the Q3 roadmap.", None),
            TranscriptionSegment(10000, 15000, "Alice will prepare the timeline.", None),
        ]
    else:
        try:
            from voicemeet.audio.capture import AudioCapture
            from voicemeet.transcribe.engine import StreamingTranscriber, Transcriber

            include_sys = mode in ("online", "auto")
            capture = AudioCapture(include_system_audio=include_sys)
            transcriber = Transcriber(language=lang if lang != "auto" else None)

            def on_seg(seg) -> None:
                console.print(f"  [{seg.start_str}] {seg.text[:80]}")
                collected_segments.append(seg)

            streaming = StreamingTranscriber(transcriber, on_segment=on_seg)

            console.print("[bold]Recording... Press Ctrl+C to stop.[/]")
            capture.start(on_block=streaming.process_block)

            if test:

                def _stop():
                    console.print("\n[yellow]Auto-stop triggered.[/]")
                    capture.stop()
                    streaming.flush()
                    _stop_event.set()

                _stop_event = threading.Event()
                timer = threading.Timer(test, _stop)
                timer.start()
                try:
                    _stop_event.wait()
                except KeyboardInterrupt:
                    pass
                finally:
                    timer.cancel()
            else:
                try:
                    import time

                    while capture.is_recording:
                        time.sleep(0.1)
                except KeyboardInterrupt:
                    pass

            audio = capture.stop()
            final = streaming.flush()
            if final:
                collected_segments.append(final)

            # Save audio
            if len(audio) > 0:
                audio_dir = Path.home() / ".voicemeet" / "recordings"
                wav_path = audio_dir / f"{session.id}.wav"
                capture.save_wav(wav_path, audio)
                store.update_session(session.id, raw_audio_path=str(wav_path))

        except ImportError as e:
            console.print(f"[red]Missing dependency: {e}[/]")
            store.delete_session(session.id)
            raise typer.Exit(1) from e

    # Save segments to DB
    for i, seg in enumerate(collected_segments):
        store.add_segment(
            session_id=session.id,
            idx=i,
            start_ms=seg.start_ms,
            end_ms=seg.end_ms,
            text=seg.text,
            confidence=seg.confidence,
        )

    console.print(f"[bold green]Transcribed {len(collected_segments)} segments.[/]")

    # Diarization (room mode only)
    segments = store.get_segments(session.id)
    if mode == "room" and len(segments) > 1 and not dry_run:
        try:
            from voicemeet.transcribe.diarize import SpeakerDiarizer

            diarizer = SpeakerDiarizer()
            full_audio = streaming.get_full_audio()
            seg_tuples = []
            for s in segments:
                start_sample = s.start_ms * 16000 // 1000
                end_sample = s.end_ms * 16000 // 1000
                seg_tuples.append((s.start_ms, s.end_ms, full_audio[start_sample:end_sample]))

            labels = diarizer.diarize(seg_tuples)
            for s, label in zip(segments, labels, strict=False):
                store.update_segment_speaker(s.id, label)
            console.print(f"[bold green]Diarization: {len(set(labels))} speakers detected.[/]")
            segments = store.get_segments(session.id)
        except Exception as e:
            console.print(f"[yellow]Diarization skipped: {e}[/]")
    elif dry_run:
        for s in segments:
            store.update_segment_speaker(s.id, "Speaker 1")
        segments = store.get_segments(session.id)

    # Summary
    summarizer = OllamaSummarizer()
    if summarizer.check_connection():
        console.print("[bold]Generating summary via Ollama...[/]")
        try:
            summary = summarizer.summarize(session, segments)
            console.print(f"  Title: {summary.title}")
            console.print(f"  Participants: {', '.join(summary.participants) or '—'}")
            console.print(f"  Topics: {', '.join(summary.topics) or '—'}")
        except Exception as e:
            console.print(f"[yellow]Summary failed: {e}[/]")
            summary = SummaryResult()
    else:
        console.print("[yellow]Ollama not running — skipping summary.[/]")
        console.print("  Start with: ollama serve")
        summary = SummaryResult()

    # Finalize
    store.finalize_session(
        session.id,
        participants=summary.participants,
        topics=summary.topics,
        summary_markdown=summary.summary_markdown,
    )

    # Auto-export
    if not no_export:
        session = store.get_session(session.id)
        assert session is not None
        path = export_markdown(session, summary, segments)
        store.add_export(session.id, "md", path)
        console.print(f"[bold green]Exported:[/] {path}")

    session = store.get_session(session.id)
    assert session is not None
    console.print(f"\n[bold green]Session complete:[/] {session.id}")
    console.print(f"  Duration: {session.duration_str}")
    store.close()


# ── list ──────────────────────────────────────────────────


@app.command("list")
def list_sessions(
    limit: int = typer.Option(20, "--limit", "-n", help="Max sessions to show"),
) -> None:
    """List all recorded sessions."""
    store = get_store()
    sessions = store.list_sessions(limit=limit)

    if not sessions:
        console.print("[dim]No sessions yet. Start one with: voicemeet record[/]")
        store.close()
        return

    table = Table(title="voicemeet sessions", show_lines=False)
    table.add_column("ID", style="dim", width=10)
    table.add_column("Title", style="bold")
    table.add_column("Date", width=12)
    table.add_column("Time", width=6)
    table.add_column("Duration", width=10)
    table.add_column("Mode", width=6)
    table.add_column("Status", width=10)

    for s in sessions:
        dt = s.started_dt
        table.add_row(
            s.id[:8],
            s.title or "Untitled",
            dt.strftime("%d.%m.%Y"),
            dt.strftime("%H:%M"),
            s.duration_str,
            s.mode,
            s.status,
        )

    console.print(table)
    console.print(f"\n[dim]{len(sessions)} session(s)[/]")
    store.close()


# ── show ──────────────────────────────────────────────────


@app.command()
def show(
    session_id: str = typer.Argument(..., help="Session ID (or first 8 chars)"),
) -> None:
    """Show details and transcript of a session."""
    store = get_store()
    session = _find_session(store, session_id)

    if session is None:
        console.print(f"[red]Session not found: {session_id}[/]")
        raise typer.Exit(1)

    # Header
    console.print(
        Panel(
            f"[bold]{session.title or 'Untitled Meeting'}[/]\n"
            f"Date: {session.started_dt.strftime('%d.%m.%Y %H:%M')}\n"
            f"Duration: {session.duration_str} | Mode: {session.mode} | Status: {session.status}\n"
            f"Participants: {', '.join(session.participants) or '—'}\n"
            f"Topics: {', '.join(session.topics) or '—'}",
            title=f"Session {session.id[:8]}",
        )
    )

    # Summary
    if session.summary_markdown:
        console.print("\n[bold]Summary[/]")
        console.print(session.summary_markdown)

    # Transcript
    segments = store.get_segments(session.id)
    if segments:
        console.print("\n[bold]Transcript[/]")
        table = Table(show_lines=False, padding=(0, 1))
        table.add_column("Time", style="dim", width=10)
        table.add_column("Speaker", style="cyan", width=12)
        table.add_column("Text")

        for seg in segments:
            table.add_row(seg.start_str, seg.speaker or "—", seg.text)

        console.print(table)
    else:
        console.print("\n[dim]No transcript segments.[/]")

    # Exports
    exports = store.get_exports(session.id)
    if exports:
        console.print("\n[bold]Exports[/]")
        for exp in exports:
            console.print(f"  {exp.format.upper():4s} {exp.path}")

    store.close()


# ── export ────────────────────────────────────────────────


@app.command()
def export(
    session_id: str = typer.Argument(..., help="Session ID (or first 8 chars)"),
    fmt: str = typer.Option("all", "--format", "-f", help="pdf, docx, md, or all"),
    output: str | None = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    """Export a session to PDF, DOCX, and/or Markdown."""
    store = get_store()
    session = _find_session(store, session_id)

    if session is None:
        console.print(f"[red]Session not found: {session_id}[/]")
        raise typer.Exit(1)

    segments = store.get_segments(session.id)
    summary = _session_to_summary(session)

    formats = ["pdf", "docx", "md"] if fmt == "all" else [fmt]
    exported: list[str] = []

    for f in formats:
        out = output if len(formats) == 1 else None
        if f == "md":
            path = export_markdown(session, summary, segments, output_path=out)
        elif f == "pdf":
            path = export_pdf(session, summary, segments, output_path=out)
        elif f == "docx":
            path = export_docx(session, summary, segments, output_path=out)
        else:
            console.print(f"[red]Unknown format: {f}[/]")
            continue
        store.add_export(session.id, f, path)
        exported.append(path)
        console.print(f"[bold green]Exported {f.upper()}:[/] {path}")

    store.close()


# ── search ────────────────────────────────────────────────


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
) -> None:
    """Search across all session transcripts and titles."""
    store = get_store()
    results = store.search_sessions(query)

    if not results:
        console.print(f"[dim]No sessions matching '{query}'[/]")
        store.close()
        return

    table = Table(title=f"Search: '{query}'", show_lines=False)
    table.add_column("ID", style="dim", width=10)
    table.add_column("Title", style="bold")
    table.add_column("Date", width=12)
    table.add_column("Mode", width=6)

    for s in results:
        dt = s.started_dt
        table.add_row(
            s.id[:8],
            s.title or "Untitled",
            dt.strftime("%d.%m.%Y"),
            s.mode,
        )

    console.print(table)
    console.print(f"\n[dim]{len(results)} match(es)[/]")
    store.close()


# ── transcribe ────────────────────────────────────────────


@app.command()
def transcribe(
    audio_file: str = typer.Argument(..., help="Path to WAV file (16kHz mono)"),
    title: str | None = typer.Option(None, "--title", "-t", help="Session title"),
    lang: str = typer.Option("auto", "--lang", "-l", help="Language code"),
    no_export: bool = typer.Option(False, "--no-export", help="Skip auto-export"),
) -> None:
    """Transcribe an existing audio file (offline meeting import)."""
    path = Path(audio_file).expanduser()
    if not path.exists():
        console.print(f"[red]File not found: {audio_file}[/]")
        raise typer.Exit(1)

    store = get_store()
    session = store.create_session(title=title or path.stem, mode="file")
    console.print(f"[bold green]Session created:[/] {session.id}")

    try:
        from voicemeet.transcribe.engine import Transcriber

        transcriber = Transcriber(language=lang if lang != "auto" else None)
        console.print("[bold]Transcribing...[/]")
        segments = transcriber.transcribe_file(path)

        for i, seg in enumerate(segments):
            store.add_segment(
                session_id=session.id,
                idx=i,
                start_ms=seg.start_ms,
                end_ms=seg.end_ms,
                text=seg.text,
                confidence=seg.confidence,
            )

        console.print(f"[bold green]Transcribed {len(segments)} segments.[/]")

    except ImportError as e:
        console.print(f"[red]Missing dependency: {e}[/]")
        store.delete_session(session.id)
        raise typer.Exit(1) from e

    # Summary
    db_segments = store.get_segments(session.id)
    summarizer = OllamaSummarizer()
    if summarizer.check_connection():
        try:
            summary = summarizer.summarize(session, db_segments)
        except Exception as e:
            console.print(f"[yellow]Summary failed: {e}[/]")
            summary = SummaryResult()
    else:
        console.print("[yellow]Ollama not running — skipping summary.[/]")
        summary = SummaryResult()

    store.finalize_session(
        session.id,
        participants=summary.participants,
        topics=summary.topics,
        summary_markdown=summary.summary_markdown,
    )

    if not no_export:
        session = store.get_session(session.id)
        assert session is not None
        md_path = export_markdown(session, summary, db_segments)
        store.add_export(session.id, "md", md_path)
        console.print(f"[bold green]Exported:[/] {md_path}")

    console.print(f"\n[bold green]Done:[/] {session.id}")
    store.close()


# ── Helpers ───────────────────────────────────────────────


def _find_session(store: SessionStore, session_id: str) -> Session | None:
    """Find a session by full ID or prefix."""
    session = store.get_session(session_id)
    if session:
        return session
    # Try prefix match
    sessions = store.list_sessions(limit=100)
    for s in sessions:
        if s.id.startswith(session_id):
            return s
    return None


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-V", help="Show version"),
) -> None:
    """voicemeet-pro — Premium local meeting notes."""
    if version:
        from voicemeet import __version__

        console.print(f"voicemeet {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()
