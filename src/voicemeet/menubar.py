"""Menubar daemon app via rumps.

Shows a menubar icon with recording controls, session list, auto-detection,
and global hotkey support (Cmd+Shift+M).

Lazy-imports rumps so the module loads without pyobjc installed.
The app is started via: python -m voicemeet menubar
or directly: python -m voicemeet.menubar
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from voicemeet.detect import DetectionResult, MeetingDetector, send_notification
from voicemeet.hotkey import HotkeyManager
from voicemeet.store.db import SessionStore


class RecordingManager:
    """Manages the recording lifecycle for the menubar app.

    Encapsulates audio capture, transcription, diarization, summary, and export
    into a single start/stop interface.
    """

    def __init__(self, store: SessionStore | None = None) -> None:
        self.store = store or SessionStore()
        self.session = None
        self.capture = None
        self.streaming = None
        self.transcriber = None
        self._segments: list = []
        self._thread: threading.Thread | None = None

    @property
    def is_recording(self) -> bool:
        return self.session is not None and self.capture is not None and self.capture.is_recording

    def start(
        self,
        title: str | None = None,
        mode: str = "room",
        lang: str = "auto",
        on_segment: Callable | None = None,
    ) -> str | None:
        """Start a recording session. Returns session ID or None on failure."""
        try:
            from voicemeet.audio.capture import AudioCapture
            from voicemeet.transcribe.engine import StreamingTranscriber, Transcriber

            self.session = self.store.create_session(title=title, mode=mode)
            self._segments = []

            include_sys = mode in ("online", "auto")
            self.capture = AudioCapture(include_system_audio=include_sys)
            self.transcriber = Transcriber(language=lang if lang != "auto" else None)

            def _on_seg(seg) -> None:
                self._segments.append(seg)
                if on_segment:
                    on_segment(seg)

            self.streaming = StreamingTranscriber(self.transcriber, on_segment=_on_seg)
            self.capture.start(on_block=self.streaming.process_block)
            return self.session.id

        except Exception:
            return None

    def stop(self) -> str | None:
        """Stop recording, finalize session, run summary and export. Returns session ID."""
        if self.session is None:
            return None

        try:
            if self.capture:
                self.capture.stop()
            if self.streaming:
                final = self.streaming.flush()
                if final:
                    self._segments.append(final)
        except Exception:
            pass

        # Save segments
        for i, seg in enumerate(self._segments):
            self.store.add_segment(
                session_id=self.session.id,
                idx=i,
                start_ms=seg.start_ms,
                end_ms=seg.end_ms,
                text=seg.text,
                confidence=seg.confidence,
            )

        # Diarization (room mode)
        segments = self.store.get_segments(self.session.id)
        if self.session.mode == "room" and len(segments) > 1 and self.streaming:
            try:
                from voicemeet.transcribe.diarize import SpeakerDiarizer

                diarizer = SpeakerDiarizer()
                full_audio = self.streaming.get_full_audio()
                seg_tuples = []
                for s in segments:
                    sr = 16000
                    start = s.start_ms * sr // 1000
                    end = s.end_ms * sr // 1000
                    seg_tuples.append((s.start_ms, s.end_ms, full_audio[start:end]))
                labels = diarizer.diarize(seg_tuples)
                for s, label in zip(segments, labels, strict=False):
                    self.store.update_segment_speaker(s.id, label)
                segments = self.store.get_segments(self.session.id)
            except Exception:
                pass

        # Summary
        from voicemeet.summarize.ollama_summarizer import OllamaSummarizer, SummaryResult

        summarizer = OllamaSummarizer()
        summary = SummaryResult()
        if summarizer.check_connection():
            try:
                summary = summarizer.summarize(self.session, segments)
            except Exception:
                pass

        # Finalize
        self.store.finalize_session(
            self.session.id,
            participants=summary.participants,
            topics=summary.topics,
            summary_markdown=summary.summary_markdown,
        )

        # Auto-export MD
        try:
            from voicemeet.export.markdown import export_markdown

            session = self.store.get_session(self.session.id)
            if session:
                path = export_markdown(session, summary, segments)
                self.store.add_export(session.id, "md", path)
        except Exception:
            pass

        sid = self.session.id
        self.session = None
        self.capture = None
        self.streaming = None
        self.transcriber = None
        self._segments = []
        return sid


def run_menubar() -> None:
    """Start the menubar daemon app."""
    try:
        import rumps
    except ImportError as e:
        raise ImportError(
            "rumps is required for the menubar app. Install with: pip install rumps"
        ) from e

    store = SessionStore()
    recorder = RecordingManager(store=store)
    detector = MeetingDetector(check_interval_s=60, cooldown_s=600)
    auto_detect_on = False

    class VoicemeetApp(rumps.App):
        def __init__(self) -> None:
            super().__init__(
                name="voicemeet",
                title="VM",
                icon=None,
                menu=[
                    "New Meeting",
                    "Start Recording",
                    None,
                    "Recent Meetings",
                    None,
                    "Export Last as PDF",
                    None,
                    "Auto-Detect",
                    None,
                    "Quit",
                ],
            )
            self._hotkey: HotkeyManager | None = None

        def startup(self) -> None:
            self._setup_hotkey()

        def _setup_hotkey(self) -> None:
            try:
                self._hotkey = HotkeyManager(callback=self._toggle_recording)
                self._hotkey.start()
            except ImportError:
                rumps.notification(
                    "voicemeet",
                    "Hotkey unavailable",
                    "Install pynput for Cmd+Shift+M support",
                )

        def _toggle_recording(self) -> None:
            if recorder.is_recording:
                self._stop_recording()
            else:
                self._start_recording()

        def _start_recording(self) -> None:
            sid = recorder.start(mode="room")
            if sid:
                self.title = "VM ●"
                rumps.notification("voicemeet", "Recording started", "Press Cmd+Shift+M to stop")
            else:
                rumps.notification("voicemeet", "Error", "Could not start recording")

        def _stop_recording(self) -> None:
            sid = recorder.stop()
            self.title = "VM"
            if sid:
                rumps.notification("voicemeet", "Recording complete", "Summary and export saved")
            else:
                rumps.notification("voicemeet", "Error", "Could not finalize recording")

        @rumps.clicked("New Meeting")
        def new_meeting(self, _item) -> None:
            self._start_recording()

        @rumps.clicked("Start Recording")
        def toggle_recording(self, _item) -> None:
            self._toggle_recording()

        @rumps.clicked("Export Last as PDF")
        def export_last_pdf(self, _item) -> None:
            sessions = store.list_sessions(limit=1)
            if not sessions:
                rumps.notification("voicemeet", "No sessions", "Record a meeting first")
                return
            sess = sessions[0]
            segments = store.get_segments(sess.id)
            try:
                from voicemeet.export.pdf import export_pdf
                from voicemeet.summarize.ollama_summarizer import SummaryResult

                summary = SummaryResult(
                    title=sess.title or "",
                    participants=sess.participants,
                    topics=sess.topics,
                    summary_markdown=sess.summary_markdown or "",
                )
                path = export_pdf(sess, summary, segments)
                store.add_export(sess.id, "pdf", path)
                rumps.notification("voicemeet", "PDF exported", path)
            except Exception as e:
                rumps.notification("voicemeet", "Export failed", str(e))

        @rumps.clicked("Auto-Detect")
        def toggle_auto_detect(self, sender) -> None:
            nonlocal auto_detect_on
            auto_detect_on = not auto_detect_on
            sender.state = auto_detect_on

            if auto_detect_on:

                def on_detected(result: DetectionResult) -> None:
                    proc = result.top_process
                    name = proc.name if proc else "Unknown"
                    send_notification(
                        "voicemeet — Meeting detected",
                        f"{name} is running. Start recording?",
                    )

                detector.start_watching(on_detected=on_detected, check_audio=True)
                rumps.notification("voicemeet", "Auto-detect enabled", "Watching for meetings")
            else:
                detector.stop_watching()
                rumps.notification("voicemeet", "Auto-detect disabled", "")

        @rumps.clicked("Recent Meetings")
        def recent_meetings(self, _item) -> None:
            sessions = store.list_sessions(limit=5)
            if not sessions:
                rumps.notification("voicemeet", "No sessions", "Record a meeting first")
                return
            for s in sessions:
                dt = s.started_dt.strftime("%d.%m.%Y %H:%M")
                label = f"{s.title or 'Untitled'} — {dt}"
                rumps.notification("voicemeet", "Recent", label)

        @rumps.clicked("Quit")
        def quit_app(self, _item) -> None:
            if recorder.is_recording:
                recorder.stop()
            if auto_detect_on:
                detector.stop_watching()
            if self._hotkey:
                self._hotkey.stop()
            rumps.quit_application()

    app = VoicemeetApp()
    app.run()


if __name__ == "__main__":
    run_menubar()
