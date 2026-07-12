"""Markdown export — session to .md file."""

from __future__ import annotations

from pathlib import Path

from voicemeet.export import _resolve_output
from voicemeet.store.models import Segment, Session
from voicemeet.summarize.ollama_summarizer import SummaryResult, build_full_document


def export_markdown(
    session: Session,
    summary: SummaryResult,
    segments: list[Segment],
    output_path: str | Path | None = None,
    export_dir: Path | None = None,
) -> str:
    """Export session as a Markdown file. Returns the file path."""
    path = _resolve_output(output_path, session, summary, "md", export_dir)
    content = build_full_document(session, summary, segments)
    path.write_text(content, encoding="utf-8")
    return str(path)
