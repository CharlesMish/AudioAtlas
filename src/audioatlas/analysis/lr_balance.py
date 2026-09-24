"""Signed channel RMS difference; no inference about perceived position."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from audioatlas.config import AnalysisConfig
from audioatlas.utils import ensure_2d_audio


@dataclass(frozen=True)
class LRBalanceResult:
    times_seconds: NDArray[np.float64]
    left_rms_linear: NDArray[np.float64]
    right_rms_linear: NDArray[np.float64]
    balance_db: NDArray[np.float64]
    frame_status: NDArray[np.str_]
    status: str
    sample_rate: int
    frame_length: int
    hop_length: int
    min_rms_dbfs: float

    def to_summary_dict(self) -> dict[str, object]:
        """Serialize undefined ratios as null, retaining per-frame reasons."""
        defined = self.balance_db[np.isfinite(self.balance_db)]
        frames = len(self.times_seconds)
        return {
            "status": self.status,
            "frame_length": self.frame_length,
            "hop_length": self.hop_length,
            "min_rms_dbfs": self.min_rms_dbfs,
            "frames": frames,
            "defined_frames": len(defined),
            "defined_frame_coverage": len(defined) / frames if frames else None,
            "balance_db_median": float(np.median(defined)) if len(defined) else None,
            "balance_db_p10": float(np.percentile(defined, 10)) if len(defined) else None,
            "balance_db_p90": float(np.percentile(defined, 90)) if len(defined) else None,
            "undefined_reason_counts": {
                reason: int(np.count_nonzero(self.frame_status == reason))
                for reason in ("left_below_floor", "right_below_floor", "both_below_floor")
            },
            "timeline": {
                "times_seconds": self.times_seconds.tolist(),
                "left_rms_linear": self.left_rms_linear.tolist(),
                "right_rms_linear": self.right_rms_linear.tolist(),
                "balance_db": [float(v) if np.isfinite(v) else None for v in self.balance_db],
                "status": self.frame_status.tolist(),
            },
        }


def compute_lr_balance(
    y: NDArray[np.floating],
    sr: int,
    config: AnalysisConfig | None = None,
) -> LRBalanceResult:
    """Measure complete unwindowed frames of exactly two decoded channels.

    Positive means higher left RMS. Each operand must be at or above the
    configured floor. Internal NaNs are absent ratios, never zeroes. The
    difference of logarithms avoids dividing extreme amplitudes and preserves
    exact channel-swap antisymmetry. No normalization or DC removal is applied.
    """
    cfg = config or AnalysisConfig()
    cfg.validate()
    if sr <= 0:
        raise ValueError("sr must be positive")
    audio = ensure_2d_audio(y).astype(np.float64, copy=False)
    if not np.all(np.isfinite(audio)):
        raise ValueError("audio must contain only finite samples")
    length, hop = cfg.rms_frame_length, cfg.hop_length
    empty = np.empty(0, dtype=np.float64)
    status = "computed"
    if audio.shape[1] != 2:
        status = "not_applicable_mono" if audio.shape[1] == 1 else "not_applicable_multichannel"
    elif len(audio) < length:
        status = "insufficient_samples"
    if status != "computed":
        return LRBalanceResult(
            empty,
            empty.copy(),
            empty.copy(),
            empty.copy(),
            np.array([], dtype="U20"),
            status,
            sr,
            length,
            hop,
            cfg.lr_balance_min_rms_dbfs,
        )

    starts = np.arange(0, len(audio) - length + 1, hop)
    # Per-frame scaled RMS bounds intermediates without cumulative subtraction
    # error or allocating an overlapping frames-by-samples copy for a whole song.
    rms = np.empty((len(starts), 2), dtype=np.float64)
    for i, start in enumerate(starts):
        frame = audio[start : start + length]
        scale = np.max(np.abs(frame), axis=0)
        scaled = np.divide(frame, scale, out=np.zeros_like(frame), where=scale > 0)
        rms[i] = scale * np.sqrt(np.mean(scaled * scaled, axis=0))
    floor = 10.0 ** (cfg.lr_balance_min_rms_dbfs / 20.0)
    left_ok, right_ok = rms[:, 0] >= floor, rms[:, 1] >= floor
    states = np.full(len(starts), "defined", dtype="U20")
    states[~left_ok & right_ok] = "left_below_floor"
    states[left_ok & ~right_ok] = "right_below_floor"
    states[~left_ok & ~right_ok] = "both_below_floor"
    valid = left_ok & right_ok
    balance = np.full(len(starts), np.nan)
    balance[valid] = 20.0 * (np.log10(rms[valid, 0]) - np.log10(rms[valid, 1]))
    return LRBalanceResult(
        (starts + length / 2.0) / sr,
        rms[:, 0],
        rms[:, 1],
        balance,
        states,
        status,
        sr,
        length,
        hop,
        cfg.lr_balance_min_rms_dbfs,
    )
