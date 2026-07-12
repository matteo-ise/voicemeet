"""Tests for auto meeting detection — mocked psutil, process matching."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from voicemeet.detect import (
    DetectedProcess,
    DetectionResult,
    MeetingDetector,
    _match_tier,
    _tier_to_confidence,
    send_notification,
)


class TestTierMatching:
    def test_tier1_zoom(self) -> None:
        assert _match_tier("zoom.us") == "tier1"
        assert _match_tier("ZoomOpener") == "tier1"

    def test_tier1_teams(self) -> None:
        assert _match_tier("Microsoft Teams") == "tier1"
        assert _match_tier("Teams Helper") == "tier1"

    def test_tier2_discord(self) -> None:
        assert _match_tier("Discord") == "tier2"

    def test_tier2_notion(self) -> None:
        assert _match_tier("Notion") == "tier2"

    def test_tier3_chrome(self) -> None:
        assert _match_tier("Google Chrome") == "tier3"
        assert _match_tier("Safari") == "tier3"

    def test_no_match(self) -> None:
        assert _match_tier("TextEdit") is None
        assert _match_tier("Finder") is None

    def test_case_insensitive(self) -> None:
        assert _match_tier("ZOOM.US") == "tier1"
        assert _match_tier("discord") == "tier2"

    def test_tier_to_confidence(self) -> None:
        assert _tier_to_confidence("tier1") == "high"
        assert _tier_to_confidence("tier2") == "medium"
        assert _tier_to_confidence("tier3") == "low"
        assert _tier_to_confidence("unknown") == "none"


class TestScanProcesses:
    @patch("voicemeet.detect.psutil.process_iter")
    def test_scan_finds_meeting_app(self, mock_iter: MagicMock) -> None:
        mock_iter.return_value = [
            MagicMock(info={"pid": 100, "name": "zoom.us"}),
            MagicMock(info={"pid": 101, "name": "TextEdit"}),
            MagicMock(info={"pid": 102, "name": "Microsoft Teams"}),
        ]
        detector = MeetingDetector()
        processes = detector.scan_processes()
        assert len(processes) == 2
        names = [p.name for p in processes]
        assert "zoom.us" in names
        assert "Microsoft Teams" in names

    @patch("voicemeet.detect.psutil.process_iter")
    def test_scan_no_meetings(self, mock_iter: MagicMock) -> None:
        mock_iter.return_value = [
            MagicMock(info={"pid": 100, "name": "Finder"}),
            MagicMock(info={"pid": 101, "name": "TextEdit"}),
        ]
        detector = MeetingDetector()
        processes = detector.scan_processes()
        assert processes == []

    @patch("voicemeet.detect.psutil.process_iter")
    def test_scan_handles_dead_process(self, mock_iter: MagicMock) -> None:
        import psutil

        # Simulate a process that raises AccessDenied during iteration
        bad_proc = MagicMock()
        bad_proc.info = MagicMock()
        bad_proc.info.get = MagicMock(side_effect=psutil.AccessDenied(999))

        mock_iter.return_value = [
            MagicMock(info={"pid": 100, "name": "zoom.us"}),
            bad_proc,
        ]
        detector = MeetingDetector()
        # Should not crash — should skip the bad process
        processes = detector.scan_processes()
        assert isinstance(processes, list)
        assert any(p.name == "zoom.us" for p in processes)

    @patch("voicemeet.detect.psutil.process_iter")
    def test_scan_deduplicates(self, mock_iter: MagicMock) -> None:
        mock_iter.return_value = [
            MagicMock(info={"pid": 100, "name": "zoom.us"}),
            MagicMock(info={"pid": 100, "name": "zoom.us"}),  # Same PID
        ]
        detector = MeetingDetector()
        processes = detector.scan_processes()
        assert len(processes) == 1


class TestDetect:
    @patch.object(MeetingDetector, "scan_processes")
    def test_detect_tier1_no_audio_check(self, mock_scan: MagicMock) -> None:
        mock_scan.return_value = [
            DetectedProcess(name="zoom.us", pid=100, tier="tier1", confidence="high"),
        ]
        detector = MeetingDetector()
        result = detector.detect(check_audio=True)
        assert result.meeting_detected is True
        assert result.confidence == "high"
        assert result.audio_active is True  # Assumed for tier1

    @patch.object(MeetingDetector, "scan_processes")
    @patch.object(MeetingDetector, "check_audio_activity", return_value=False)
    def test_detect_tier2_no_audio(self, mock_audio: MagicMock, mock_scan: MagicMock) -> None:
        mock_scan.return_value = [
            DetectedProcess(name="Discord", pid=200, tier="tier2", confidence="medium"),
        ]
        detector = MeetingDetector()
        result = detector.detect(check_audio=True)
        assert result.meeting_detected is False
        assert result.confidence == "low"

    @patch.object(MeetingDetector, "scan_processes")
    @patch.object(MeetingDetector, "check_audio_activity", return_value=True)
    def test_detect_tier2_with_audio(self, mock_audio: MagicMock, mock_scan: MagicMock) -> None:
        mock_scan.return_value = [
            DetectedProcess(name="Discord", pid=200, tier="tier2", confidence="medium"),
        ]
        detector = MeetingDetector()
        result = detector.detect(check_audio=True)
        assert result.meeting_detected is True
        assert result.confidence == "medium"

    @patch.object(MeetingDetector, "scan_processes")
    def test_detect_no_processes(self, mock_scan: MagicMock) -> None:
        mock_scan.return_value = []
        detector = MeetingDetector()
        result = detector.detect()
        assert result.meeting_detected is False
        assert result.processes == []

    @patch.object(MeetingDetector, "scan_processes")
    @patch.object(MeetingDetector, "check_audio_activity", return_value=False)
    def test_detect_tier3_no_audio(self, mock_audio: MagicMock, mock_scan: MagicMock) -> None:
        mock_scan.return_value = [
            DetectedProcess(name="Google Chrome", pid=300, tier="tier3", confidence="low"),
        ]
        detector = MeetingDetector()
        result = detector.detect(check_audio=True)
        assert result.meeting_detected is False

    @patch.object(MeetingDetector, "scan_processes")
    @patch.object(MeetingDetector, "check_audio_activity", return_value=True)
    def test_detect_tier3_with_audio(self, mock_audio: MagicMock, mock_scan: MagicMock) -> None:
        mock_scan.return_value = [
            DetectedProcess(name="Google Chrome", pid=300, tier="tier3", confidence="low"),
        ]
        detector = MeetingDetector()
        result = detector.detect(check_audio=True)
        assert result.meeting_detected is True
        assert result.confidence == "low"

    @patch.object(MeetingDetector, "scan_processes")
    def test_detect_skip_audio_check(self, mock_scan: MagicMock) -> None:
        mock_scan.return_value = [
            DetectedProcess(name="Discord", pid=200, tier="tier2", confidence="medium"),
        ]
        detector = MeetingDetector()
        result = detector.detect(check_audio=False)
        # Without audio check, tier2 is not confirmed
        assert result.meeting_detected is False


class TestDetectionResult:
    def test_top_process(self) -> None:
        procs = [
            DetectedProcess(name="Chrome", pid=1, tier="tier3", confidence="low"),
            DetectedProcess(name="Zoom", pid=2, tier="tier1", confidence="high"),
            DetectedProcess(name="Discord", pid=3, tier="tier2", confidence="medium"),
        ]
        result = DetectionResult(meeting_detected=True, processes=procs)
        top = result.top_process
        assert top is not None
        assert top.name == "Zoom"

    def test_top_process_empty(self) -> None:
        result = DetectionResult(meeting_detected=False)
        assert result.top_process is None


class TestStartStopWatching:
    @patch.object(MeetingDetector, "detect")
    def test_start_stop_watching(self, mock_detect: MagicMock) -> None:
        mock_detect.return_value = DetectionResult(meeting_detected=False, processes=[])
        detector = MeetingDetector(check_interval_s=1, cooldown_s=0)
        detector.start_watching(on_detected=lambda r: None, check_audio=False)
        assert detector.is_watching is True
        detector.stop_watching()
        assert detector.is_watching is False

    @patch.object(MeetingDetector, "detect")
    def test_watching_triggers_callback(self, mock_detect: MagicMock) -> None:
        mock_detect.return_value = DetectionResult(
            meeting_detected=True,
            processes=[DetectedProcess(name="zoom.us", pid=1, tier="tier1", confidence="high")],
        )

        detector = MeetingDetector(check_interval_s=1, cooldown_s=0)
        detected_results: list[DetectionResult] = []
        detector.start_watching(
            on_detected=detected_results.append,
            check_audio=False,
        )

        import time

        time.sleep(2.5)
        detector.stop_watching()
        assert len(detected_results) >= 1

    @patch.object(MeetingDetector, "detect")
    def test_watching_cooldown(self, mock_detect: MagicMock) -> None:
        mock_detect.return_value = DetectionResult(
            meeting_detected=True,
            processes=[DetectedProcess(name="zoom.us", pid=1, tier="tier1", confidence="high")],
        )

        detector = MeetingDetector(check_interval_s=1, cooldown_s=100)
        detected_count: list[int] = []
        detector.start_watching(
            on_detected=lambda r: detected_count.append(1),
            check_audio=False,
        )

        import time

        time.sleep(3)
        detector.stop_watching()
        # Cooldown should prevent multiple detections
        assert len(detected_count) <= 1


class TestNotification:
    @patch("voicemeet.detect.subprocess.run")
    def test_send_notification(self, mock_run: MagicMock) -> None:
        send_notification("Test Title", "Test message")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "osascript"
        assert "-e" in args

    @patch("voicemeet.detect.subprocess.run", side_effect=Exception("fail"))
    def test_send_notification_fails_silently(self, mock_run: MagicMock) -> None:
        # Should not raise
        send_notification("Test", "Message")

    @patch("voicemeet.detect.subprocess.run")
    def test_notification_escapes_quotes(self, mock_run: MagicMock) -> None:
        send_notification('Title with "quote"', 'Message with "quote"')
        call_args = mock_run.call_args[0][0]
        script = call_args[2]
        assert '\\"' in script
