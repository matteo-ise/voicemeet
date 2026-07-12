"""Tests for speaker diarization — synthetic audio with distinct frequencies."""

from __future__ import annotations

import numpy as np

from voicemeet.transcribe.diarize import SpeakerDiarizer, SpeakerSegment

SAMPLE_RATE = 16000


def _generate_tone(freq: float, duration_s: float, sr: int = SAMPLE_RATE) -> np.ndarray:
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    return (0.3 * 32767 * np.sin(2 * np.pi * freq * t)).astype(np.int16)


def _generate_silence(duration_s: float, sr: int = SAMPLE_RATE) -> np.ndarray:
    return np.zeros(int(sr * duration_s), dtype=np.int16)


def _make_segment(audio: np.ndarray, start_ms: int = 0) -> tuple[int, int, np.ndarray]:
    end_ms = start_ms + int(len(audio) * 1000 / SAMPLE_RATE)
    return (start_ms, end_ms, audio)


class TestFeatureExtraction:
    def test_extract_features_shape(self) -> None:
        d = SpeakerDiarizer()
        audio = _generate_tone(200, 1.0)
        features = d.extract_features(audio)
        assert features.shape == (10,)

    def test_extract_features_silence(self) -> None:
        d = SpeakerDiarizer()
        audio = _generate_silence(1.0)
        features = d.extract_features(audio)
        assert features.shape == (10,)
        # RMS should be ~0 for silence
        assert features[6] < 1.0  # rms_mean

    def test_extract_features_short_audio(self) -> None:
        d = SpeakerDiarizer()
        audio = _generate_tone(200, 0.01)  # Very short
        features = d.extract_features(audio)
        assert features.shape == (10,)

    def test_different_frequencies_different_features(self) -> None:
        d = SpeakerDiarizer()
        low = d.extract_features(_generate_tone(150, 1.0))
        high = d.extract_features(_generate_tone(400, 1.0))
        # Spectral centroid should differ significantly
        assert abs(low[0] - high[0]) > 50  # centroid_mean difference


class TestDiarization:
    def test_empty_segments(self) -> None:
        d = SpeakerDiarizer()
        assert d.diarize([]) == []

    def test_single_segment(self) -> None:
        d = SpeakerDiarizer()
        segs = [_make_segment(_generate_tone(200, 0.5))]
        labels = d.diarize(segs)
        assert labels == ["Speaker 1"]

    def test_two_distinct_speakers(self) -> None:
        """Two distinct frequency tones should cluster into 2 speakers."""
        d = SpeakerDiarizer(n_speakers=2)
        # Alternating low and high frequency segments
        segs = [
            _make_segment(_generate_tone(150, 0.5), start_ms=0),
            _make_segment(_generate_tone(400, 0.5), start_ms=500),
            _make_segment(_generate_tone(150, 0.5), start_ms=1000),
            _make_segment(_generate_tone(400, 0.5), start_ms=1500),
            _make_segment(_generate_tone(150, 0.5), start_ms=2000),
            _make_segment(_generate_tone(400, 0.5), start_ms=2500),
        ]
        labels = d.diarize(segs)
        assert len(labels) == 6
        # Low freq segments should have same label
        low_label = labels[0]
        high_label = labels[1]
        assert low_label != high_label
        assert labels[2] == low_label
        assert labels[3] == high_label
        assert labels[4] == low_label
        assert labels[5] == high_label

    def test_same_speaker_all_segments(self) -> None:
        """Same frequency tone should cluster into 1 speaker (forced to 2)."""
        d = SpeakerDiarizer(n_speakers=2)
        segs = [
            _make_segment(_generate_tone(200, 0.5), start_ms=0),
            _make_segment(_generate_tone(200, 0.5), start_ms=500),
            _make_segment(_generate_tone(200, 0.5), start_ms=1000),
        ]
        labels = d.diarize(segs)
        assert len(labels) == 3
        # With same audio, KMeans may still split — but all should be valid speaker labels
        for label in labels:
            assert label.startswith("Speaker ")

    def test_auto_detect_speakers(self) -> None:
        """Auto-detection should find 2 speakers for 2 distinct voices."""
        d = SpeakerDiarizer(n_speakers=None, min_speakers=2, max_speakers=4)
        segs = [
            _make_segment(_generate_tone(150, 0.5), start_ms=0),
            _make_segment(_generate_tone(400, 0.5), start_ms=500),
            _make_segment(_generate_tone(150, 0.5), start_ms=1000),
            _make_segment(_generate_tone(400, 0.5), start_ms=1500),
        ]
        labels = d.diarize(segs)
        assert len(labels) == 4
        unique = set(labels)
        assert len(unique) == 2

    def test_three_speakers(self) -> None:
        """Three distinct frequency tones with forced n_speakers=3."""
        d = SpeakerDiarizer(n_speakers=3)
        segs = [
            _make_segment(_generate_tone(120, 0.5), start_ms=0),
            _make_segment(_generate_tone(300, 0.5), start_ms=500),
            _make_segment(_generate_tone(600, 0.5), start_ms=1000),
            _make_segment(_generate_tone(120, 0.5), start_ms=1500),
            _make_segment(_generate_tone(600, 0.5), start_ms=2000),
            _make_segment(_generate_tone(300, 0.5), start_ms=2500),
        ]
        labels = d.diarize(segs)
        assert len(labels) == 6
        unique = set(labels)
        assert len(unique) == 3
        # First and fourth should be same speaker
        assert labels[0] == labels[3]
        assert labels[1] == labels[5]
        assert labels[2] == labels[4]

    def test_speaker_labels_ordered_by_appearance(self) -> None:
        """First appearing speaker should be 'Speaker 1'."""
        d = SpeakerDiarizer(n_speakers=2)
        segs = [
            _make_segment(_generate_tone(400, 0.5), start_ms=0),  # High first
            _make_segment(_generate_tone(150, 0.5), start_ms=500),  # Low second
        ]
        labels = d.diarize(segs)
        assert labels[0] == "Speaker 1"
        assert labels[1] == "Speaker 2"

    def test_diarize_segments_returns_objects(self) -> None:
        d = SpeakerDiarizer(n_speakers=2)
        segs = [
            _make_segment(_generate_tone(150, 0.5), start_ms=0),
            _make_segment(_generate_tone(400, 0.5), start_ms=500),
        ]
        result = d.diarize_segments(segs)
        assert len(result) == 2
        assert all(isinstance(s, SpeakerSegment) for s in result)
        assert result[0].start_ms == 0
        assert result[1].start_ms == 500
        assert result[0].speaker.startswith("Speaker ")
        assert result[0].audio is not None

    def test_silence_segments(self) -> None:
        """All-silence segments should not crash."""
        d = SpeakerDiarizer(n_speakers=2)
        segs = [
            _make_segment(_generate_silence(0.5), start_ms=0),
            _make_segment(_generate_silence(0.5), start_ms=500),
        ]
        labels = d.diarize(segs)
        assert len(labels) == 2
