"""Small shared utilities."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

EPS = 1e-12


def ensure_2d_audio(y: NDArray[np.floating]) -> NDArray[np.float32]:
    """Return audio as float32 with shape (n_samples, n_channels)."""

    arr = np.asarray(y, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr[:, None]
    if arr.ndim != 2:
        raise ValueError(f"Expected audio shape (samples, channels); got {arr.shape}")
    return arr


def to_mono(y: NDArray[np.floating]) -> NDArray[np.float32]:
    """Downmix audio to mono using an arithmetic channel average.

    Used for mono-only visualizations such as spectrum and spectrogram.
    Does not normalize the result.
    """

    arr = ensure_2d_audio(y)
    return np.mean(arr, axis=1, dtype=np.float32)


def linear_to_dbfs(
    value: float | NDArray[np.floating],
    *,
    floor_db: float | None = None,
) -> float | NDArray[np.float64]:
    """Convert linear full-scale amplitude to dBFS with numerical protection.

    Args:
        value: Linear amplitude (0.0 = silence, 1.0 = full scale).
        floor_db: If provided, clamp the result so it never reads more negative
            than ``floor_db``. Use this to keep silent inputs from producing
            absurd numbers like -240 dB in user-visible reports. Pass ``None``
            (default) when you want the raw math without clamping.
    """

    out = 20.0 * np.log10(np.maximum(np.asarray(value, dtype=np.float64), EPS))
    if floor_db is not None:
        out = np.maximum(out, floor_db)
    if np.ndim(value) == 0:
        return float(out)
    return out


def power_to_db(
    value: float | NDArray[np.floating],
    *,
    floor_db: float | None = None,
) -> float | NDArray[np.float64]:
    """Convert full-scale power to dB with numerical protection.

    See :func:`linear_to_dbfs` for the meaning of ``floor_db``.
    """

    out = 10.0 * np.log10(np.maximum(np.asarray(value, dtype=np.float64), EPS))
    if floor_db is not None:
        out = np.maximum(out, floor_db)
    if np.ndim(value) == 0:
        return float(out)
    return out


def mmss(seconds: float) -> str:
    """Format seconds as M:SS."""

    if not math.isfinite(seconds):
        return "?:??"
    minutes = int(seconds // 60)
    secs = int(round(seconds - minutes * 60))
    return f"{minutes}:{secs:02d}"


def safe_stem(path: str | Path) -> str:
    """Return a filesystem-friendly stem."""

    return Path(path).stem.replace(" ", "_")


def mask_to_time_ranges(
    mask: NDArray[np.bool_],
    times: NDArray[np.floating],
    min_duration_sec: float = 0.0,
    merge_gap_sec: float = 0.0,
) -> list[dict[str, float]]:
    """Convert a boolean frame mask into contiguous time ranges."""

    mask_arr = np.asarray(mask, dtype=bool)
    times_arr = np.asarray(times, dtype=np.float64)
    if mask_arr.shape != times_arr.shape:
        raise ValueError("mask and times must have the same shape")
    if min_duration_sec < 0:
        raise ValueError("min_duration_sec must be >= 0")
    if merge_gap_sec < 0:
        raise ValueError("merge_gap_sec must be >= 0")
    if len(mask_arr) == 0 or not np.any(mask_arr):
        return []

    if len(times_arr) > 1:
        positive_steps = np.diff(times_arr)
        positive_steps = positive_steps[positive_steps > 0]
        frame_duration = float(np.median(positive_steps)) if len(positive_steps) else 0.0
    else:
        frame_duration = 0.0

    ranges: list[dict[str, float]] = []
    start_idx: int | None = None
    for i, active in enumerate(mask_arr):
        if active and start_idx is None:
            start_idx = i
        elif not active and start_idx is not None:
            ranges.append(_range_from_indices(times_arr, start_idx, i - 1, frame_duration))
            start_idx = None
    if start_idx is not None:
        ranges.append(_range_from_indices(times_arr, start_idx, len(mask_arr) - 1, frame_duration))

    merged: list[dict[str, float]] = []
    for item in ranges:
        if merged and item["start"] - merged[-1]["end"] <= merge_gap_sec:
            merged[-1]["end"] = item["end"]
            merged[-1]["duration"] = merged[-1]["end"] - merged[-1]["start"]
        else:
            merged.append(item)

    return [item for item in merged if item["duration"] >= min_duration_sec]


def _range_from_indices(
    times: NDArray[np.float64], start_idx: int, end_idx: int, frame_duration: float
) -> dict[str, float]:
    start = float(times[start_idx])
    end = float(times[end_idx] + frame_duration)
    return {"start": start, "end": end, "duration": end - start}
