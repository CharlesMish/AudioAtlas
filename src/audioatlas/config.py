"""Shared configuration objects for AudioAtlas."""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real


def _require_positive_int(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _require_finite_number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number")
    return number


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
        _require_positive_int("n_fft", self.n_fft)
        _require_positive_int("hop_length", self.hop_length)
        _require_positive_int("rms_frame_length", self.rms_frame_length)
        _require_positive_int("true_peak_oversample", self.true_peak_oversample)
        _require_positive_int("welch_nperseg", self.welch_nperseg)
        _require_positive_int("max_plot_points", self.max_plot_points)
        _require_positive_int("max_findings", self.max_findings)
        _require_positive_int("report_max_time_ranges", self.report_max_time_ranges)
        if not isinstance(self.window, str) or not self.window.strip():
            raise ValueError("window must be a non-empty string")

        db_floor = _require_finite_number("db_floor", self.db_floor)
        clipping_threshold = _require_finite_number(
            "clipping_threshold", self.clipping_threshold
        )
        near_clipping_threshold = _require_finite_number(
            "near_clipping_threshold", self.near_clipping_threshold
        )
        correlation_floor = _require_finite_number(
            "correlation_min_rms_dbfs", self.correlation_min_rms_dbfs
        )
        onset_window = _require_finite_number(
            "onset_density_window_seconds", self.onset_density_window_seconds
        )
        short_term_window = _require_finite_number(
            "short_term_lufs_window_seconds", self.short_term_lufs_window_seconds
        )
        short_term_hop = _require_finite_number(
            "short_term_lufs_hop_seconds", self.short_term_lufs_hop_seconds
        )
        band_min_duration = _require_finite_number(
            "band_finding_min_duration_seconds", self.band_finding_min_duration_seconds
        )
        band_relative_db = _require_finite_number(
            "band_finding_min_relative_db", self.band_finding_min_relative_db
        )
        finding_min_range = _require_finite_number(
            "finding_min_time_range_seconds", self.finding_min_time_range_seconds
        )

        if db_floor >= 0:
            raise ValueError("db_floor must be negative")
        if not 0 < near_clipping_threshold < clipping_threshold <= 1.0:
            raise ValueError("Expected 0 < near_clipping_threshold < clipping_threshold <= 1.0")
        if correlation_floor > 0:
            raise ValueError("correlation_min_rms_dbfs must be <= 0")
        if onset_window <= 0:
            raise ValueError("onset_density_window_seconds must be positive")
        if short_term_window <= 0:
            raise ValueError("short_term_lufs_window_seconds must be positive")
        if short_term_hop <= 0:
            raise ValueError("short_term_lufs_hop_seconds must be positive")
        if band_min_duration < 0:
            raise ValueError("band_finding_min_duration_seconds must be non-negative")
        if band_relative_db < db_floor:
            raise ValueError("band_finding_min_relative_db must be >= db_floor")
        if band_relative_db > 0:
            raise ValueError("band_finding_min_relative_db must be <= 0")
        if finding_min_range < 0:
            raise ValueError("finding_min_time_range_seconds must be non-negative")
