"""Tests for the export pipeline — PDF, DOCX, Markdown."""

from __future__ import annotations

from pathlib import Path

import pytest

from voicemeet.export import _default_filename, _slugify
from voicemeet.export.docx import export_docx
from voicemeet.export.markdown import export_markdown
from voicemeet.export.pdf import export_pdf
from voicemeet.store.models import Segment, Session
from voicemeet.summarize.ollama_summarizer import SummaryResult


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


# ── Helper Tests ──────────────────────────────────────────


class TestHelpers:
    def test_slugify(self) -> None:
        assert _slugify("Q3 Planning Meeting") == "Q3_Planning_Meeting"
        assert _slugify("Test/Meeting: With! Special?") == "Test_Meeting_With_Special"
        assert _slugify("") == "untitled"
        assert _slugify("a" * 100) == "a" * 60

    def test_default_filename(self, sample_session: Session, sample_summary: SummaryResult) -> None:
        name = _default_filename(sample_session, sample_summary, "md")
        assert name.endswith(".md")
        assert "20260712_1400" in name
        assert "Q3_Roadmap_Planning" in name

    def test_default_filename_fallback(
        self, sample_session: Session, sample_summary: SummaryResult
    ) -> None:
        summary = SummaryResult()  # Empty title
        sample_session.title = None
        name = _default_filename(sample_session, summary, "pdf")
        assert name.endswith(".pdf")
        assert "meeting" in name


# ── Markdown Export Tests ─────────────────────────────────


class TestMarkdownExport:
    def test_export_creates_file(
        self,
        sample_session: Session,
        sample_summary: SummaryResult,
        sample_segments: list[Segment],
        tmp_path: Path,
    ) -> None:
        path = export_markdown(
            sample_session,
            sample_summary,
            sample_segments,
            output_path=tmp_path / "test.md",
        )
        assert Path(path).exists()
        content = Path(path).read_text(encoding="utf-8")
        assert "Q3 Roadmap Planning" in content
        assert "12.07.2026" in content
        assert "Alice" in content
        assert "Speaker 1" in content
        assert "Speaker 2" in content
        assert "Action Items" in content
        assert "Transcript" in content

    def test_export_to_default_dir(
        self,
        sample_session: Session,
        sample_summary: SummaryResult,
        sample_segments: list[Segment],
        tmp_path: Path,
    ) -> None:
        path = export_markdown(
            sample_session,
            sample_summary,
            sample_segments,
            export_dir=tmp_path,
        )
        assert Path(path).exists()
        assert str(tmp_path) in path
        assert path.endswith(".md")

    def test_export_empty_segments(
        self,
        sample_session: Session,
        sample_summary: SummaryResult,
        tmp_path: Path,
    ) -> None:
        path = export_markdown(
            sample_session,
            sample_summary,
            [],
            output_path=tmp_path / "empty.md",
        )
        content = Path(path).read_text(encoding="utf-8")
        assert "Transcript" in content  # Section header still present


# ── PDF Export Tests ──────────────────────────────────────


class TestPDFExport:
    def test_export_creates_pdf(
        self,
        sample_session: Session,
        sample_summary: SummaryResult,
        sample_segments: list[Segment],
        tmp_path: Path,
    ) -> None:
        path = export_pdf(
            sample_session,
            sample_summary,
            sample_segments,
            output_path=tmp_path / "test.pdf",
        )
        assert Path(path).exists()
        assert path.endswith(".pdf")
        # Check file is not empty
        assert Path(path).stat().st_size > 0

    def test_export_pdf_to_default_dir(
        self,
        sample_session: Session,
        sample_summary: SummaryResult,
        sample_segments: list[Segment],
        tmp_path: Path,
    ) -> None:
        path = export_pdf(
            sample_session,
            sample_summary,
            sample_segments,
            export_dir=tmp_path,
        )
        assert Path(path).exists()
        assert path.endswith(".pdf")

    def test_export_pdf_empty_segments(
        self,
        sample_session: Session,
        sample_summary: SummaryResult,
        tmp_path: Path,
    ) -> None:
        path = export_pdf(
            sample_session,
            sample_summary,
            [],
            output_path=tmp_path / "empty.pdf",
        )
        assert Path(path).exists()
        assert Path(path).stat().st_size > 0


# ── DOCX Export Tests ─────────────────────────────────────


class TestDOCXExport:
    def test_export_creates_docx(
        self,
        sample_session: Session,
        sample_summary: SummaryResult,
        sample_segments: list[Segment],
        tmp_path: Path,
    ) -> None:
        path = export_docx(
            sample_session,
            sample_summary,
            sample_segments,
            output_path=tmp_path / "test.docx",
        )
        assert Path(path).exists()
        assert path.endswith(".docx")
        assert Path(path).stat().st_size > 0

    def test_export_docx_content(
        self,
        sample_session: Session,
        sample_summary: SummaryResult,
        sample_segments: list[Segment],
        tmp_path: Path,
    ) -> None:
        path = export_docx(
            sample_session,
            sample_summary,
            sample_segments,
            output_path=tmp_path / "content.docx",
        )
        # Verify by reading the docx
        from docx import Document

        doc = Document(path)
        full_text = "\n".join(p.text for p in doc.paragraphs)
        assert "Q3 Roadmap Planning" in full_text
        assert "Alice" in full_text
        assert "Summary" in full_text

    def test_export_docx_to_default_dir(
        self,
        sample_session: Session,
        sample_summary: SummaryResult,
        sample_segments: list[Segment],
        tmp_path: Path,
    ) -> None:
        path = export_docx(
            sample_session,
            sample_summary,
            sample_segments,
            export_dir=tmp_path,
        )
        assert Path(path).exists()
        assert path.endswith(".docx")


# ── Integration: All Formats ──────────────────────────────


class TestAllFormats:
    def test_all_formats(
        self,
        sample_session: Session,
        sample_summary: SummaryResult,
        sample_segments: list[Segment],
        tmp_path: Path,
    ) -> None:
        md_path = export_markdown(
            sample_session,
            sample_summary,
            sample_segments,
            output_path=tmp_path / "test.md",
        )
        pdf_path = export_pdf(
            sample_session,
            sample_summary,
            sample_segments,
            output_path=tmp_path / "test.pdf",
        )
        docx_path = export_docx(
            sample_session,
            sample_summary,
            sample_segments,
            output_path=tmp_path / "test.docx",
        )
        assert Path(md_path).exists()
        assert Path(pdf_path).exists()
        assert Path(docx_path).exists()
        assert Path(md_path).read_text(encoding="utf-8")  # MD is readable
