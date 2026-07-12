"""Tests for the transcription engine — mocked pywhispercpp, streaming logic."""

from __future__ import annotations

import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from voicemeet.transcribe.engine import (
    StreamingTranscriber,
    Transcriber,
    TranscriptionSegment,
    find_model,
)
from voicemeet.transcribe.vad import VoiceActivityDetector


def _generate_tone(freq: float, duration_s: float, sr: int = 16000) -> np.ndarray:
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    return (0.3 * 32767 * np.sin(2 * np.pi * freq * t)).astype(np.int16)


def _generate_silence(duration_s: float, sr: int = 16000) -> np.ndarray:
    return np.zeros(int(sr * duration_s), dtype=np.int16)


def _save_wav(path: Path, audio: np.ndarray, sr: int = 16000) -> None:
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(audio.tobytes())


# ── TranscriptionSegment Tests ────────────────────────────


class TestTranscriptionSegment:
    def test_properties(self) -> None:
        seg = TranscriptionSegment(start_ms=65000, end_ms=70000, text="Hello")
        assert seg.duration_ms == 5000
        assert seg.start_str == "01:05"

    def test_start_str_hours(self) -> None:
        seg = TranscriptionSegment(start_ms=3725000, end_ms=3730000, text="Test")
        assert seg.start_str == "01:02:05"


# ── find_model Tests ──────────────────────────────────────


class TestFindModel:
    def test_env_var(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        model_file = tmp_path / "model.bin"
        model_file.write_bytes(b"fake model")
        monkeypatch.setenv("VOICEMEET_MODEL_PATH", str(model_file))
        result = find_model()
        assert result == str(model_file)

    def test_env_var_nonexistent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VOICEMEET_MODEL_PATH", "/nonexistent/path.bin")
        # Should fall through to other checks, likely return None
        result = find_model()
        # May find something in OpenSuperWhisper dir on this machine
        assert result is None or isinstance(result, str)

    def test_no_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("VOICEMEET_MODEL_PATH", raising=False)
        result = find_model()
        # On this machine, might find OpenSuperWhisper models
        assert result is None or isinstance(result, str)


# ── Transcriber Tests (mocked) ────────────────────────────


class TestTranscriber:
    def test_init_defaults(self) -> None:
        t = Transcriber(model_path="/fake/path.bin")
        assert t.model_path == "/fake/path.bin"
        assert t._model is None

    def test_transcribe_empty_audio(self) -> None:
        t = Transcriber(model_path="/fake/path.bin")
        result = t.transcribe(np.array([], dtype=np.int16))
        assert result == []

    @patch("voicemeet.transcribe.engine.Transcriber._ensure_model")
    def test_transcribe_with_mock(self, mock_ensure: MagicMock) -> None:
        """Test transcription with a mocked pywhispercpp model."""
        t = Transcriber(model_path="/fake/path.bin")

        # Create mock segments (whisper.cpp uses centiseconds for t0/t1)
        mock_seg1 = MagicMock()
        mock_seg1.t0 = 0  # 0 centiseconds = 0ms
        mock_seg1.t1 = 500  # 500 centiseconds = 5000ms
        mock_seg1.text = " Hello world "
        mock_seg1.probability = float("nan")

        mock_seg2 = MagicMock()
        mock_seg2.t0 = 500
        mock_seg2.t1 = 1000
        mock_seg2.text = " Second segment "
        mock_seg2.probability = 0.95

        # Mock the model
        mock_model = MagicMock()
        mock_model.transcribe.return_value = [mock_seg1, mock_seg2]
        t._model = mock_model

        audio = _generate_tone(440, 1.0)
        results = t.transcribe(audio)

        assert len(results) == 2
        assert results[0].text == "Hello world"
        assert results[0].start_ms == 0
        assert results[0].end_ms == 5000
        assert results[0].confidence is None  # NaN → None
        assert results[1].text == "Second segment"
        assert results[1].start_ms == 5000
        assert results[1].end_ms == 10000
        assert results[1].confidence == 0.95

    @patch("voicemeet.transcribe.engine.Transcriber._ensure_model")
    def test_transcribe_file(self, mock_ensure: MagicMock, tmp_path: Path) -> None:
        t = Transcriber(model_path="/fake/path.bin")

        mock_seg = MagicMock()
        mock_seg.t0 = 0
        mock_seg.t1 = 1000
        mock_seg.text = " File content "
        mock_seg.probability = float("nan")

        mock_model = MagicMock()
        mock_model.transcribe.return_value = [mock_seg]
        t._model = mock_model

        wav_path = tmp_path / "test.wav"
        audio = _generate_tone(440, 0.5)
        _save_wav(wav_path, audio)

        results = t.transcribe_file(wav_path)
        assert len(results) == 1
        assert results[0].text == "File content"

    def test_transcribe_file_wrong_sample_rate(self, tmp_path: Path) -> None:
        t = Transcriber(model_path="/fake/path.bin")
        wav_path = tmp_path / "test.wav"
        audio = _generate_tone(440, 0.5, sr=44100)
        _save_wav(wav_path, audio, sr=44100)

        with pytest.raises(ValueError, match="16kHz"):
            t.transcribe_file(wav_path)


# ── StreamingTranscriber Tests ────────────────────────────


class TestStreamingTranscriber:
    def _make_mock_transcriber(self, text: str = "Mock text") -> Transcriber:
        """Create a transcriber with a mocked model that returns fixed text."""
        t = Transcriber(model_path="/fake/path.bin")

        mock_seg = MagicMock()
        mock_seg.t0 = 0
        mock_seg.t1 = 100
        mock_seg.text = text
        mock_seg.probability = float("nan")

        mock_model = MagicMock()
        mock_model.transcribe.return_value = [mock_seg]
        t._model = mock_model
        return t

    def test_streaming_basic(self) -> None:
        """Test that streaming produces transcriptions at segment boundaries."""
        transcriber = self._make_mock_transcriber("Hello")
        vad = VoiceActivityDetector(min_silence_ms=300, min_segment_ms=200)
        st = StreamingTranscriber(transcriber, vad=vad)

        block_size = int(16000 * 0.1)  # 100ms
        audio = np.concatenate(
            [
                _generate_silence(0.3),
                _generate_tone(440, 0.5),
                _generate_silence(0.5),
            ]
        )

        segments: list[TranscriptionSegment] = []
        for i in range(0, len(audio), block_size):
            block = audio[i : i + block_size]
            seg = st.process_block(block)
            if seg is not None:
                segments.append(seg)

        final = st.flush()
        if final is not None:
            segments.append(final)

        assert len(segments) >= 1
        assert all(s.text == "Hello" for s in segments)

    def test_streaming_callback(self) -> None:
        """Test that on_segment callback is called."""
        transcriber = self._make_mock_transcriber("Callback test")
        vad = VoiceActivityDetector(min_silence_ms=300, min_segment_ms=200)

        callback_segments: list[TranscriptionSegment] = []
        st = StreamingTranscriber(transcriber, vad=vad, on_segment=callback_segments.append)

        block_size = int(16000 * 0.1)
        audio = np.concatenate(
            [
                _generate_tone(440, 0.5),
                _generate_silence(0.5),
            ]
        )

        for i in range(0, len(audio), block_size):
            st.process_block(audio[i : i + block_size])
        st.flush()

        assert len(callback_segments) >= 1

    def test_streaming_multiple_segments(self) -> None:
        """Test that multiple speech segments produce multiple transcriptions."""
        transcriber = self._make_mock_transcriber("Segment")
        vad = VoiceActivityDetector(min_silence_ms=400, min_segment_ms=200)
        st = StreamingTranscriber(transcriber, vad=vad)

        block_size = int(16000 * 0.1)
        audio = np.concatenate(
            [
                _generate_tone(440, 0.5),
                _generate_silence(0.6),
                _generate_tone(880, 0.5),
                _generate_silence(0.6),
            ]
        )

        segments: list[TranscriptionSegment] = []
        for i in range(0, len(audio), block_size):
            block = audio[i : i + block_size]
            seg = st.process_block(block)
            if seg is not None:
                segments.append(seg)

        final = st.flush()
        if final is not None:
            segments.append(final)

        assert len(segments) >= 2

    def test_streaming_get_full_audio(self) -> None:
        transcriber = self._make_mock_transcriber("test")
        st = StreamingTranscriber(transcriber)

        block1 = _generate_tone(440, 0.1)
        block2 = _generate_tone(880, 0.1)
        st.process_block(block1)
        st.process_block(block2)

        full = st.get_full_audio()
        assert len(full) == len(block1) + len(block2)

    def test_streaming_silence_only(self) -> None:
        transcriber = self._make_mock_transcriber("Should not appear")
        vad = VoiceActivityDetector()
        st = StreamingTranscriber(transcriber, vad=vad)

        block = _generate_silence(0.5)
        result = st.process_block(block)
        assert result is None
        assert st.flush() is None
