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
    correlation_min_rms_dbfs: float = -80.0
    onset_density_window_seconds: float = 1.0
    short_term_lufs_window_seconds: float = 3.0
    short_term_lufs_hop_seconds: float = 0.1
    max_findings: int = 8
    band_finding_min_duration_seconds: float = 0.5
    band_finding_min_relative_db: float = -80.0
    finding_min_time_range_seconds: float = 0.25
    report_max_time_ranges: int = 8

    def validate(self) -> None:
        if self.n_fft <= 0:
            raise ValueError("n_fft must be positive")
        if self.hop_length <= 0:
            raise ValueError("hop_length must be positive")
        if not 0 < self.near_clipping_threshold < self.clipping_threshold <= 1.0:
            raise ValueError("Expected 0 < near_clipping_threshold < clipping_threshold <= 1.0")
        if self.true_peak_oversample < 1:
            raise ValueError("true_peak_oversample must be >= 1")
        if self.correlation_min_rms_dbfs > 0:
            raise ValueError("correlation_min_rms_dbfs must be <= 0")
        if self.onset_density_window_seconds <= 0:
            raise ValueError("onset_density_window_seconds must be positive")
        if self.short_term_lufs_window_seconds <= 0:
            raise ValueError("short_term_lufs_window_seconds must be positive")
        if self.short_term_lufs_hop_seconds <= 0:
            raise ValueError("short_term_lufs_hop_seconds must be positive")
        if self.max_findings <= 0:
            raise ValueError("max_findings must be positive")
        if self.band_finding_min_duration_seconds < 0:
            raise ValueError("band_finding_min_duration_seconds must be non-negative")
        if self.band_finding_min_relative_db < self.db_floor:
            raise ValueError("band_finding_min_relative_db must be >= db_floor")
        if self.finding_min_time_range_seconds < 0:
            raise ValueError("finding_min_time_range_seconds must be non-negative")
        if self.report_max_time_ranges <= 0:
            raise ValueError("report_max_time_ranges must be positive")
