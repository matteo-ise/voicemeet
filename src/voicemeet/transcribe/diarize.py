"""Speaker diarization via spectral feature extraction + KMeans clustering.

No external models, no API keys, no downloads. Pure scipy + scikit-learn.
Extracts spectral features per VAD segment, clusters by voice similarity,
assigns "Speaker 1", "Speaker 2", etc. labels.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import find_peaks
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

DEFAULT_SAMPLE_RATE = 16000
DEFAULT_FRAME_MS = 30
DEFAULT_N_SPEAKERS = None  # None = auto-detect
DEFAULT_MAX_SPEAKERS = 6
DEFAULT_MIN_SPEAKERS = 2


@dataclass(slots=True)
class SpeakerSegment:
    """A segment labeled with a speaker."""

    start_ms: int
    end_ms: int
    speaker: str
    audio: np.ndarray | None = None


class SpeakerDiarizer:
    """Speaker diarization using spectral features and KMeans clustering.

    Args:
        n_speakers: Fixed number of speakers, or None for auto-detection.
        sample_rate: Audio sample rate.
        max_speakers: Maximum speakers for auto-detection.
        min_speakers: Minimum speakers for auto-detection.
    """

    def __init__(
        self,
        n_speakers: int | None = DEFAULT_N_SPEAKERS,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        max_speakers: int = DEFAULT_MAX_SPEAKERS,
        min_speakers: int = DEFAULT_MIN_SPEAKERS,
    ) -> None:
        self.n_speakers = n_speakers
        self.sample_rate = sample_rate
        self.max_speakers = max_speakers
        self.min_speakers = min_speakers
        self._frame_samples = int(sample_rate * DEFAULT_FRAME_MS / 1000)
        self._scaler = StandardScaler()
        self._kmeans: KMeans | None = None

    def _compute_spectral_centroid(self, frame: np.ndarray) -> float:
        """Compute spectral centroid (brightness) of a frame."""
        if len(frame) == 0:
            return 0.0
        spectrum = np.abs(np.fft.rfft(frame.astype(np.float64)))
        freqs = np.fft.rfftfreq(len(frame), d=1.0 / self.sample_rate)
        total = spectrum.sum()
        if total == 0:
            return 0.0
        return float(np.sum(freqs * spectrum) / total)

    def _compute_spectral_rolloff(self, frame: np.ndarray, roll_pct: float = 0.85) -> float:
        """Compute spectral rolloff frequency."""
        if len(frame) == 0:
            return 0.0
        spectrum = np.abs(np.fft.rfft(frame.astype(np.float64)))
        freqs = np.fft.rfftfreq(len(frame), d=1.0 / self.sample_rate)
        total = spectrum.sum()
        if total == 0:
            return 0.0
        cumulative = np.cumsum(spectrum) / total
        idx = np.searchsorted(cumulative, roll_pct)
        return float(freqs[min(idx, len(freqs) - 1)])

    def _compute_zcr(self, frame: np.ndarray) -> float:
        """Compute zero crossing rate."""
        if len(frame) < 2:
            return 0.0
        signs = np.sign(frame.astype(np.float64))
        return float(np.sum(np.diff(signs) != 0) / len(frame))

    def _compute_rms(self, frame: np.ndarray) -> float:
        """Compute RMS energy."""
        if len(frame) == 0:
            return 0.0
        return float(np.sqrt(np.mean(frame.astype(np.float64) ** 2)))

    def _compute_f0(self, frame: np.ndarray) -> float:
        """Estimate fundamental frequency via autocorrelation."""
        if len(frame) < 2:
            return 0.0
        signal = frame.astype(np.float64)
        signal = signal - signal.mean()
        if np.all(signal == 0):
            return 0.0

        # Autocorrelation
        corr = np.correlate(signal, signal, mode="full")
        corr = corr[len(corr) // 2 :]  # Keep positive lags only
        corr = corr / corr[0] if corr[0] > 0 else corr

        # Find first significant peak (skip first few lags to avoid DC)
        min_lag = self.sample_rate // 500  # Max F0 = 500 Hz
        max_lag = self.sample_rate // 80  # Min F0 = 80 Hz
        if max_lag >= len(corr):
            max_lag = len(corr) - 1

        peaks, _ = find_peaks(corr[min_lag:max_lag], height=0.3)
        if len(peaks) == 0:
            return 0.0

        # First peak = F0
        lag = peaks[0] + min_lag
        if lag == 0:
            return 0.0
        return float(self.sample_rate / lag)

    def extract_features(self, audio: np.ndarray) -> np.ndarray:
        """Extract spectral feature vector from an audio segment.

        Returns a 10-dimensional vector:
        [centroid_mean, centroid_std, rolloff_mean, rolloff_std,
         zcr_mean, zcr_std, rms_mean, rms_std, f0_mean, f0_std]
        """
        if len(audio) < self._frame_samples:
            # Pad short audio
            audio = np.pad(audio, (0, self._frame_samples - len(audio)))

        centroids: list[float] = []
        rolloffs: list[float] = []
        zcrs: list[float] = []
        rmss: list[float] = []
        f0s: list[float] = []

        for i in range(0, len(audio), self._frame_samples):
            frame = audio[i : i + self._frame_samples]
            if len(frame) < self._frame_samples // 2:
                break
            centroids.append(self._compute_spectral_centroid(frame))
            rolloffs.append(self._compute_spectral_rolloff(frame))
            zcrs.append(self._compute_zcr(frame))
            rmss.append(self._compute_rms(frame))
            f0s.append(self._compute_f0(frame))

        if not centroids:
            return np.zeros(10)

        return np.array(
            [
                np.mean(centroids),
                np.std(centroids),
                np.mean(rolloffs),
                np.std(rolloffs),
                np.mean(zcrs),
                np.std(zcrs),
                np.mean(rmss),
                np.std(rmss),
                np.mean(f0s),
                np.std(f0s),
            ]
        )

    def _estimate_n_speakers(self, features: np.ndarray) -> int:
        """Estimate optimal number of speakers using silhouette score."""
        n_samples = len(features)
        if n_samples < 3:
            return max(1, n_samples)

        best_k = self.min_speakers
        best_score = -1.0

        max_k = min(self.max_speakers, n_samples - 1)
        for k in range(self.min_speakers, max_k + 1):
            try:
                kmeans = KMeans(n_clusters=k, n_init=10, random_state=42)
                labels = kmeans.fit_predict(features)
                if len(set(labels)) < 2:
                    continue
                score = silhouette_score(features, labels)
                if score > best_score:
                    best_score = score
                    best_k = k
            except (ValueError, RuntimeError):
                continue

        return best_k

    def diarize(
        self,
        segments: list[tuple[int, int, np.ndarray]],
    ) -> list[str]:
        """Assign speaker labels to segments.

        Args:
            segments: List of (start_ms, end_ms, audio) tuples.

        Returns:
            List of speaker labels ("Speaker 1", "Speaker 2", ...).
        """
        if not segments:
            return []

        if len(segments) == 1:
            return ["Speaker 1"]

        # Extract features for each segment
        feature_matrix = np.array([self.extract_features(audio) for _, _, audio in segments])

        # Determine number of speakers
        n_speakers = self.n_speakers
        if n_speakers is None:
            n_speakers = self._estimate_n_speakers(feature_matrix)

        n_speakers = min(n_speakers, len(segments))

        # Normalize features
        scaled = self._scaler.fit_transform(feature_matrix)

        # Cluster
        self._kmeans = KMeans(n_clusters=n_speakers, n_init=10, random_state=42)
        cluster_labels = self._kmeans.fit_predict(scaled)

        # Convert cluster IDs to "Speaker N" labels
        # Order speakers by first appearance in the segment sequence
        speaker_map: dict[int, str] = {}
        next_id = 1
        result: list[str] = []
        for cid in cluster_labels:
            if cid not in speaker_map:
                speaker_map[cid] = f"Speaker {next_id}"
                next_id += 1
            result.append(speaker_map[cid])

        return result

    def diarize_segments(
        self,
        segments: list[tuple[int, int, np.ndarray]],
    ) -> list[SpeakerSegment]:
        """Full diarization returning SpeakerSegment objects."""
        labels = self.diarize(segments)
        return [
            SpeakerSegment(
                start_ms=start,
                end_ms=end,
                speaker=label,
                audio=audio,
            )
            for (start, end, audio), label in zip(segments, labels, strict=False)
        ]
