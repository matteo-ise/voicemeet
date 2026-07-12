"""Microphone and system-audio capture via sounddevice.

Lazy-imports sounddevice so the module loads even without PortAudio.
All audio is 16 kHz mono int16 (Whisper convention).
"""

from __future__ import annotations

import wave
from collections.abc import Callable
from pathlib import Path

import numpy as np

# Default audio format: 16kHz mono int16 — Whisper convention
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHANNELS = 1
DEFAULT_DTYPE = np.int16
DEFAULT_BLOCK_MS = 100  # 100ms blocks → 1600 samples at 16kHz

OnBlock = Callable[[np.ndarray], None]


def _find_blackhole_device() -> int | None:
    """Auto-detect BlackHole virtual audio device index."""
    try:
        import sounddevice as sd
    except (ImportError, OSError):
        return None

    for i, dev in enumerate(sd.query_devices()):
        name = dev.get("name", "")
        if "BlackHole" in name and dev.get("max_input_channels", 0) >= 2:
            return i
    return None


def list_input_devices() -> list[dict]:
    """List available audio input devices."""
    try:
        import sounddevice as sd
    except (ImportError, OSError):
        return []
    return [
        {"index": i, "name": d["name"], "channels": d["max_input_channels"]}
        for i, d in enumerate(sd.query_devices())
        if d["max_input_channels"] > 0
    ]


class AudioCapture:
    """Captures microphone audio, optionally mixed with system audio via BlackHole.

    Args:
        sample_rate: Target sample rate (default 16000 for Whisper).
        channels: Audio channels (default 1 = mono).
        block_ms: Block duration in milliseconds for callback.
        include_system_audio: If True, try to capture system audio via BlackHole.
        mic_device: Device index for microphone (None = default).
        system_device: Device index for system audio (None = auto-detect BlackHole).
    """

    def __init__(
        self,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        channels: int = DEFAULT_CHANNELS,
        block_ms: int = DEFAULT_BLOCK_MS,
        include_system_audio: bool = False,
        mic_device: int | None = None,
        system_device: int | None = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.block_ms = block_ms
        self.include_system_audio = include_system_audio
        self.mic_device = mic_device
        self.system_device = system_device

        self._blocks: list[np.ndarray] = []
        self._on_block: OnBlock | None = None
        self._mic_stream = None
        self._sys_stream = None
        self._sys_block: np.ndarray | None = None
        self._recording = False

        # Resolve system audio device
        if include_system_audio and system_device is None:
            self.system_device = _find_blackhole_device()
            if self.system_device is None:
                import warnings

                warnings.warn(
                    "BlackHole not found — falling back to microphone-only. "
                    "Install with: brew install blackhole-2ch",
                    stacklevel=2,
                )
                self.include_system_audio = False

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def block_samples(self) -> int:
        return int(self.sample_rate * self.block_ms / 1000)

    def start(self, on_block: OnBlock | None = None) -> None:
        """Start capturing audio. Calls on_block(np.ndarray) for each block."""
        try:
            import sounddevice as sd
        except ImportError as e:
            raise ImportError(
                "sounddevice is required for audio capture. Install with: pip install sounddevice"
            ) from e

        self._on_block = on_block
        self._blocks = []
        self._recording = True
        block_size = self.block_samples

        def _mic_callback(indata: np.ndarray, frames: int, time, status) -> None:
            if status:
                pass
            block = indata.copy().reshape(-1).astype(np.int16)
            if self.include_system_audio and self._sys_block is not None:
                from voicemeet.audio.mixer import mix_audio

                block = mix_audio(block, self._sys_block[: len(block)])
            self._blocks.append(block)
            if self._on_block:
                self._on_block(block)

        self._mic_stream = sd.InputStream(
            device=self.mic_device,
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="int16",
            blocksize=block_size,
            callback=_mic_callback,
        )
        self._mic_stream.start()

        if self.include_system_audio and self.system_device is not None:

            def _sys_callback(indata: np.ndarray, frames: int, time, status) -> None:
                self._sys_block = indata.copy().reshape(-1).astype(np.int16)

            self._sys_stream = sd.InputStream(
                device=self.system_device,
                samplerate=self.sample_rate,
                channels=2,
                dtype="int16",
                blocksize=block_size,
                callback=_sys_callback,
            )
            self._sys_stream.start()

    def stop(self) -> np.ndarray:
        """Stop capturing and return the full audio buffer."""
        if self._mic_stream:
            self._mic_stream.stop()
            self._mic_stream.close()
            self._mic_stream = None
        if self._sys_stream:
            self._sys_stream.stop()
            self._sys_stream.close()
            self._sys_stream = None
        self._recording = False
        if not self._blocks:
            return np.array([], dtype=np.int16)
        return np.concatenate(self._blocks)

    def get_audio(self) -> np.ndarray:
        """Return current audio buffer without stopping."""
        if not self._blocks:
            return np.array([], dtype=np.int16)
        return np.concatenate(self._blocks)

    def save_wav(self, path: str | Path, audio: np.ndarray | None = None) -> str:
        """Save audio buffer to a WAV file. Returns the path."""
        if audio is None:
            audio = self.get_audio()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # int16 = 2 bytes
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio.tobytes())
        return str(path)
