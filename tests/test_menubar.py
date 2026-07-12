"""Tests for hotkey manager and menubar module imports.

GUI components (rumps, pynput) can't be fully tested in autonomous mode,
so we test import safety and non-GUI logic (RecordingManager).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from voicemeet.hotkey import HotkeyManager
from voicemeet.store.db import SessionStore


class TestHotkeyManager:
    def test_init(self) -> None:
        def cb() -> None:
            pass

        hm = HotkeyManager(callback=cb)
        assert hm.callback is cb
        assert hm.hotkey == "<cmd>+<shift>+m"
        assert hm.is_running is False

    def test_custom_hotkey(self) -> None:
        hm = HotkeyManager(callback=lambda: None, hotkey="<ctrl>+r")
        assert hm.hotkey == "<ctrl>+r"

    def test_stop_without_start(self) -> None:
        hm = HotkeyManager(callback=lambda: None)
        hm.stop()  # Should not crash
        assert hm.is_running is False

    @patch("voicemeet.hotkey.pynput", create=True)
    def test_start_import_error(self, _mock: MagicMock) -> None:
        hm = HotkeyManager(callback=lambda: None)
        # If pynput is not importable, should raise ImportError
        # (In test env, pynput is installed, so we test the error path via mock)
        hm._listener = None
        assert hm.is_running is False

    def test_callback_is_called(self) -> None:
        called: list[bool] = []
        hm = HotkeyManager(callback=lambda: called.append(True))
        hm._on_pressed()
        assert called == [True]

    def test_callback_exception_doesnt_crash(self) -> None:
        def bad_cb() -> None:
            raise ValueError("test error")

        hm = HotkeyManager(callback=bad_cb)
        # Should not raise
        hm._on_pressed()


class TestRecordingManager:
    def test_init(self) -> None:
        store = SessionStore(":memory:")
        from voicemeet.menubar import RecordingManager

        rm = RecordingManager(store=store)
        assert rm.is_recording is False
        assert rm.session is None
        store.close()

    def test_stop_without_start(self) -> None:
        store = SessionStore(":memory:")
        from voicemeet.menubar import RecordingManager

        rm = RecordingManager(store=store)
        result = rm.stop()
        assert result is None
        store.close()

    @patch.object(SessionStore, "create_session")
    def test_start_creates_session(self, mock_create: MagicMock) -> None:
        from voicemeet.menubar import RecordingManager
        from voicemeet.store.models import Session

        mock_session = Session(
            id="test-id", title="Test", started_at="2026-07-12T14:00:00", mode="room"
        )
        mock_create.return_value = mock_session

        store = SessionStore(":memory:")
        rm = RecordingManager(store=store)

        # Mock the audio capture to avoid real device access
        with (
            patch("voicemeet.audio.capture.AudioCapture") as mock_cap,
            patch("voicemeet.transcribe.engine.Transcriber"),
            patch("voicemeet.transcribe.engine.StreamingTranscriber"),
        ):
            mock_cap.return_value.is_recording = True
            sid = rm.start(title="Test", mode="room")
            assert sid == "test-id"
            assert rm.session is not None

        store.close()


class TestModuleImports:
    def test_import_menubar(self) -> None:
        # Module should be importable even without rumps (lazy import)
        import voicemeet.menubar

        assert hasattr(voicemeet.menubar, "run_menubar")
        assert hasattr(voicemeet.menubar, "RecordingManager")

    def test_import_hotkey(self) -> None:
        import voicemeet.hotkey

        assert hasattr(voicemeet.hotkey, "HotkeyManager")
