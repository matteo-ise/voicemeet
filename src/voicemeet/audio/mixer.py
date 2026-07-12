"""Audio mixing — combine microphone and system audio with clip prevention."""

from __future__ import annotations

import numpy as np


def mix_audio(mic: np.ndarray, system: np.ndarray) -> np.ndarray:
    """Mix two audio signals with normalization and clip prevention.

    Both inputs should be int16. The output is int16.
    If lengths differ, the shorter one is zero-padded.
    """
    max_len = max(len(mic), len(system))
    if len(mic) < max_len:
        mic = np.pad(mic, (0, max_len - len(mic)))
    if len(system) < max_len:
        system = np.pad(system, (0, max_len - len(system)))

    # Convert to float for safe mixing
    mixed = mic.astype(np.float32) + system.astype(np.float32)

    # Normalize if peaks exceed int16 range
    max_val = float(np.max(np.abs(mixed)))
    if max_val > 32767.0:
        mixed = mixed * (32767.0 / max_val)

    return mixed.astype(np.int16)


def normalize(audio: np.ndarray, target_peak: float = 0.85) -> np.ndarray:
    """Normalize audio to a target peak amplitude (0-1 of int16 range)."""
    if len(audio) == 0:
        return audio
    target = 32767.0 * target_peak
    max_val = float(np.max(np.abs(audio)))
    if max_val == 0:
        return audio
    scale = target / max_val
    return (audio.astype(np.float32) * scale).astype(np.int16)
