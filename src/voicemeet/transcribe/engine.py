"""Whisper transcription engine using pywhispercpp.

Loads ggml .bin models (e.g. large-v3-turbo from OpenSuperWhisper).
Lazy-imports pywhispercpp so the module loads even without the binding.
"""

from __future__ import annotations

import os
import wave
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from voicemeet.transcribe.vad import VoiceActivityDetector

# Model search locations (checked in order)
_OPENSW_MODELS = (
    Path.home() / "Library/Application Support/ru.starmel.OpenSuperWhisper/whisper-models"
)
_VOICEMEET_MODELS = Path.home() / ".voicemeet" / "models"
_DEFAULT_MODEL_NAME = "ggml-large-v3-turbo-q5_0.bin"


@dataclass(slots=True)
class TranscriptionSegment:
    """A single transcribed segment with timing."""

    start_ms: int
    end_ms: int
    text: str
    confidence: float | None = None

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    @property
    def start_str(self) -> str:
        total = self.start_ms // 1000
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"


def find_model() -> str | None:
    """Find a whisper model file. Returns path or None.

    Search order:
      1. VOICEMEET_MODEL_PATH env var
      2. ~/.voicemeet/models/*.bin
      3. OpenSuperWhisper models directory (convenience for existing users)
    """
    env_path = os.environ.get("VOICEMEET_MODEL_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    if _VOICEMEET_MODELS.exists():
        bins = sorted(_VOICEMEET_MODELS.glob("*.bin"))
        if bins:
            return str(bins[0])

    if _OPENSW_MODELS.exists():
        bins = sorted(_OPENSW_MODELS.glob("*.bin"))
        # Prefer q5_0 (good speed/quality balance)
        for b in bins:
            if "q5_0" in b.name:
                return str(b)
        if bins:
            return str(bins[0])

    return None


class Transcriber:
    """Whisper transcription engine backed by pywhispercpp.

    Args:
        model_path: Path to ggml .bin model file. If None, auto-detects.
        language: Language code (e.g. "de", "en") or None for auto-detect.
        n_threads: Number of CPU threads. None = auto.
    """

    def __init__(
        self,
        model_path: str | None = None,
        language: str | None = None,
        n_threads: int | None = None,
    ) -> None:
        self.model_path = model_path or find_model()
        self.language = language
        self.n_threads = n_threads or os.cpu_count() or 4
        self._model = None

    def _ensure_model(self) -> None:
        """Lazy-load the whisper model."""
        if self._model is not None:
            return
        try:
            from pywhispercpp.model import Model
        except ImportError as e:
            raise ImportError(
                "pywhispercpp is required for transcription. Install with: pip install pywhispercpp"
            ) from e

        model_path = self.model_path or _DEFAULT_MODEL_NAME
        params: dict = {"n_threads": self.n_threads}
        if self.language and self.language != "auto":
            params["language"] = self.language
        params["no_context"] = True
        params["translate"] = False

        self._model = Model(model=str(model_path), **params)

    def transcribe(self, audio: np.ndarray) -> list[TranscriptionSegment]:
        """Transcribe an audio buffer. Returns list of segments.

        Args:
            audio: int16 numpy array at 16kHz mono.
        """
        self._ensure_model()
        assert self._model is not None

        if len(audio) == 0:
            return []

        # pywhispercpp expects float32 normalized [-1, 1] or int16
        segments = self._model.transcribe(audio)
        return [
            TranscriptionSegment(
                start_ms=s.t0 * 10,  # whisper.cpp uses centiseconds
                end_ms=s.t1 * 10,
                text=s.text.strip(),
                confidence=getattr(s, "probability", None)
                if not _is_nan(getattr(s, "probability", None))
                else None,
            )
            for s in segments
        ]

    def transcribe_file(self, file_path: str | Path) -> list[TranscriptionSegment]:
        """Load a WAV file and transcribe it."""
        file_path = Path(file_path)
        with wave.open(str(file_path), "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            frames = wf.readframes(wf.getnframes())

        if sampwidth != 2:
            raise ValueError(f"Only 16-bit WAV supported, got {sampwidth * 8}-bit")
        if framerate != 16000:
            raise ValueError(f"Only 16kHz WAV supported, got {framerate}Hz")

        audio = np.frombuffer(frames, dtype=np.int16)
        if n_channels > 1:
            audio = audio[::n_channels]  # Downmix to mono by taking every nth sample
        return self.transcribe(audio)


def _is_nan(val: object) -> bool:
    try:
        import math

        return math.isnan(float(val))
    except (TypeError, ValueError):
        return False


class StreamingTranscriber:
    """Combines VAD + Transcriber for streaming transcription.

    Feed audio blocks via process_block(). When VAD detects a segment boundary,
    the segment is transcribed and returned (and on_segment callback is called).
    """

    def __init__(
        self,
        transcriber: Transcriber,
        vad: VoiceActivityDetector | None = None,
        on_segment: Callable[[TranscriptionSegment], None] | None = None,
    ) -> None:
        self.transcriber = transcriber
        from voicemeet.transcribe.vad import VoiceActivityDetector

        self.vad = vad or VoiceActivityDetector()
        self.on_segment = on_segment
        self._audio_buffer: list[np.ndarray] = []
        self._segment_idx = 0

    def process_block(self, block: np.ndarray) -> TranscriptionSegment | None:
        """Process an audio block. Returns a transcription if a segment completed."""
        self._audio_buffer.append(block)
        _is_voice, completed = self.vad.process_block(block)

        if completed is not None:
            return self._transcribe_vad_segment(completed)
        return None

    def flush(self) -> TranscriptionSegment | None:
        """Transcribe any remaining audio after streaming ends."""
        final = self.vad.flush()
        if final is not None:
            return self._transcribe_vad_segment(final)
        return None

    def _transcribe_vad_segment(self, vad_seg: object) -> TranscriptionSegment:
        """Extract audio for a VAD segment and transcribe it."""
        full_audio = (
            np.concatenate(self._audio_buffer)
            if self._audio_buffer
            else np.array([], dtype=np.int16)
        )
        sr = self.vad.sample_rate
        start_sample = vad_seg.start_ms * sr // 1000
        end_sample = vad_seg.end_ms * sr // 1000
        segment_audio = full_audio[start_sample:end_sample]

        if len(segment_audio) == 0:
            return TranscriptionSegment(
                start_ms=vad_seg.start_ms,
                end_ms=vad_seg.end_ms,
                text="",
            )

        results = self.transcriber.transcribe(segment_audio)
        combined_text = " ".join(r.text for r in results).strip()

        seg = TranscriptionSegment(
            start_ms=vad_seg.start_ms,
            end_ms=vad_seg.end_ms,
            text=combined_text,
            confidence=results[0].confidence if results else None,
        )

        if self.on_segment:
            self.on_segment(seg)
        self._segment_idx += 1
        return seg

    def get_full_audio(self) -> np.ndarray:
        """Return the complete accumulated audio buffer."""
        if not self._audio_buffer:
            return np.array([], dtype=np.int16)
        return np.concatenate(self._audio_buffer)
