"""Chroma CQT visualization."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from audioatlas.analysis.tonal import ChromaCqtResult


def plot_chroma_cqt(
    chroma: ChromaCqtResult,
    out_path: str | Path,
    *,
    title: str = "Chroma CQT (Pitch-Class Energy)",
) -> Path:
    """Save a heatmap of pitch-class energy over time."""

    fig, ax = plt.subplots(figsize=(14, 5))
    if len(chroma.times_seconds) > 1:
        x_min = float(chroma.times_seconds[0])
        step = float(np.median(np.diff(chroma.times_seconds)))
        x_max = float(chroma.times_seconds[-1] + step)
    else:
        x_min = 0.0
        x_max = 1.0
    vmax = float(np.max(chroma.chroma)) if chroma.chroma.size else 1.0
    if vmax <= 0.0:
        vmax = 1.0
    img = ax.imshow(
        chroma.chroma,
        aspect="auto",
        origin="lower",
        interpolation="nearest",
        extent=(x_min, x_max, -0.5, len(chroma.pitch_classes) - 0.5),
        cmap="viridis",
        vmin=0.0,
        vmax=vmax,
    )
    ax.set_title(title)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Pitch class")
    ax.set_yticks(np.arange(len(chroma.pitch_classes)))
    ax.set_yticklabels(list(chroma.pitch_classes))
    fig.colorbar(img, ax=ax, label="Relative pitch-class energy")
    fig.tight_layout()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out