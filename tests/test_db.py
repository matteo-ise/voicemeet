"""Tests for the session store — CRUD, segments, exports, search."""

from __future__ import annotations

import pytest

from voicemeet.store.db import SessionStore


@pytest.fixture
def store() -> SessionStore:
    s = SessionStore(":memory:")
    yield s
    s.close()


def test_create_session(store: SessionStore) -> None:
    sess = store.create_session(title="Test Meeting", mode="room")
    assert sess.id is not None and len(sess.id) > 0
    assert sess.title == "Test Meeting"
    assert sess.status == "recording"
    assert sess.mode == "room"
    assert sess.participants == []
    assert sess.topics == []
    assert sess.duration_s == 0.0


def test_get_session(store: SessionStore) -> None:
    sess = store.create_session(title="Get Me")
    fetched = store.get_session(sess.id)
    assert fetched is not None
    assert fetched.id == sess.id
    assert fetched.title == "Get Me"
    assert store.get_session("nonexistent") is None


def test_finalize_session(store: SessionStore) -> None:
    sess = store.create_session(title="Finalize Me")
    finalized = store.finalize_session(
        sess.id,
        participants=["Alice", "Bob"],
        topics=["Q3 Roadmap", "Budget"],
        summary_markdown="# Summary\n\nDiscussion about Q3.",
    )
    assert finalized is not None
    assert finalized.status == "completed"
    assert finalized.ended_at is not None
    assert finalized.duration_s > 0
    assert finalized.participants == ["Alice", "Bob"]
    assert finalized.topics == ["Q3 Roadmap", "Budget"]
    assert "Discussion about Q3." in (finalized.summary_markdown or "")


def test_list_sessions(store: SessionStore) -> None:
    s1 = store.create_session(title="First")
    s2 = store.create_session(title="Second")
    s3 = store.create_session(title="Third")
    sessions = store.list_sessions(limit=10)
    assert len(sessions) == 3
    # Most recent first (DESC by started_at)
    assert sessions[0].id == s3.id
    assert sessions[1].id == s2.id
    assert sessions[2].id == s1.id


def test_list_sessions_limit(store: SessionStore) -> None:
    for i in range(5):
        store.create_session(title=f"S{i}")
    sessions = store.list_sessions(limit=2)
    assert len(sessions) == 2


def test_add_and_get_segments(store: SessionStore) -> None:
    sess = store.create_session(title="Segments Test")
    seg1 = store.add_segment(sess.id, 0, 0, 5000, "Hello world")
    seg2 = store.add_segment(sess.id, 1, 5000, 10000, "Second segment", speaker="Speaker 1")
    seg3 = store.add_segment(
        sess.id, 2, 10000, 15000, "Third segment", speaker="Speaker 2", confidence=0.95
    )

    segments = store.get_segments(sess.id)
    assert len(segments) == 3
    assert segments[0].text == "Hello world"
    assert segments[0].speaker is None
    assert segments[1].speaker == "Speaker 1"
    assert segments[2].confidence == 0.95
    assert segments[0].idx == 0
    assert segments[1].idx == 1


def test_update_segment_speaker(store: SessionStore) -> None:
    sess = store.create_session(title="Speaker Update")
    seg = store.add_segment(sess.id, 0, 0, 3000, "Test text")
    assert seg.speaker is None
    store.update_segment_speaker(seg.id, "Speaker 1")
    segments = store.get_segments(sess.id)
    assert segments[0].speaker == "Speaker 1"


def test_search_sessions(store: SessionStore) -> None:
    s1 = store.create_session(title="Q3 Planning")
    s2 = store.create_session(title="Standup")
    store.add_segment(s1.id, 0, 0, 5000, "Let's discuss the quarterly budget")
    store.add_segment(s2.id, 0, 0, 3000, "Daily standup notes")

    results = store.search_sessions("budget")
    assert len(results) == 1
    assert results[0].id == s1.id

    results = store.search_sessions("standup")
    assert len(results) == 1
    assert results[0].id == s2.id

    results = store.search_sessions("Q3")
    assert len(results) == 1
    assert results[0].id == s1.id


def test_add_and_get_exports(store: SessionStore) -> None:
    sess = store.create_session(title="Export Test")
    exp1 = store.add_export(sess.id, "pdf", "/tmp/test.pdf")
    exp2 = store.add_export(sess.id, "md", "/tmp/test.md")

    exports = store.get_exports(sess.id)
    assert len(exports) == 2
    assert exports[0].format in ("pdf", "md")
    assert all(e.session_id == sess.id for e in exports)


def test_delete_session_cascades(store: SessionStore) -> None:
    sess = store.create_session(title="Delete Me")
    store.add_segment(sess.id, 0, 0, 5000, "Some text")
    store.add_export(sess.id, "pdf", "/tmp/test.pdf")

    assert store.delete_session(sess.id) is True
    assert store.get_session(sess.id) is None
    assert store.get_segments(sess.id) == []
    assert store.get_exports(sess.id) == []
    assert store.delete_session(sess.id) is False


def test_update_session(store: SessionStore) -> None:
    sess = store.create_session(title="Original")
    updated = store.update_session(sess.id, title="Updated", participants=["Alice"])
    assert updated is not None
    assert updated.title == "Updated"
    assert updated.participants == ["Alice"]


def test_duration_str(store: SessionStore) -> None:
    sess = store.create_session(title="Duration Test")
    store.finalize_session(sess.id)
    finalized = store.get_session(sess.id)
    assert finalized is not None
    # Duration should be very short but formatted correctly
    parts = finalized.duration_str.split(":")
    assert len(parts) == 3


def test_segment_start_str(store: SessionStore) -> None:
    sess = store.create_session(title="Timestamp Test")
    seg = store.add_segment(sess.id, 0, 65000, 70000, "Test")
    segments = store.get_segments(sess.id)
    # 65 seconds = 1:05
    assert segments[0].start_str == "01:05"


def test_persists_to_disk(tmp_path) -> None:
    """Verify the store can create and read from a file-based DB."""
    db_path = str(tmp_path / "test.db")
    s1 = SessionStore(db_path)
    sess = s1.create_session(title="Persistent")
    s1.close()

    s2 = SessionStore(db_path)
    sessions = s2.list_sessions()
    assert len(sessions) == 1
    assert sessions[0].title == "Persistent"
    s2.close()
