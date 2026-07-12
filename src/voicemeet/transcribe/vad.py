"""Energy-based Voice Activity Detection.

Detects speech segments in audio by computing RMS energy per frame.
Silence longer than min_silence_ms triggers a segment boundary.

Works in both batch mode (full audio array) and streaming mode (block-by-block).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

DEFAULT_SAMPLE_RATE = 16000
DEFAULT_FRAME_MS = 30  # 30ms frames — standard VAD frame size
DEFAULT_ENERGY_THRESHOLD = 300.0  # RMS threshold for int16 audio
DEFAULT_MIN_SILENCE_MS = 700  # Pause duration to trigger segment boundary
DEFAULT_MIN_SEGMENT_MS = 300  # Discard segments shorter than this
DEFAULT_PADDING_MS = 300  # Pad segments with this much silence at start/end


@dataclass(slots=True)
class VADSegment:
    """A detected speech segment."""

    start_ms: int
    end_ms: int
    audio: np.ndarray | None = None  # Set in batch mode, None in streaming

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


class VoiceActivityDetector:
    """Energy-based VAD for speech segment detection.

    Args:
        sample_rate: Audio sample rate.
        frame_ms: Frame duration in ms.
        energy_threshold: RMS energy threshold (int16 scale, 0-32767).
        min_silence_ms: Silence duration to split segments.
        min_segment_ms: Minimum segment duration to keep.
        padding_ms: Padding around detected speech.
    """

    def __init__(
        self,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        frame_ms: int = DEFAULT_FRAME_MS,
        energy_threshold: float = DEFAULT_ENERGY_THRESHOLD,
        min_silence_ms: int = DEFAULT_MIN_SILENCE_MS,
        min_segment_ms: int = DEFAULT_MIN_SEGMENT_MS,
        padding_ms: int = DEFAULT_PADDING_MS,
    ) -> None:
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self.energy_threshold = energy_threshold
        self.min_silence_ms = min_silence_ms
        self.min_segment_ms = min_segment_ms
        self.padding_ms = padding_ms

        self.frame_samples = int(sample_rate * frame_ms / 1000)
        self.silence_frames_needed = max(1, int(min_silence_ms / frame_ms))

        # Streaming state
        self._current_speech_start: int | None = None
        self._silence_count = 0
        self._total_samples = 0
        self._segments: list[VADSegment] = []

    def _frame_energy(self, frame: np.ndarray) -> float:
        """Compute RMS energy of a frame."""
        if len(frame) == 0:
            return 0.0
        return float(np.sqrt(np.mean(frame.astype(np.float64) ** 2)))

    def detect(self, audio: np.ndarray) -> list[VADSegment]:
        """Batch mode: detect all speech segments in a complete audio buffer."""
        if len(audio) == 0:
            return []

        segments: list[tuple[int, int]] = []
        in_speech = False
        speech_start = 0
        silence_count = 0

        for i in range(0, len(audio), self.frame_samples):
            frame = audio[i : i + self.frame_samples]
            energy = self._frame_energy(frame)
            is_voice = energy > self.energy_threshold

            if is_voice:
                if not in_speech:
                    in_speech = True
                    speech_start = max(0, i - self.padding_samples)
                silence_count = 0
            else:
                if in_speech:
                    silence_count += 1
                    if silence_count >= self.silence_frames_needed:
                        end = min(len(audio), i + self.frame_samples)
                        segments.append((speech_start, end))
                        in_speech = False
                        silence_count = 0

        # Don't forget ongoing speech at end
        if in_speech:
            segments.append((speech_start, len(audio)))

        # Filter short segments and build VADSegment objects with audio
        min_samples = int(self.sample_rate * self.min_segment_ms / 1000)
        result: list[VADSegment] = []
        for start, end in segments:
            if end - start >= min_samples:
                result.append(
                    VADSegment(
                        start_ms=int(start * 1000 / self.sample_rate),
                        end_ms=int(end * 1000 / self.sample_rate),
                        audio=audio[start:end],
                    )
                )
        return result

    @property
    def padding_samples(self) -> int:
        return int(self.sample_rate * self.padding_ms / 1000)

    def process_block(self, block: np.ndarray) -> tuple[bool, VADSegment | None]:
        """Streaming mode: process one block of audio.

        Returns (is_voice, completed_segment). completed_segment is non-None
        when a segment boundary is detected (silence after speech).
        """
        completed: VADSegment | None = None

        for i in range(0, len(block), self.frame_samples):
            frame = block[i : i + self.frame_samples]
            energy = self._frame_energy(frame)
            is_voice = energy > self.energy_threshold
            frame_ms = self._total_samples * 1000 // self.sample_rate

            if is_voice:
                if self._current_speech_start is None:
                    start_sample = max(0, self._total_samples - self.padding_samples)
                    self._current_speech_start = start_sample * 1000 // self.sample_rate
                self._silence_count = 0
            else:
                if self._current_speech_start is not None:
                    self._silence_count += 1
                    if self._silence_count >= self.silence_frames_needed:
                        end_ms = frame_ms
                        duration = end_ms - self._current_speech_start
                        if duration >= self.min_segment_ms:
                            completed = VADSegment(
                                start_ms=self._current_speech_start,
                                end_ms=end_ms,
                            )
                        self._current_speech_start = None
                        self._silence_count = 0

            self._total_samples += len(frame)

        return (self._current_speech_start is not None, completed)

    def flush(self) -> VADSegment | None:
        """Call after streaming ends to get the final in-progress segment."""
        if self._current_speech_start is not None:
            end_ms = self._total_samples * 1000 // self.sample_rate
            duration = end_ms - self._current_speech_start
            self._current_speech_start = None
            self._silence_count = 0
            if duration >= self.min_segment_ms:
                return VADSegment(start_ms=self._current_speech_start or end_ms, end_ms=end_ms)
        return None

    def reset(self) -> None:
        """Reset streaming state for a new session."""
        self._current_speech_start = None
        self._silence_count = 0
        self._total_samples = 0
        self._segments = []
