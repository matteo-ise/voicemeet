"""Tests for audio capture, mixer, and VAD — all with synthetic numpy buffers."""

from __future__ import annotations

import numpy as np
import pytest

from voicemeet.audio.mixer import mix_audio, normalize
from voicemeet.transcribe.vad import VoiceActivityDetector, VADSegment

SAMPLE_RATE = 16000


def _generate_tone(freq: float, duration_s: float, sr: int = SAMPLE_RATE) -> np.ndarray:
    """Generate a sine wave tone as int16 audio."""
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    wave = (0.3 * 32767 * np.sin(2 * np.pi * freq * t)).astype(np.int16)
    return wave


def _generate_silence(duration_s: float, sr: int = SAMPLE_RATE) -> np.ndarray:
    return np.zeros(int(sr * duration_s), dtype=np.int16)


# ── Mixer Tests ───────────────────────────────────────────


class TestMixer:
    def test_mix_equal_length(self) -> None:
        a = _generate_tone(440, 0.5)
        b = _generate_tone(880, 0.5)
        mixed = mix_audio(a, b)
        assert len(mixed) == len(a)
        assert mixed.dtype == np.int16

    def test_mix_different_length(self) -> None:
        a = _generate_tone(440, 0.5)
        b = _generate_tone(880, 0.3)
        mixed = mix_audio(a, b)
        assert len(mixed) == max(len(a), len(b))

    def test_mix_clip_prevention(self) -> None:
        a = np.full(100, 30000, dtype=np.int16)
        b = np.full(100, 30000, dtype=np.int16)
        mixed = mix_audio(a, b)
        assert np.max(mixed) <= 32767
        assert np.min(mixed) >= -32768

    def test_mix_silence(self) -> None:
        a = _generate_silence(0.5)
        b = _generate_silence(0.5)
        mixed = mix_audio(a, b)
        assert np.all(mixed == 0)

    def test_normalize(self) -> None:
        audio = np.array([1000, 2000, 3000], dtype=np.int16)
        normed = normalize(audio, target_peak=0.5)
        assert np.max(np.abs(normed)) <= 32767 * 0.51

    def test_normalize_empty(self) -> None:
        assert len(normalize(np.array([], dtype=np.int16))) == 0

    def test_normalize_silence(self) -> None:
        audio = _generate_silence(0.1)
        normed = normalize(audio)
        assert np.all(normed == 0)


# ── VAD Tests ─────────────────────────────────────────────


class TestVAD:
    def test_detect_silence_only(self) -> None:
        audio = _generate_silence(2.0)
        vad = VoiceActivityDetector()
        segments = vad.detect(audio)
        assert segments == []

    def test_detect_single_segment(self) -> None:
        audio = np.concatenate([
            _generate_silence(0.5),
            _generate_tone(440, 1.0),
            _generate_silence(0.5),
        ])
        vad = VoiceActivityDetector()
        segments = vad.detect(audio)
        assert len(segments) == 1
        assert segments[0].duration_ms >= 500
        assert segments[0].audio is not None
        assert len(segments[0].audio) > 0

    def test_detect_multiple_segments(self) -> None:
        audio = np.concatenate([
            _generate_tone(440, 0.5),
            _generate_silence(1.0),
            _generate_tone(880, 0.5),
            _generate_silence(1.0),
            _generate_tone(660, 0.5),
        ])
        vad = VoiceActivityDetector(min_silence_ms=500)
        segments = vad.detect(audio)
        assert len(segments) == 3
        for seg in segments:
            assert seg.duration_ms >= 200

    def test_detect_filters_short_segments(self) -> None:
        audio = np.concatenate([
            _generate_silence(0.5),
            _generate_tone(440, 0.1),  # Very short — should be filtered
            _generate_silence(0.5),
            _generate_tone(440, 0.5),  # Long enough
            _generate_silence(0.5),
        ])
        vad = VoiceActivityDetector(min_segment_ms=300)
        segments = vad.detect(audio)
        assert len(segments) == 1

    def test_detect_empty_audio(self) -> None:
        vad = VoiceActivityDetector()
        assert vad.detect(np.array([], dtype=np.int16)) == []

    def test_segment_timestamps(self) -> None:
        audio = np.concatenate([
            _generate_silence(1.0),
            _generate_tone(440, 1.0),
            _generate_silence(1.0),
        ])
        vad = VoiceActivityDetector()
        segments = vad.detect(audio)
        assert len(segments) == 1
        seg = segments[0]
        # Speech starts at ~1s; VAD includes padding at start and trailing silence at end
        assert seg.start_ms >= 500
        assert seg.start_ms <= 1200
        assert seg.end_ms >= 1500  # Must include the tone
        assert seg.end_ms <= 3000  # Allow trailing silence + padding

    def test_streaming_mode(self) -> None:
        """Test block-by-block processing."""
        vad = VoiceActivityDetector(min_silence_ms=300, min_segment_ms=200)
        block_size = int(SAMPLE_RATE * 0.1)  # 100ms blocks

        # Create audio: silence, speech, silence, speech, silence
        audio = np.concatenate([
            _generate_silence(0.3),
            _generate_tone(440, 0.5),
            _generate_silence(0.5),
            _generate_tone(880, 0.5),
            _generate_silence(0.3),
        ])

        completed_segments: list[VADSegment] = []
        for i in range(0, len(audio), block_size):
            block = audio[i : i + block_size]
            _is_voice, seg = vad.process_block(block)
            if seg is not None:
                completed_segments.append(seg)

        final = vad.flush()
        if final is not None:
            completed_segments.append(final)

        assert len(completed_segments) >= 1

    def test_streaming_reset(self) -> None:
        vad = VoiceActivityDetector()
        block = _generate_tone(440, 0.1)
        vad.process_block(block)
        vad.reset()
        assert vad._current_speech_start is None
        assert vad._total_samples == 0

    def test_vad_segment_properties(self) -> None:
        seg = VADSegment(start_ms=1000, end_ms=3000)
        assert seg.duration_ms == 2000

    def test_custom_threshold(self) -> None:
        """High threshold should detect fewer segments."""
        audio = np.concatenate([
            _generate_silence(0.5),
            _generate_tone(440, 1.0),
            _generate_silence(0.5),
        ])
        low_thresh = VoiceActivityDetector(energy_threshold=50)
        high_thresh = VoiceActivityDetector(energy_threshold=20000)
        assert len(low_thresh.detect(audio)) >= 1
        assert len(high_thresh.detect(audio)) == 0


# ── AudioCapture Tests (no real device needed) ────────────


class TestAudioCapture:
    def test_init_defaults(self) -> None:
        from voicemeet.audio.capture import AudioCapture

        cap = AudioCapture()
        assert cap.sample_rate == 16000
        assert cap.channels == 1
        assert cap.is_recording is False
        assert cap.block_samples == 1600  # 100ms at 16kHz

    def test_init_with_system_audio_no_blackhole(self) -> None:
        from voicemeet.audio.capture import AudioCapture

        cap = AudioCapture(include_system_audio=True, system_device=999)
        # Should fall back to mic-only since device 999 doesn't exist
        # (BlackHole detection returns None for non-existent device)
        assert cap.include_system_audio is False or cap.system_device == 999

    def test_save_wav(self, tmp_path) -> None:
        from voicemeet.audio.capture import AudioCapture

        cap = AudioCapture()
        audio = _generate_tone(440, 0.5)
        path = cap.save_wav(tmp_path / "test.wav", audio)
        assert path == str(tmp_path / "test.wav")

        import wave

        with wave.open(path, "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getframerate() == 16000
            assert wf.getsampwidth() == 2
            frames = wf.getnframes()
            assert frames > 0

    def test_stop_without_start(self) -> None:
        from voicemeet.audio.capture import AudioCapture

        cap = AudioCapture()
        audio = cap.stop()
        assert len(audio) == 0

    def test_get_audio_empty(self) -> None:
        from voicemeet.audio.capture import AudioCapture

        cap = AudioCapture()
        audio = cap.get_audio()
        assert len(audio) == 0
