"""Dynamics and onset-density analysis."""

from __future__ import annotations

from dataclasses import dataclass

import librosa
import numpy as np
from numpy.typing import NDArray

from audioatlas.config import AnalysisConfig
from audioatlas.utils import EPS, mask_to_time_ranges, to_mono


@dataclass(frozen=True)
class OnsetDensityResult:
    """Onset-strength based transient density timeline."""

    times_seconds: NDArray[np.float64]
    onset_strength: NDArray[np.float64]
    normalized_onset_strength: NDArray[np.float64]
    smoothed_onset_density: NDArray[np.float64]
    sample_rate: int
    hop_length: int
    smoothing_window_seconds: float
    smoothing_window_frames: int
    mel_bands: int
    warnings: list[str]

    def to_summary_dict(self) -> dict[str, object]:
        if len(self.onset_strength) == 0:
            return {
                "hop_length": self.hop_length,
                "frames": 0,
                "smoothing_window_seconds": self.smoothing_window_seconds,
                "smoothing_window_frames": self.smoothing_window_frames,
                "mel_bands": self.mel_bands,
                "warnings": self.warnings,
            }
        median_density = float(np.median(self.smoothed_onset_density))
        high_threshold = median_density + max(0.15, 0.5 * median_density)
        high_ranges = mask_to_time_ranges(
            self.smoothed_onset_density > high_threshold,
            self.times_seconds,
            min_duration_sec=0.0,
            merge_gap_sec=float(self.hop_length / self.sample_rate),
        )
        max_idx = int(np.argmax(self.smoothed_onset_density))
        return {
            "hop_length": self.hop_length,
            "frames": int(len(self.times_seconds)),
            "smoothing_window_seconds": self.smoothing_window_seconds,
            "smoothing_window_frames": self.smoothing_window_frames,
            "mel_bands": self.mel_bands,
            "onset_strength_mean": float(np.mean(self.onset_strength)),
            "onset_strength_median": float(np.median(self.onset_strength)),
            "onset_strength_max": float(np.max(self.onset_strength)),
            "onset_density_mean": float(np.mean(self.smoothed_onset_density)),
            "onset_density_median": median_density,
            "onset_density_max": float(np.max(self.smoothed_onset_density)),
            "high_onset_density_threshold": high_threshold,
            "high_onset_density_time_ranges": high_ranges,
            "strongest_onset_density_time": float(self.times_seconds[max_idx]),
            "warnings": self.warnings,
        }


def compute_onset_density(
    y: NDArray[np.floating], sr: int, config: AnalysisConfig | None = None
) -> OnsetDensityResult:
    """Compute onset strength and smoothed onset-density timelines.

    The result is based on librosa onset strength. It is not a definitive
    measure of punch or transient quality.
    """

    cfg = config or AnalysisConfig()
    cfg.validate()
    if sr <= 0:
        raise ValueError("sr must be positive")
    mono = to_mono(y).astype(np.float64)
    if len(mono) == 0:
        raise ValueError("audio has zero samples")

    # Librosa defaults to 128 mel filters. At very small user-selected FFT
    # sizes that can create empty filters and emit a raw library warning. Keep
    # the default at normal AudioAtlas FFT sizes and scale it down only when
    # frequency resolution is too coarse.
    mel_bands = min(128, max(1, cfg.n_fft // 8))
    onset_strength = librosa.onset.onset_strength(
        y=mono,
        sr=sr,
        hop_length=cfg.hop_length,
        n_fft=cfg.n_fft,
        n_mels=mel_bands,
    ).astype(np.float64)
    warnings: list[str] = []
    max_strength = float(np.max(onset_strength)) if len(onset_strength) else 0.0
    if max_strength <= EPS:
        normalized = np.zeros_like(onset_strength, dtype=np.float64)
        warnings.append("no measurable onset strength; onset density is reported as zero")
    else:
        normalized = onset_strength / max_strength

    window_frames = max(1, int(round(cfg.onset_density_window_seconds * sr / cfg.hop_length)))
    # np.convolve(..., mode="same") returns max(len(signal), len(kernel)); cap the
    # kernel so short sections keep smoothed density aligned with onset frames.
    window_frames = min(window_frames, len(onset_strength))
    kernel = np.ones(window_frames, dtype=np.float64) / window_frames
    density = np.convolve(onset_strength, kernel, mode="same").astype(np.float64)
    if len(density) != len(onset_strength):
        raise ValueError("onset density smoothing length mismatch")
    times = librosa.frames_to_time(
        np.arange(len(onset_strength)), sr=sr, hop_length=cfg.hop_length
    ).astype(np.float64)
    return OnsetDensityResult(
        times_seconds=times,
        onset_strength=onset_strength,
        normalized_onset_strength=normalized.astype(np.float64),
        smoothed_onset_density=density,
        sample_rate=int(sr),
        hop_length=cfg.hop_length,
        smoothing_window_seconds=float(cfg.onset_density_window_seconds),
        smoothing_window_frames=window_frames,
        mel_bands=mel_bands,
        warnings=warnings,
    )