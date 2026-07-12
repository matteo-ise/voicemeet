"""Export pipeline — PDF, DOCX, Markdown generation from sessions."""

from __future__ import annotations

from pathlib import Path

from voicemeet.store.models import Session
from voicemeet.summarize.ollama_summarizer import SummaryResult

DEFAULT_EXPORT_DIR = Path.home() / ".voicemeet" / "exports"


def _slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    safe = ""
    for ch in text:
        if ch.isalnum() or ch in "-_ ":
            safe += ch
        else:
            safe += " "
    return " ".join(safe.split()).replace(" ", "_")[:60] or "untitled"


def _default_filename(session: Session, summary: SummaryResult, ext: str) -> str:
    """Generate a default export filename."""
    date_str = session.started_dt.strftime("%Y%m%d_%H%M")
    title = _slugify(summary.title or session.title or "meeting")
    return f"{date_str}_{title}.{ext}"


def _resolve_output(
    output_path: str | Path | None,
    session: Session,
    summary: SummaryResult,
    ext: str,
    export_dir: Path | None = None,
) -> Path:
    """Resolve the output file path."""
    if output_path:
        p = Path(output_path).expanduser()
    else:
        d = export_dir or DEFAULT_EXPORT_DIR
        d.mkdir(parents=True, exist_ok=True)
        p = d / _default_filename(session, summary, ext)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p
