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
