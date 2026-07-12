"""SQLite-backed session store with CRUD and full-text search."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from voicemeet.store.models import ExportRecord, Segment, Session

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def _now_iso() -> str:
    return datetime.now().isoformat()


class SessionStore:
    """Persistent session storage backed by SQLite.

    Pass ':memory:' for an in-memory database (useful for tests).
    """

    def __init__(self, db_path: str = "~/.voicemeet/voicemeet.db") -> None:
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._connect()

    def _connect(self) -> None:
        path = self.db_path
        if path != ":memory:":
            resolved = Path(path).expanduser()
            resolved.parent.mkdir(parents=True, exist_ok=True)
            path = str(resolved)
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        assert self._conn is not None
        schema = _SCHEMA_PATH.read_text(encoding="utf-8")
        self._conn.executescript(schema)
        self._conn.commit()

    @property
    def conn(self) -> sqlite3.Connection:
        assert self._conn is not None, "Store is closed"
        return self._conn

    # ── Session CRUD ──────────────────────────────────────────

    def create_session(
        self,
        title: str | None = None,
        mode: str = "room",
        raw_audio_path: str | None = None,
    ) -> Session:
        """Create a new recording session and persist it."""
        sid = str(uuid.uuid4())
        now = _now_iso()
        self.conn.execute(
            "INSERT INTO sessions (id, title, started_at, mode, raw_audio_path) "
            "VALUES (?, ?, ?, ?, ?)",
            (sid, title, now, mode, raw_audio_path),
        )
        self.conn.commit()
        return Session(
            id=sid,
            title=title,
            started_at=now,
            raw_audio_path=raw_audio_path,
            mode=mode,
        )

    def finalize_session(
        self,
        session_id: str,
        participants: list[str] | None = None,
        topics: list[str] | None = None,
        summary_markdown: str | None = None,
    ) -> Session | None:
        """Mark a session as completed, set end time and duration."""
        sess = self.get_session(session_id)
        if sess is None:
            return None
        now = _now_iso()
        duration = (datetime.fromisoformat(now) - sess.started_dt).total_seconds()
        self.conn.execute(
            "UPDATE sessions SET ended_at=?, duration_s=?, status='completed', "
            "participants=?, topics=?, summary_markdown=? WHERE id=?",
            (
                now,
                duration,
                json.dumps(participants or []),
                json.dumps(topics or []),
                summary_markdown,
                session_id,
            ),
        )
        self.conn.commit()
        return self.get_session(session_id)

    def get_session(self, session_id: str) -> Session | None:
        row = self.conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        return Session.from_row(row) if row else None

    def list_sessions(self, limit: int = 20, offset: int = 0) -> list[Session]:
        rows = self.conn.execute(
            "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [Session.from_row(r) for r in rows]

    def search_sessions(self, query: str, limit: int = 50) -> list[Session]:
        """Full-text search over segment text and session title."""
        pattern = f"%{query}%"
        rows = self.conn.execute(
            "SELECT DISTINCT s.* FROM sessions s "
            "LEFT JOIN segments seg ON seg.session_id = s.id "
            "WHERE s.title LIKE ? OR seg.text LIKE ? "
            "ORDER BY s.started_at DESC LIMIT ?",
            (pattern, pattern, limit),
        ).fetchall()
        return [Session.from_row(r) for r in rows]

    def delete_session(self, session_id: str) -> bool:
        cur = self.conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def update_session(
        self,
        session_id: str,
        **fields: Any,
    ) -> Session | None:
        """Update arbitrary fields on a session. Keys must match column names."""
        if not fields:
            return self.get_session(session_id)
        allowed = {
            "title",
            "participants",
            "topics",
            "summary_markdown",
            "raw_audio_path",
            "status",
        }
        updates: dict[str, Any] = {}
        for k, v in fields.items():
            if k not in allowed:
                continue
            if k in ("participants", "topics") and isinstance(v, list):
                updates[k] = json.dumps(v)
            else:
                updates[k] = v
        if not updates:
            return self.get_session(session_id)
        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [session_id]
        self.conn.execute(f"UPDATE sessions SET {set_clause} WHERE id=?", values)
        self.conn.commit()
        return self.get_session(session_id)

    # ── Segment CRUD ──────────────────────────────────────────

    def add_segment(
        self,
        session_id: str,
        idx: int,
        start_ms: int,
        end_ms: int,
        text: str,
        speaker: str | None = None,
        confidence: float | None = None,
    ) -> Segment:
        cur = self.conn.execute(
            "INSERT INTO segments (session_id, idx, start_ms, end_ms, text, speaker, confidence) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session_id, idx, start_ms, end_ms, text, speaker, confidence),
        )
        self.conn.commit()
        return Segment(
            id=cur.lastrowid,
            session_id=session_id,
            idx=idx,
            start_ms=start_ms,
            end_ms=end_ms,
            text=text,
            speaker=speaker,
            confidence=confidence,
        )

    def get_segments(self, session_id: str) -> list[Segment]:
        rows = self.conn.execute(
            "SELECT * FROM segments WHERE session_id=? ORDER BY idx ASC",
            (session_id,),
        ).fetchall()
        return [Segment.from_row(r) for r in rows]

    def update_segment_speaker(self, segment_id: int, speaker: str) -> None:
        """Set speaker label on a segment (used by diarization)."""
        self.conn.execute("UPDATE segments SET speaker=? WHERE id=?", (speaker, segment_id))
        self.conn.commit()

    # ── Export CRUD ───────────────────────────────────────────

    def add_export(self, session_id: str, fmt: str, path: str) -> ExportRecord:
        now = _now_iso()
        cur = self.conn.execute(
            "INSERT INTO exports (session_id, format, path, created_at) VALUES (?, ?, ?, ?)",
            (session_id, fmt, path, now),
        )
        self.conn.commit()
        return ExportRecord(
            id=cur.lastrowid,
            session_id=session_id,
            format=fmt,
            path=path,
            created_at=now,
        )

    def get_exports(self, session_id: str) -> list[ExportRecord]:
        rows = self.conn.execute(
            "SELECT * FROM exports WHERE session_id=? ORDER BY created_at DESC",
            (session_id,),
        ).fetchall()
        return [ExportRecord.from_row(r) for r in rows]

    # ── Lifecycle ─────────────────────────────────────────────

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> SessionStore:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
