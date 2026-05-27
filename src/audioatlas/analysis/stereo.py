"""Stereo-field analysis."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from audioatlas.config import AnalysisConfig
from audioatlas.utils import EPS, ensure_2d_audio, linear_to_dbfs


@dataclass(frozen=True)
class StereoCorrelationResult:
    """Per-frame Pearson correlation between left and right channels.

    Undefined frames are represented as ``NaN`` in ``correlation`` and are
    excluded from summary statistics.
    """

    times_seconds: NDArray[np.float64]
    correlation: NDArray[np.float64]
    overall_correlation: float | None
    sample_rate: int
    frame_length: int
    hop_length: int
    warnings: list[str]

    def to_summary_dict(self) -> dict[str, object]:
        finite = self.correlation[np.isfinite(self.correlation)]
        if len(self.correlation) == 0:
            return {
                "frame_length": self.frame_length,
                "hop_length": self.hop_length,
                "frames": 0,
                "defined_frames": 0,
                "undefined_frames": 0,
                "warnings": self.warnings,
            }
        if len(finite) == 0:
            return {
                "frame_length": self.frame_length,
                "hop_length": self.hop_length,
                "frames": int(len(self.correlation)),
                "defined_frames": 0,
                "undefined_frames": int(len(self.correlation)),
                "correlation_min": None,
                "correlation_max": None,
                "correlation_mean": None,
                "correlation_median": None,
                "overall_correlation": self.overall_correlation,
                "warnings": self.warnings,
            }
        return {
            "frame_length": self.frame_length,
            "hop_length": self.hop_length,
            "frames": int(len(self.correlation)),
            "defined_frames": int(len(finite)),
            "undefined_frames": int(len(self.correlation) - len(finite)),
            "correlation_min": float(np.min(finite)),
            "correlation_max": float(np.max(finite)),
            "correlation_mean": float(np.mean(finite)),
            "correlation_median": float(np.median(finite)),
            "overall_correlation": self.overall_correlation,
            "warnings": self.warnings,
        }


@dataclass(frozen=True)
class MidSideEnergyResult:
    """Frame-wise RMS energy for mid and side signals."""

    times_seconds: NDArray[np.float64]
    mid_rms_linear: NDArray[np.float64]
    side_rms_linear: NDArray[np.float64]
    mid_rms_dbfs: NDArray[np.float64]
    side_rms_dbfs: NDArray[np.float64]
    side_to_mid_ratio_db: NDArray[np.float64]
    sample_rate: int
    frame_length: int
    hop_length: int
    warnings: list[str]

    def to_summary_dict(self) -> dict[str, object]:
        finite_ratio = self.side_to_mid_ratio_db[np.isfinite(self.side_to_mid_ratio_db)]
        return {
            "frame_length": self.frame_length,
            "hop_length": self.hop_length,
            "frames": int(len(self.times_seconds)),
            "mid_rms_dbfs_min": float(np.min(self.mid_rms_dbfs))
            if len(self.mid_rms_dbfs)
            else None,
            "mid_rms_dbfs_max": float(np.max(self.mid_rms_dbfs))
            if len(self.mid_rms_dbfs)
            else None,
            "mid_rms_dbfs_mean": float(np.mean(self.mid_rms_dbfs))
            if len(self.mid_rms_dbfs)
            else None,
            "side_rms_dbfs_min": float(np.min(self.side_rms_dbfs))
            if len(self.side_rms_dbfs)
            else None,
            "side_rms_dbfs_max": float(np.max(self.side_rms_dbfs))
            if len(self.side_rms_dbfs)
            else None,
            "side_rms_dbfs_mean": float(np.mean(self.side_rms_dbfs))
            if len(self.side_rms_dbfs)
            else None,
            "side_to_mid_ratio_db_median": float(np.median(finite_ratio))
            if len(finite_ratio)
            else None,
            "side_to_mid_ratio_db_mean": float(np.mean(finite_ratio))
            if len(finite_ratio)
            else None,
            "undefined_ratio_frames": int(len(self.side_to_mid_ratio_db) - len(finite_ratio)),
            "warnings": self.warnings,
        }


def _frame_pair(
    left: NDArray[np.float64], right: NDArray[np.float64], frame_length: int, hop_length: int
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    starts = np.arange(0, len(left), hop_length, dtype=np.int64)
    left_frames = np.zeros((len(starts), frame_length), dtype=np.float64)
    right_frames = np.zeros((len(starts), frame_length), dtype=np.float64)
    for i, start in enumerate(starts):
        end = min(start + frame_length, len(left))
        size = end - start
        if size > 0:
            left_frames[i, :size] = left[start:end]
            right_frames[i, :size] = right[start:end]
    times = starts.astype(np.float64)
    return times, left_frames, right_frames


def _pearson_by_frame(
    left_frames: NDArray[np.float64],
    right_frames: NDArray[np.float64],
    low_energy: NDArray[np.bool_] | None = None,
) -> tuple[NDArray[np.float64], bool, bool]:
    left_centered = left_frames - np.mean(left_frames, axis=1, keepdims=True)
    right_centered = right_frames - np.mean(right_frames, axis=1, keepdims=True)
    numerator = np.sum(left_centered * right_centered, axis=1)
    left_power = np.sum(np.square(left_centered), axis=1)
    right_power = np.sum(np.square(right_centered), axis=1)
    denominator = np.sqrt(left_power * right_power)
    zero_variance = denominator <= EPS
    degenerate = zero_variance.copy()
    if low_energy is not None:
        degenerate = degenerate | low_energy
    correlation = np.full(len(left_frames), np.nan, dtype=np.float64)
    np.divide(numerator, denominator, out=correlation, where=~degenerate)
    low_energy_only = (
        bool(np.any(low_energy & ~zero_variance)) if low_energy is not None else False
    )
    return np.clip(correlation, -1.0, 1.0), bool(np.any(zero_variance)), low_energy_only


def _rms_by_frame(frames: NDArray[np.float64]) -> NDArray[np.float64]:
    return np.sqrt(np.mean(np.square(frames), axis=1)).astype(np.float64)


def compute_stereo_correlation(
    y: NDArray[np.floating], sr: int, config: AnalysisConfig | None = None
) -> StereoCorrelationResult:
    """Compute a left/right Pearson correlation timeline.

    Mono input is reported as a constant ``+1.0`` series by convention and
    includes one warning in ``result.warnings``. Stereo silence or other
    zero-variance frames are represented as ``NaN`` because Pearson
    correlation is undefined there.
    """

    cfg = config or AnalysisConfig()
    cfg.validate()
    audio = ensure_2d_audio(y)
    if sr <= 0:
        raise ValueError("sr must be positive")
    if audio.shape[0] == 0:
        raise ValueError("audio has zero samples")

    warnings: list[str] = []
    starts = np.arange(0, audio.shape[0], cfg.hop_length, dtype=np.float64)
    times = (starts / sr).astype(np.float64)

    if audio.shape[1] == 1:
        warnings.append("mono input; stereo correlation is reported as +1.0 by convention")
        correlation = np.ones(len(times), dtype=np.float64)
        return StereoCorrelationResult(
            times_seconds=times,
            correlation=correlation,
            overall_correlation=1.0,
            sample_rate=int(sr),
            frame_length=cfg.n_fft,
            hop_length=cfg.hop_length,
            warnings=warnings,
        )

    if audio.shape[1] > 2:
        warnings.append(
            f"input has {audio.shape[1]} channels; stereo correlation uses channels 0 and 1"
        )

    left = audio[:, 0].astype(np.float64, copy=False)
    right = audio[:, 1].astype(np.float64, copy=False)
    _starts, left_frames, right_frames = _frame_pair(left, right, cfg.n_fft, cfg.hop_length)
    frame_rms = np.sqrt(
        (np.mean(np.square(left_frames), axis=1) + np.mean(np.square(right_frames), axis=1))
        / 2.0
    )
    frame_rms_dbfs = np.asarray(linear_to_dbfs(frame_rms, floor_db=None), dtype=np.float64)
    low_energy = frame_rms_dbfs < cfg.correlation_min_rms_dbfs
    correlation, has_degenerate_frames, has_low_energy_frames = _pearson_by_frame(
        left_frames, right_frames, low_energy
    )
    if has_degenerate_frames:
        warnings.append("one or more frames have zero variance; correlation is undefined")
    if has_low_energy_frames:
        warnings.append(
            "one or more frames are below correlation_min_rms_dbfs; correlation is undefined"
        )

    left_centered = left - float(np.mean(left))
    right_centered = right - float(np.mean(right))
    full_rms = float(np.sqrt((np.mean(np.square(left)) + np.mean(np.square(right))) / 2.0))
    denominator = float(
        np.sqrt(np.sum(np.square(left_centered)) * np.sum(np.square(right_centered)))
    )
    overall_correlation: float | None = None
    if denominator > EPS and linear_to_dbfs(full_rms, floor_db=None) >= cfg.correlation_min_rms_dbfs:
        overall_correlation = float(
            np.clip(np.sum(left_centered * right_centered) / denominator, -1.0, 1.0)
        )

    return StereoCorrelationResult(
        times_seconds=times,
        correlation=correlation,
        overall_correlation=overall_correlation,
        sample_rate=int(sr),
        frame_length=cfg.n_fft,
        hop_length=cfg.hop_length,
        warnings=warnings,
    )


def compute_mid_side_energy(
    y: NDArray[np.floating], sr: int, config: AnalysisConfig | None = None
) -> MidSideEnergyResult:
    """Compute frame-wise mid and side RMS energy.

    For mono input, mid is the mono signal and side is zero by convention.
    The result includes a warning so downstream consumers can distinguish
    mono input from stereo input with no side energy.
    """

    cfg = config or AnalysisConfig()
    cfg.validate()
    audio = ensure_2d_audio(y)
    if sr <= 0:
        raise ValueError("sr must be positive")
    if audio.shape[0] == 0:
        raise ValueError("audio has zero samples")

    warnings: list[str] = []
    if audio.shape[1] == 1:
        warnings.append("mono input; side energy is reported as zero by convention")
        mid = audio[:, 0].astype(np.float64, copy=False)
        side = np.zeros_like(mid)
    else:
        if audio.shape[1] > 2:
            warnings.append(f"input has {audio.shape[1]} channels; mid/side uses channels 0 and 1")
        left = audio[:, 0].astype(np.float64, copy=False)
        right = audio[:, 1].astype(np.float64, copy=False)
        mid = (left + right) / 2.0
        side = (left - right) / 2.0

    starts, mid_frames, side_frames = _frame_pair(mid, side, cfg.n_fft, cfg.hop_length)
    times = (starts / sr).astype(np.float64)
    mid_rms = _rms_by_frame(mid_frames)
    side_rms = _rms_by_frame(side_frames)
    mid_dbfs = np.asarray(linear_to_dbfs(mid_rms, floor_db=cfg.db_floor), dtype=np.float64)
    side_dbfs = np.asarray(linear_to_dbfs(side_rms, floor_db=cfg.db_floor), dtype=np.float64)

    ratio_db = np.full(len(mid_rms), np.nan, dtype=np.float64)
    valid_mid = mid_rms > EPS
    if np.any(valid_mid):
        ratio = np.maximum(side_rms[valid_mid], EPS) / mid_rms[valid_mid]
        ratio_db[valid_mid] = np.maximum(20.0 * np.log10(ratio), cfg.db_floor)

    return MidSideEnergyResult(
        times_seconds=times,
        mid_rms_linear=mid_rms,
        side_rms_linear=side_rms,
        mid_rms_dbfs=mid_dbfs,
        side_rms_dbfs=side_dbfs,
        side_to_mid_ratio_db=ratio_db,
        sample_rate=int(sr),
        frame_length=cfg.n_fft,
        hop_length=cfg.hop_length,
        warnings=warnings,
    )


__all__ = [
    "MidSideEnergyResult",
    "StereoCorrelationResult",
    "compute_mid_side_energy",
    "compute_stereo_correlation",
]
