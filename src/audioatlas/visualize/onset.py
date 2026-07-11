"""Onset-density visualization."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from audioatlas.analysis.dynamics import OnsetDensityResult


def plot_onset_density(
    onset: OnsetDensityResult,
    out_path: str | Path,
    *,
    title: str = "Onset / Transient Density Timeline",
) -> Path:
    """Save an onset-strength based density timeline plot."""

    max_density = float(max(onset.smoothed_onset_density)) if len(onset.smoothed_onset_density) else 0.0
    if max_density > 0:
        display_density = onset.smoothed_onset_density / max_density
    else:
        display_density = onset.smoothed_onset_density

    fig, ax = plt.subplots(figsize=(14, 4))
    ax.plot(
        onset.times_seconds,
        onset.normalized_onset_strength,
        linewidth=0.8,
        alpha=0.45,
        label="Normalized onset strength",
    )
    ax.plot(
        onset.times_seconds,
        display_density,
        linewidth=1.4,
        label="Smoothed onset density (normalized for display)",
    )
    ax.set_title(title)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Onset-strength based value (normalized for display)")
    ax.set_ylim(0, 1.05)
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=9)
    fig.tight_layout()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out
