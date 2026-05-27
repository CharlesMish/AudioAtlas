"""Waveform and RMS visualization."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from numpy.typing import NDArray

from audioatlas.analysis.levels import RmsEnvelopeResult
from audioatlas.config import AnalysisConfig
from audioatlas.utils import to_mono


def _downsample_for_plot(
    x: NDArray[np.floating], max_points: int
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return indices and samples downsampled for plotting only."""

    arr = np.asarray(x, dtype=np.float64)
    if len(arr) <= max_points:
        idx = np.arange(len(arr), dtype=np.float64)
        return idx, arr
    step = int(np.ceil(len(arr) / max_points))
    idx = np.arange(0, len(arr), step, dtype=np.float64)
    return idx, arr[::step]


def plot_waveform_rms(
    y: NDArray[np.floating],
    sr: int,
    rms: RmsEnvelopeResult,
    out_path: str | Path,
    config: AnalysisConfig | None = None,
    *,
    title: str = "Waveform + RMS Envelope",
) -> Path:
    """Save a waveform plot with RMS overlay."""

    cfg = config or AnalysisConfig()
    mono = to_mono(y)
    idx, samples = _downsample_for_plot(mono, cfg.max_plot_points)
    times = idx / sr

    fig, ax1 = plt.subplots(figsize=(14, 5))
    ax1.plot(times, samples, linewidth=0.35, alpha=0.8)
    ax1.set_title(title)
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("Amplitude (full scale)")
    ax1.set_ylim(-1.05, 1.05)
    ax1.grid(True, alpha=0.25)

    ax2 = ax1.twinx()
    ax2.plot(rms.times_seconds, rms.rms_dbfs, linewidth=1.2, alpha=0.9)
    ax2.set_ylabel("RMS (dBFS)")
    ax2.set_ylim(cfg.db_floor, 0)

    fig.tight_layout()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def plot_rms_timeline(
    rms: RmsEnvelopeResult,
    out_path: str | Path,
    config: AnalysisConfig | None = None,
    *,
    title: str = "Frame RMS Timeline (dBFS)",
) -> Path:
    """Save the v0.1 RMS dBFS timeline.

    This is RMS dBFS, not K-weighted short-term LUFS. The name reflects that
    intentionally - per AGENT_BRIEF, AudioAtlas does not overclaim.
    A short-term-LUFS timeline can be added later as a separate, named plot.
    """

    cfg = config or AnalysisConfig()
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.plot(rms.times_seconds, rms.rms_dbfs, linewidth=1.25)
    ax.fill_between(rms.times_seconds, cfg.db_floor, rms.rms_dbfs, alpha=0.2)
    ax.set_title(title)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("RMS (dBFS)")
    ax.set_ylim(cfg.db_floor, 0)
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out
