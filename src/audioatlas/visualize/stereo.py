"""Stereo-field visualization."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from audioatlas.analysis.stereo import StereoCorrelationResult


def plot_stereo_correlation(
    stereo: StereoCorrelationResult,
    out_path: str | Path,
    *,
    title: str = "Stereo Correlation Timeline",
) -> Path:
    """Save a left/right correlation timeline plot."""

    fig, ax = plt.subplots(figsize=(14, 4))
    ax.plot(stereo.times_seconds, stereo.correlation, linewidth=1.2)
    ax.axhline(1.0, linestyle=":", linewidth=0.8, alpha=0.5)
    ax.axhline(0.0, linestyle="--", linewidth=0.8, alpha=0.5)
    ax.axhline(-1.0, linestyle=":", linewidth=0.8, alpha=0.5)
    ax.set_title(title)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Pearson r (L/R)")
    ax.set_ylim(-1.05, 1.05)
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out
