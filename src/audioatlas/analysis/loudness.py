"""Short-term loudness analysis (K-weighted LUFS timeline).

This module provides a time-varying loudness measurement using BS.1770
K-weighting via pyloudnorm, distinct from the RMS-based timelines.

The implementation uses pyloudnorm's blockwise processing with a 3-second
integration window (standard short-term) and high overlap for reasonable
time resolution while remaining practical for long files.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from audioatlas.config import AnalysisConfig
from audioatlas.utils import ensure_2d_audio

try:
    import pyloudnorm as pyln
except Exception:  # pragma: no cover - depends on local environment
    pyln = None  # type: ignore[assignment]


@dataclass(frozen=True)
class ShortTermLufsResult:
    """3-second short-term K-weighted LUFS timeline.

    ``lufs`` contains the short-term loudness values (in LUFS).
    ``times_seconds`` gives the time (end of each analysis window) for each value.
    ``integrated_lufs`` is the track-level integrated value for reference
    (computed with standard pyloudnorm settings).
    """

    times_seconds: NDArray[np.float64]
    lufs: NDArray[np.float64]
    integrated_lufs: float | None
    sample_rate: int
    window_seconds: float
    hop_seconds: float
    warnings: list[str]

    def to_summary_dict(self) -> dict[str, object]:
        if len(self.lufs) == 0:
            return {
                "window_seconds": self.window_seconds,
                "hop_seconds": self.hop_seconds,
                "frames": 0,
                "lufs_min": None,
                "lufs_median": None,
                "lufs_max": None,
                "warnings": self.warnings,
            }
        return {
            "window_seconds": self.window_seconds,
            "hop_seconds": self.hop_seconds,
            "frames": int(len(self.lufs)),
            "lufs_min": float(np.min(self.lufs)),
            "lufs_median": float(np.median(self.lufs)),
            "lufs_max": float(np.max(self.lufs)),
            "warnings": self.warnings,
        }


def compute_short_term_lufs(
    y: NDArray[np.floating], sr: int, config: AnalysisConfig | None = None
) -> ShortTermLufsResult:
    """Compute short-term (3 s window) LUFS timeline.

    Uses BS.1770 K-weighting via pyloudnorm blockwise loudness.
    Returns an empty timeline (with warning) for audio shorter than 3 s.
    """
    cfg = config or AnalysisConfig()
    cfg.validate()

    audio = ensure_2d_audio(y).astype(np.float64, copy=False)
    warnings: list[str] = []

    window_s = float(cfg.short_term_lufs_window_seconds)
    hop_s = float(cfg.short_term_lufs_hop_seconds)

    min_samples = int(window_s * sr)
    if len(audio) < min_samples:
        warnings.append(
            "audio is shorter than the short-term window; short-term LUFS timeline is empty"
        )
        return ShortTermLufsResult(
            times_seconds=np.array([], dtype=np.float64),
            lufs=np.array([], dtype=np.float64),
            integrated_lufs=None,
            sample_rate=int(sr),
            window_seconds=window_s,
            hop_seconds=hop_s,
            warnings=warnings,
        )

    if pyln is None:
        warnings.append("pyloudnorm is not installed; short-term LUFS timeline is empty")
        return ShortTermLufsResult(
            times_seconds=np.array([], dtype=np.float64),
            lufs=np.array([], dtype=np.float64),
            integrated_lufs=None,
            sample_rate=int(sr),
            window_seconds=window_s,
            hop_seconds=hop_s,
            warnings=warnings,
        )

    data_for_meter = audio[:, 0] if audio.shape[1] == 1 else audio

    try:
        # Configure meter for 3 s short-term blocks with high overlap (~10 Hz updates)
        meter = pyln.Meter(
            sr,
            block_size=window_s,
            overlap=0.97,
        )
        # Calling integrated populates meter.blockwise_loudness with the
        # ungated short-term loudness values for the configured blocks.
        integrated_lufs: float | None = None
        try:
            il = meter.integrated_loudness(data_for_meter)
            if np.isfinite(il):
                integrated_lufs = float(il)
        except Exception as exc:  # pragma: no cover
            warnings.append(f"integrated LUFS reference failed: {exc}")

        block_lufs = np.asarray(meter.blockwise_loudness, dtype=np.float64)
        if len(block_lufs) == 0:
            warnings.append("no short-term blocks produced")
            return ShortTermLufsResult(
                times_seconds=np.array([], dtype=np.float64),
                lufs=np.array([], dtype=np.float64),
                integrated_lufs=integrated_lufs,
                sample_rate=int(sr),
                window_seconds=window_s,
                hop_seconds=hop_s,
                warnings=warnings,
            )

        # Compute corresponding times (end of each block)
        hop_time = window_s * (1.0 - 0.97)
        n = len(block_lufs)
        times = np.arange(n, dtype=np.float64) * hop_time + window_s
        duration = len(audio) / float(sr)
        times = np.minimum(times, duration)

    except Exception as exc:  # pragma: no cover
        warnings.append(f"short-term LUFS computation failed: {exc}")
        return ShortTermLufsResult(
            times_seconds=np.array([], dtype=np.float64),
            lufs=np.array([], dtype=np.float64),
            integrated_lufs=None,
            sample_rate=int(sr),
            window_seconds=window_s,
            hop_seconds=hop_s,
            warnings=warnings,
        )

    return ShortTermLufsResult(
        times_seconds=times,
        lufs=block_lufs,
        integrated_lufs=integrated_lufs,
        sample_rate=int(sr),
        window_seconds=window_s,
        hop_seconds=hop_time,
        warnings=warnings,
    )
