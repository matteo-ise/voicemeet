"""Tests for the CLI — list, show, export, search, record --dry-run."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from voicemeet.cli import app
from voicemeet.store.db import SessionStore

runner = CliRunner()


@pytest.fixture(autouse=True)
def _wide_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure rich tables are wide enough in test output."""
    monkeypatch.setenv("COLUMNS", "200")


@pytest.fixture
def test_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set VOICEMEET_DB to a temp path and return it."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("VOICEMEET_DB", str(db_path))
    # Also set the exports dir to tmp
    monkeypatch.setattr(
        "voicemeet.export.DEFAULT_EXPORT_DIR",
        tmp_path / "exports",
    )
    return db_path


@pytest.fixture
def populated_db(test_db: Path) -> str:
    """Create a DB with one session and segments. Returns the session ID."""
    store = SessionStore(str(test_db))
    session = store.create_session(title="Q3 Planning", mode="room")
    store.add_segment(session.id, 0, 0, 5000, "Let's discuss the roadmap.", "Speaker 1")
    store.add_segment(session.id, 1, 5000, 10000, "Focus on product launch.", "Speaker 2")
    store.finalize_session(
        session.id,
        participants=["Alice", "Bob"],
        topics=["Roadmap", "Launch"],
        summary_markdown="## Summary\n\nDiscussed Q3 priorities.",
    )
    sid = session.id
    store.close()
    return sid


# ── Help & Version ────────────────────────────────────────


class TestHelp:
    def test_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "record" in result.stdout
        assert "list" in result.stdout
        assert "export" in result.stdout
        assert "search" in result.stdout

    def test_version(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "voicemeet" in result.stdout

    def test_no_args_shows_help(self) -> None:
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        assert "record" in result.stdout  # Help is shown


# ── list ──────────────────────────────────────────────────


class TestList:
    def test_list_empty(self, test_db: Path) -> None:
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "No sessions" in result.stdout

    def test_list_with_sessions(self, populated_db: str) -> None:
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "Q3 Planning" in result.stdout

    def test_list_limit(self, populated_db: str) -> None:
        result = runner.invoke(app, ["list", "--limit", "5"])
        assert result.exit_code == 0


# ── show ──────────────────────────────────────────────────


class TestShow:
    def test_show_full_id(self, populated_db: str) -> None:
        result = runner.invoke(app, ["show", populated_db])
        assert result.exit_code == 0
        assert "Q3 Planning" in result.stdout
        assert "Speaker 1" in result.stdout
        assert "Speaker 2" in result.stdout
        assert "roadmap" in result.stdout

    def test_show_short_id(self, populated_db: str) -> None:
        short_id = populated_db[:8]
        result = runner.invoke(app, ["show", short_id])
        assert result.exit_code == 0
        assert "Q3 Planning" in result.stdout

    def test_show_not_found(self, test_db: Path) -> None:
        result = runner.invoke(app, ["show", "nonexistent"])
        assert result.exit_code == 1
        assert "not found" in result.stdout


# ── export ────────────────────────────────────────────────


class TestExport:
    def test_export_md(self, populated_db: str, tmp_path: Path) -> None:
        out = tmp_path / "test_export.md"
        result = runner.invoke(
            app, ["export", populated_db, "--format", "md", "--output", str(out)]
        )
        assert result.exit_code == 0
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "Q3 Planning" in content

    def test_export_pdf(self, populated_db: str, tmp_path: Path) -> None:
        out = tmp_path / "test_export.pdf"
        result = runner.invoke(
            app, ["export", populated_db, "--format", "pdf", "--output", str(out)]
        )
        assert result.exit_code == 0
        assert out.exists()
        assert out.stat().st_size > 0

    def test_export_docx(self, populated_db: str, tmp_path: Path) -> None:
        out = tmp_path / "test_export.docx"
        result = runner.invoke(
            app, ["export", populated_db, "--format", "docx", "--output", str(out)]
        )
        assert result.exit_code == 0
        assert out.exists()
        assert out.stat().st_size > 0

    def test_export_all(self, populated_db: str) -> None:
        result = runner.invoke(app, ["export", populated_db, "--format", "all"])
        assert result.exit_code == 0
        assert "Exported" in result.stdout

    def test_export_not_found(self, test_db: Path) -> None:
        result = runner.invoke(app, ["export", "nonexistent", "--format", "md"])
        assert result.exit_code == 1


# ── search ────────────────────────────────────────────────


class TestSearch:
    def test_search_found(self, populated_db: str) -> None:
        result = runner.invoke(app, ["search", "roadmap"])
        assert result.exit_code == 0
        assert "Q3 Planning" in result.stdout

    def test_search_not_found(self, populated_db: str) -> None:
        result = runner.invoke(app, ["search", "nonexistent_term"])
        assert result.exit_code == 0
        assert "No sessions" in result.stdout

    def test_search_title(self, populated_db: str) -> None:
        result = runner.invoke(app, ["search", "Q3"])
        assert result.exit_code == 0
        assert "Q3 Planning" in result.stdout


# ── record --dry-run ──────────────────────────────────────


class TestRecordDryRun:
    def test_dry_run_creates_session(self, test_db: Path, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            ["record", "--dry-run", "--title", "Test Meeting", "--no-export"],
        )
        assert result.exit_code == 0
        assert "Session started" in result.stdout
        assert "3 segments" in result.stdout

    def test_dry_run_with_export(self, test_db: Path, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            ["record", "--dry-run", "--title", "Export Test"],
        )
        assert result.exit_code == 0
        assert "Exported" in result.stdout

    def test_dry_run_list_after(self, test_db: Path) -> None:
        runner.invoke(app, ["record", "--dry-run", "--title", "List Test", "--no-export"])
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "List Test" in result.stdout
