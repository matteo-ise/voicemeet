"""Ollama-backed meeting summarizer.

Calls a local Ollama model to generate structured meeting summaries
with title, participants, topics, summary markdown, and action items.
Lazy-imports ollama for graceful degradation when not running.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from voicemeet.store.models import Segment, Session

_PROMPT_PATH = Path(__file__).parent.parent.parent.parent / "templates" / "summary_prompt.txt"
DEFAULT_MODEL = "llama3.2"
DEFAULT_HOST = "http://localhost:11434"


@dataclass(slots=True)
class SummaryResult:
    """Structured meeting summary from Ollama."""

    title: str = ""
    participants: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    summary_markdown: str = ""
    action_items: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.title and not self.summary_markdown and not self.action_items


def _load_prompt() -> str:
    """Load the summary prompt template."""
    if _PROMPT_PATH.exists():
        return _PROMPT_PATH.read_text(encoding="utf-8")
    # Fallback embedded prompt
    return (
        "Analyze this meeting transcript and respond with JSON containing: "
        "title, participants, topics, summary_markdown, action_items.\n\n"
        "TRANSCRIPT:\n{transcript}"
    )


def _format_transcript(segments: list[Segment]) -> str:
    """Format segments into a readable transcript with speaker labels and timestamps."""
    if not segments:
        return "(empty transcript)"
    lines: list[str] = []
    for seg in segments:
        speaker = seg.speaker or "Speaker"
        lines.append(f"[{seg.start_str}] {speaker}: {seg.text}")
    return "\n".join(lines)


def _parse_json_response(content: str) -> SummaryResult:
    """Parse Ollama's response into a SummaryResult. Handles code fences and malformed JSON."""
    # Strip code fences
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    # Try direct JSON parse
    try:
        data = json.loads(cleaned)
        return _dict_to_summary(data)
    except json.JSONDecodeError:
        pass

    # Try to extract JSON object from surrounding text
    json_match = re.search(r"\{[\s\S]*\}", cleaned)
    if json_match:
        try:
            data = json.loads(json_match.group())
            return _dict_to_summary(data)
        except json.JSONDecodeError:
            pass

    # Fallback: extract individual fields via regex
    return _regex_fallback(cleaned)


def _dict_to_summary(data: dict[str, Any]) -> SummaryResult:
    """Convert a parsed dict to SummaryResult with safe defaults."""
    return SummaryResult(
        title=str(data.get("title", "")),
        participants=[str(p) for p in data.get("participants", [])],
        topics=[str(t) for t in data.get("topics", [])],
        summary_markdown=str(data.get("summary_markdown", "")),
        action_items=[str(a) for a in data.get("action_items", [])],
    )


def _regex_fallback(text: str) -> SummaryResult:
    """Last-resort extraction when JSON parsing fails entirely."""
    title = ""
    title_match = re.search(r'"title"\s*:\s*"([^"]*)"', text)
    if title_match:
        title = title_match.group(1)

    participants: list[str] = []
    part_match = re.search(r'"participants"\s*:\s*\[([^\]]*)\]', text)
    if part_match:
        participants = re.findall(r'"([^"]*)"', part_match.group(1))

    topics: list[str] = []
    topics_match = re.search(r'"topics"\s*:\s*\[([^\]]*)\]', text)
    if topics_match:
        topics = re.findall(r'"([^"]*)"', topics_match.group(1))

    return SummaryResult(
        title=title,
        participants=participants,
        topics=topics,
        summary_markdown="",
        action_items=[],
    )


def build_header(session: Session, summary: SummaryResult) -> str:
    """Build the meeting header markdown with date, time, duration, participants, topics."""
    started = session.started_dt
    date_str = started.strftime("%d.%m.%Y")
    start_time = started.strftime("%H:%M")
    end_time = session.ended_dt.strftime("%H:%M") if session.ended_dt else "—"
    duration = session.duration_str

    title = summary.title or session.title or "Untitled Meeting"

    lines: list[str] = [
        f"# {title}",
        "",
        f"**Date:** {date_str}  ",
        f"**Time:** {start_time} – {end_time} ({duration})  ",
    ]

    participants = summary.participants or session.participants
    if participants:
        lines.append(f"**Participants:** {', '.join(participants)}  ")

    topics = summary.topics or session.topics
    if topics:
        lines.append(f"**Topics:** {', '.join(topics)}  ")

    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def build_full_document(session: Session, summary: SummaryResult, segments: list[Segment]) -> str:
    """Build the complete meeting document: header + summary + action items + transcript."""
    parts: list[str] = [build_header(session, summary)]

    if summary.summary_markdown:
        parts.append("## Summary\n")
        parts.append(summary.summary_markdown)
        parts.append("")

    if summary.action_items:
        parts.append("## Action Items\n")
        for item in summary.action_items:
            parts.append(f"- [ ] {item}")
        parts.append("")

    parts.append("## Transcript\n")
    for seg in segments:
        speaker = seg.speaker or "Speaker"
        parts.append(f"**[{seg.start_str}] {speaker}:** {seg.text}")
        parts.append("")

    return "\n".join(parts)


class OllamaSummarizer:
    """Meeting summarizer backed by a local Ollama model.

    Args:
        model: Ollama model name (default: llama3.2).
        host: Ollama server URL.
    """

    def __init__(self, model: str = DEFAULT_MODEL, host: str = DEFAULT_HOST) -> None:
        self.model = model
        self.host = host

    def check_connection(self) -> bool:
        """Check if Ollama is running and reachable."""
        try:
            import ollama

            ollama.list()
            return True
        except Exception:
            return False

    def summarize(self, session: Session, segments: list[Segment]) -> SummaryResult:
        """Generate a structured summary for a session.

        Args:
            session: The meeting session.
            segments: Transcribed segments with optional speaker labels.

        Returns:
            SummaryResult with title, participants, topics, summary, action items.
        """
        transcript = _format_transcript(segments)
        prompt_template = _load_prompt()
        prompt = (
            prompt_template.replace("{transcript}", transcript)
            .replace("{started_at}", session.started_at)
            .replace("{duration}", session.duration_str)
            .replace("{mode}", session.mode)
        )

        try:
            import ollama
        except ImportError as e:
            raise ImportError(
                "ollama package is required for summaries. Install with: pip install ollama"
            ) from e

        response = ollama.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            format="json",
        )

        # Handle both dict-like and attribute access
        if isinstance(response, dict):
            content = response.get("message", {}).get("content", "")
        else:
            content = getattr(response, "message", None)
            content = getattr(content, "content", "") if content else ""

        return _parse_json_response(content)

    def summarize_and_build(
        self,
        session: Session,
        segments: list[Segment],
    ) -> tuple[SummaryResult, str]:
        """Generate summary and build the full meeting document.

        Returns (summary_result, full_markdown_document).
        """
        summary = self.summarize(session, segments)
        doc = build_full_document(session, summary, segments)
        return summary, doc
