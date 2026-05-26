"""Shared configuration objects for AudioAtlas."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnalysisConfig:
    """Global analysis defaults.

    Keep frame and hop settings centralized so time-series plots align.
    """

    n_fft: int = 4096
    hop_length: int = 1024
    window: str = "hann"
    db_floor: float = -100.0
    rms_frame_length: int = 4096
    clipping_threshold: float = 0.999
    near_clipping_threshold: float = 0.99
    true_peak_oversample: int = 4
    welch_nperseg: int = 8192
    max_plot_points: int = 250_000

    def validate(self) -> None:
        if self.n_fft <= 0:
            raise ValueError("n_fft must be positive")
        if self.hop_length <= 0:
            raise ValueError("hop_length must be positive")
        if not 0 < self.near_clipping_threshold < self.clipping_threshold <= 1.0:
            raise ValueError("Expected 0 < near_clipping_threshold < clipping_threshold <= 1.0")
        if self.true_peak_oversample < 1:
            raise ValueError("true_peak_oversample must be >= 1")
