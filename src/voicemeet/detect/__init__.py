"""Auto meeting detection — process watch + audio VAD confirmation."""

from __future__ import annotations

import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import psutil

# Meeting-related process names (case-insensitive substring match)
# Tier 1: Native meeting apps (high confidence)
TIER1_PROCESSES = [
    "zoom.us",
    "zoomopener",
    "zoom",
    "microsoft teams",
    "teams helper",
    "webex",
    "cisco webex",
    "webexhelper",
    "gotomeeting",
    "g2m",
    "bluejeans",
    "ringcentral",
    "whereby",
]

# Tier 2: Communication apps (medium confidence — may be in call or not)
TIER2_PROCESSES = [
    "discord",
    "slack",
    "notion",
    "signal",
    "whatsapp",
    "facetime",
    "skype",
]

# Tier 3: Browsers (low confidence — need audio confirmation)
TIER3_PROCESSES = [
    "google chrome",
    "safari",
    "firefox",
    "microsoft edge",
    "brave",
    "arc",
]

ALL_MEETING_PROCESSES = TIER1_PROCESSES + TIER2_PROCESSES + TIER3_PROCESSES


@dataclass(slots=True)
class DetectedProcess:
    """A detected meeting-related process."""

    name: str
    pid: int
    tier: str  # "tier1", "tier2", "tier3"
    confidence: str  # "high", "medium", "low"


@dataclass(slots=True)
class DetectionResult:
    """Result of a meeting detection check."""

    meeting_detected: bool
    processes: list[DetectedProcess] = field(default_factory=list)
    audio_active: bool = False
    confidence: str = "none"  # "high", "medium", "low", "none"

    @property
    def top_process(self) -> DetectedProcess | None:
        if not self.processes:
            return None
        # Return highest tier process
        tier_order = {"tier1": 0, "tier2": 1, "tier3": 2}
        return sorted(self.processes, key=lambda p: tier_order.get(p.tier, 3))[0]


def _match_tier(proc_name: str) -> str | None:
    """Match a process name to a tier. Returns tier name or None."""
    name_lower = proc_name.lower()
    for p in TIER1_PROCESSES:
        if p in name_lower:
            return "tier1"
    for p in TIER2_PROCESSES:
        if p in name_lower:
            return "tier2"
    for p in TIER3_PROCESSES:
        if p in name_lower:
            return "tier3"
    return None


def _tier_to_confidence(tier: str) -> str:
    return {"tier1": "high", "tier2": "medium", "tier3": "low"}.get(tier, "none")


class MeetingDetector:
    """Detects active meetings by scanning processes and optionally checking audio.

    Args:
        check_interval_s: How often to scan (seconds).
        audio_check_duration_s: Duration of audio capture for VAD confirmation.
        cooldown_s: Minimum time between detections of the same meeting.
    """

    def __init__(
        self,
        check_interval_s: int = 30,
        audio_check_duration_s: int = 5,
        cooldown_s: int = 300,
    ) -> None:
        self.check_interval_s = check_interval_s
        self.audio_check_duration_s = audio_check_duration_s
        self.cooldown_s = cooldown_s
        self._watching = False
        self._thread: threading.Thread | None = None
        self._last_detection_time: float = 0
        self._last_detection: DetectionResult | None = None

    def scan_processes(self) -> list[DetectedProcess]:
        """Scan running processes for meeting-related apps."""
        detected: list[DetectedProcess] = []
        seen_pids: set[int] = set()

        for proc in psutil.process_iter(attrs=["pid", "name"]):
            try:
                name = proc.info.get("name", "") or ""
                pid = proc.info.get("pid", 0)
                if pid in seen_pids:
                    continue
                tier = _match_tier(name)
                if tier:
                    detected.append(
                        DetectedProcess(
                            name=name,
                            pid=pid,
                            tier=tier,
                            confidence=_tier_to_confidence(tier),
                        )
                    )
                    seen_pids.add(pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return detected

    def check_audio_activity(self, duration_s: int | None = None) -> bool:
        """Capture audio briefly and check for speech via VAD.

        Returns True if sustained speech is detected.
        """
        duration = duration_s or self.audio_check_duration_s
        try:
            from voicemeet.audio.capture import AudioCapture
            from voicemeet.transcribe.vad import VoiceActivityDetector

            cap = AudioCapture()
            cap.start()
            time.sleep(duration)
            audio = cap.stop()

            if len(audio) == 0:
                return False

            vad = VoiceActivityDetector(min_segment_ms=500)
            segments = vad.detect(audio)
            return len(segments) > 0

        except Exception:
            return False

    def detect(self, check_audio: bool = True) -> DetectionResult:
        """Full detection: process scan + optional audio confirmation.

        Args:
            check_audio: If True, verify audio activity for tier2/tier3 detections.
        """
        processes = self.scan_processes()
        if not processes:
            return DetectionResult(meeting_detected=False, processes=[])

        top = self.top_process_by_tier(processes)

        # Tier 1: high confidence, no audio check needed
        if top and top.tier == "tier1":
            return DetectionResult(
                meeting_detected=True,
                processes=processes,
                audio_active=True,  # Assume active for native meeting apps
                confidence="high",
            )

        # Tier 2/3: need audio confirmation
        audio_active = False
        if check_audio:
            audio_active = self.check_audio_activity()

        if top and top.tier == "tier2":
            confidence = "medium" if audio_active else "low"
            return DetectionResult(
                meeting_detected=audio_active,
                processes=processes,
                audio_active=audio_active,
                confidence=confidence,
            )

        if top and top.tier == "tier3":
            # Browsers: only report as meeting if audio is active
            return DetectionResult(
                meeting_detected=audio_active,
                processes=processes,
                audio_active=audio_active,
                confidence="low" if audio_active else "none",
            )

        return DetectionResult(meeting_detected=False, processes=processes)

    def start_watching(
        self,
        on_detected: Callable[[DetectionResult], None],
        check_audio: bool = True,
    ) -> None:
        """Start background monitoring. Calls on_detected when a meeting is found."""
        if self._watching:
            return
        self._watching = True
        self._thread = threading.Thread(
            target=self._watch_loop,
            args=(on_detected, check_audio),
            daemon=True,
        )
        self._thread.start()

    def stop_watching(self) -> None:
        """Stop background monitoring."""
        self._watching = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def _watch_loop(
        self,
        on_detected: Callable[[DetectionResult], None],
        check_audio: bool,
    ) -> None:
        """Background watch loop."""
        while self._watching:
            result = self.detect(check_audio=check_audio)
            now = time.time()
            if result.meeting_detected and now - self._last_detection_time > self.cooldown_s:
                self._last_detection_time = now
                self._last_detection = result
                on_detected(result)
            time.sleep(self.check_interval_s)

    @property
    def is_watching(self) -> bool:
        return self._watching

    @staticmethod
    def top_process_by_tier(processes: list[DetectedProcess]) -> DetectedProcess | None:
        """Return the highest-tier (most confident) process."""
        if not processes:
            return None
        tier_order = {"tier1": 0, "tier2": 1, "tier3": 2}
        return sorted(processes, key=lambda p: tier_order.get(p.tier, 3))[0]


def send_notification(title: str, message: str) -> None:
    """Send a macOS notification via osascript.

    Uses subprocess with a list (no shell=True) — safe, no unsanitised input.
    """
    try:
        safe_title = title.replace('"', '\\"')
        safe_msg = message.replace('"', '\\"')
        script = f'display notification "{safe_msg}" with title "{safe_title}"'
        subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            timeout=5,
        )
    except Exception:
        pass  # Non-critical — notifications are best-effort
