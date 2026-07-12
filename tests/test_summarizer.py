"""Tests for the Ollama summarizer — mocked Ollama client, JSON parsing, header building."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from voicemeet.store.models import Segment, Session
from voicemeet.summarize.ollama_summarizer import (
    OllamaSummarizer,
    SummaryResult,
    _format_transcript,
    _parse_json_response,
    build_full_document,
    build_header,
)


@pytest.fixture
def sample_session() -> Session:
    return Session(
        id="test-id",
        title="Q3 Planning",
        started_at="2026-07-12T14:00:00",
        ended_at="2026-07-12T15:30:00",
        duration_s=5400,
        mode="room",
    )


@pytest.fixture
def sample_segments() -> list[Segment]:
    return [
        Segment(
            id=1,
            session_id="test-id",
            idx=0,
            start_ms=0,
            end_ms=5000,
            text="Let's discuss the Q3 roadmap.",
            speaker="Speaker 1",
        ),
        Segment(
            id=2,
            session_id="test-id",
            idx=1,
            start_ms=5000,
            end_ms=10000,
            text="I think we should focus on the new product launch.",
            speaker="Speaker 2",
        ),
        Segment(
            id=3,
            session_id="test-id",
            idx=2,
            start_ms=10000,
            end_ms=15000,
            text="Agreed. Alice will prepare the timeline by Friday.",
            speaker="Speaker 1",
        ),
    ]


@pytest.fixture
def sample_summary() -> SummaryResult:
    return SummaryResult(
        title="Q3 Roadmap Planning",
        participants=["Alice", "Bob"],
        topics=["Q3 Roadmap", "Product Launch", "Timeline"],
        summary_markdown="## Summary\n\nDiscussed Q3 priorities and product launch timeline.",
        action_items=["Alice: Prepare timeline by Friday", "Bob: Review launch checklist"],
    )


# ── JSON Parsing Tests ────────────────────────────────────


class TestJsonParsing:
    def test_clean_json(self) -> None:
        content = json.dumps(
            {
                "title": "Test Meeting",
                "participants": ["Alice", "Bob"],
                "topics": ["Topic 1"],
                "summary_markdown": "## Summary\n\nTest",
                "action_items": ["Task 1"],
            }
        )
        result = _parse_json_response(content)
        assert result.title == "Test Meeting"
        assert result.participants == ["Alice", "Bob"]
        assert result.topics == ["Topic 1"]
        assert "Test" in result.summary_markdown
        assert result.action_items == ["Task 1"]

    def test_code_fenced_json(self) -> None:
        content = (
            '```json\n{"title": "Fenced", "participants": [], '
            '"topics": [], "summary_markdown": "", "action_items": []}\n```'
        )
        result = _parse_json_response(content)
        assert result.title == "Fenced"

    def test_json_with_preamble(self) -> None:
        content = (
            'Here is the summary:\n{"title": "With Preamble", '
            '"participants": [], "topics": [], '
            '"summary_markdown": "", "action_items": []}'
        )
        result = _parse_json_response(content)
        assert result.title == "With Preamble"

    def test_malformed_json_regex_fallback(self) -> None:
        # Trailing comma makes this invalid JSON, but regex should still extract fields
        content = (
            '{"title": "Bad JSON", "participants": ["Alice",], '
            '"topics": [], "summary_markdown": "", "action_items": []}'
        )
        result = _parse_json_response(content)
        assert result.title == "Bad JSON"
        assert "Alice" in result.participants

    def test_empty_response(self) -> None:
        result = _parse_json_response("")
        assert result.title == ""
        assert result.is_empty

    def test_missing_fields(self) -> None:
        content = '{"title": "Partial"}'
        result = _parse_json_response(content)
        assert result.title == "Partial"
        assert result.participants == []
        assert result.topics == []


# ── Transcript Formatting ─────────────────────────────────


class TestTranscriptFormatting:
    def test_format_with_speakers(self, sample_segments: list[Segment]) -> None:
        transcript = _format_transcript(sample_segments)
        assert "Speaker 1" in transcript
        assert "Speaker 2" in transcript
        assert "Q3 roadmap" in transcript

    def test_format_empty(self) -> None:
        assert _format_transcript([]) == "(empty transcript)"

    def test_format_no_speaker(self) -> None:
        seg = Segment(id=1, session_id="s", idx=0, start_ms=0, end_ms=5000, text="Hello")
        transcript = _format_transcript([seg])
        assert "Speaker" in transcript
        assert "Hello" in transcript


# ── Header Building ───────────────────────────────────────


class TestHeaderBuilding:
    def test_header_contains_date(
        self, sample_session: Session, sample_summary: SummaryResult
    ) -> None:
        header = build_header(sample_session, sample_summary)
        assert "12.07.2026" in header
        assert "14:00" in header
        assert "15:30" in header

    def test_header_contains_participants(
        self, sample_session: Session, sample_summary: SummaryResult
    ) -> None:
        header = build_header(sample_session, sample_summary)
        assert "Alice" in header
        assert "Bob" in header

    def test_header_contains_topics(
        self, sample_session: Session, sample_summary: SummaryResult
    ) -> None:
        header = build_header(sample_session, sample_summary)
        assert "Q3 Roadmap" in header
        assert "Product Launch" in header

    def test_header_falls_back_to_session_title(self, sample_session: Session) -> None:
        summary = SummaryResult()  # Empty
        header = build_header(sample_session, summary)
        assert "Q3 Planning" in header  # Falls back to session.title

    def test_header_uses_summary_title(
        self, sample_session: Session, sample_summary: SummaryResult
    ) -> None:
        header = build_header(sample_session, sample_summary)
        assert "Q3 Roadmap Planning" in header

    def test_header_duration(self, sample_session: Session, sample_summary: SummaryResult) -> None:
        header = build_header(sample_session, sample_summary)
        assert "01:30:00" in header  # 5400 seconds = 1h 30m


# ── Full Document Building ────────────────────────────────


class TestFullDocument:
    def test_full_document_structure(
        self, sample_session: Session, sample_summary: SummaryResult, sample_segments: list[Segment]
    ) -> None:
        doc = build_full_document(sample_session, sample_summary, sample_segments)
        assert "# Q3 Roadmap Planning" in doc
        assert "## Summary" in doc
        assert "## Action Items" in doc
        assert "## Transcript" in doc
        assert "Speaker 1" in doc
        assert "Speaker 2" in doc

    def test_full_document_action_items(
        self, sample_session: Session, sample_summary: SummaryResult, sample_segments: list[Segment]
    ) -> None:
        doc = build_full_document(sample_session, sample_summary, sample_segments)
        assert "- [ ] Alice: Prepare timeline by Friday" in doc

    def test_full_document_empty_summary(
        self, sample_session: Session, sample_segments: list[Segment]
    ) -> None:
        summary = SummaryResult()
        doc = build_full_document(sample_session, summary, sample_segments)
        assert "## Transcript" in doc
        assert "## Summary" not in doc  # No summary section when empty


# ── OllamaSummarizer Tests (mocked) ───────────────────────


class TestOllamaSummarizer:
    @patch("ollama.chat")
    def test_summarize_success(
        self,
        mock_chat: MagicMock,
        sample_session: Session,
        sample_segments: list[Segment],
    ) -> None:
        mock_chat.return_value = {
            "message": {
                "content": json.dumps(
                    {
                        "title": "Q3 Planning Sync",
                        "participants": ["Alice", "Bob"],
                        "topics": ["Roadmap", "Launch"],
                        "summary_markdown": "## Summary\n\nGreat discussion.",
                        "action_items": ["Alice: Send timeline"],
                    }
                )
            }
        }

        summarizer = OllamaSummarizer()
        result = summarizer.summarize(sample_session, sample_segments)

        assert result.title == "Q3 Planning Sync"
        assert result.participants == ["Alice", "Bob"]
        assert "Great discussion" in result.summary_markdown
        assert "Alice: Send timeline" in result.action_items

    @patch("ollama.chat")
    def test_summarize_and_build(
        self,
        mock_chat: MagicMock,
        sample_session: Session,
        sample_segments: list[Segment],
    ) -> None:
        mock_chat.return_value = {
            "message": {
                "content": json.dumps(
                    {
                        "title": "Test",
                        "participants": ["Alice"],
                        "topics": ["Topic"],
                        "summary_markdown": "Short summary.",
                        "action_items": ["Do something"],
                    }
                )
            }
        }

        summarizer = OllamaSummarizer()
        summary, doc = summarizer.summarize_and_build(sample_session, sample_segments)

        assert summary.title == "Test"
        assert "# Test" in doc
        assert "Short summary" in doc
        assert "Do something" in doc

    @patch("ollama.list")
    def test_check_connection_success(self, mock_list: MagicMock) -> None:
        mock_list.return_value = {"models": []}
        summarizer = OllamaSummarizer()
        assert summarizer.check_connection() is True

    @patch("ollama.list")
    def test_check_connection_failure(self, mock_list: MagicMock) -> None:
        mock_list.side_effect = ConnectionError("Ollama not running")
        summarizer = OllamaSummarizer()
        assert summarizer.check_connection() is False

    @patch("ollama.chat")
    def test_summarize_malformed_response(
        self,
        mock_chat: MagicMock,
        sample_session: Session,
        sample_segments: list[Segment],
    ) -> None:
        mock_chat.return_value = {"message": {"content": "This is not JSON at all."}}

        summarizer = OllamaSummarizer()
        result = summarizer.summarize(sample_session, sample_segments)
        assert isinstance(result, SummaryResult)

    @patch("ollama.chat")
    def test_summarize_code_fenced_response(
        self,
        mock_chat: MagicMock,
        sample_session: Session,
        sample_segments: list[Segment],
    ) -> None:
        content = (
            '```json\n{"title": "Fenced", "participants": [], '
            '"topics": [], "summary_markdown": "", "action_items": []}\n```'
        )
        mock_chat.return_value = {"message": {"content": content}}

        summarizer = OllamaSummarizer()
        result = summarizer.summarize(sample_session, sample_segments)
        assert result.title == "Fenced"
