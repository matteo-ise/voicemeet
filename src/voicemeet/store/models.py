"""Data models for voicemeet sessions, segments, and export records."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class Session:
    """A single recording session (one meeting)."""

    id: str
    title: str | None
    started_at: str
    ended_at: str | None = None
    duration_s: float = 0.0
    participants: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    raw_audio_path: str | None = None
    status: str = "recording"
    summary_markdown: str | None = None
    mode: str = "room"

    @property
    def started_dt(self) -> datetime:
        return datetime.fromisoformat(self.started_at)

    @property
    def ended_dt(self) -> datetime | None:
        return datetime.fromisoformat(self.ended_at) if self.ended_at else None

    @property
    def duration_str(self) -> str:
        """Human-readable duration HH:MM:SS."""
        total = int(self.duration_s)
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    @classmethod
    def from_row(cls, row: Any) -> Session:
        return cls(
            id=row["id"],
            title=row["title"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            duration_s=row["duration_s"],
            participants=json.loads(row["participants"] or "[]"),
            topics=json.loads(row["topics"] or "[]"),
            raw_audio_path=row["raw_audio_path"],
            status=row["status"],
            summary_markdown=row["summary_markdown"],
            mode=row["mode"],
        )


@dataclass(slots=True)
class Segment:
    """A transcribed audio segment with optional speaker label."""

    id: int | None
    session_id: str
    idx: int
    start_ms: int
    end_ms: int
    text: str
    speaker: str | None = None
    confidence: float | None = None

    @property
    def start_str(self) -> str:
        """Timestamp as MM:SS or HH:MM:SS."""
        total = self.start_ms // 1000
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    @classmethod
    def from_row(cls, row: Any) -> Segment:
        return cls(
            id=row["id"],
            session_id=row["session_id"],
            idx=row["idx"],
            start_ms=row["start_ms"],
            end_ms=row["end_ms"],
            text=row["text"],
            speaker=row["speaker"],
            confidence=row["confidence"],
        )


@dataclass(slots=True)
class ExportRecord:
    """A generated export file (PDF, DOCX, or MD)."""

    id: int | None
    session_id: str
    format: str
    path: str
    created_at: str

    @classmethod
    def from_row(cls, row: Any) -> ExportRecord:
        return cls(
            id=row["id"],
            session_id=row["session_id"],
            format=row["format"],
            path=row["path"],
            created_at=row["created_at"],
        )
