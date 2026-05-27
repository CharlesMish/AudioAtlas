"""Spectral shape visualization."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from audioatlas.analysis.spectral import SpectralShapeResult


def plot_spectral_shape(
    shape: SpectralShapeResult,
    out_path: str | Path,
    *,
    title: str = "Spectral Shape Timeline",
) -> Path:
    """Save a spectral shape timeline plot."""

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(
        shape.times_seconds,
        shape.spectral_centroid_hz,
        linewidth=1.1,
        label="Spectral centroid",
    )
    ax.plot(
        shape.times_seconds,
        shape.spectral_rolloff_85_hz,
        linewidth=1.0,
        label="Rolloff 85%",
    )
    ax.plot(
        shape.times_seconds,
        shape.spectral_rolloff_95_hz,
        linewidth=1.0,
        label="Rolloff 95%",
    )
    ax.set_title(title)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Frequency (Hz)")
    ax.set_ylim(0, shape.sample_rate / 2)
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=9)
    fig.tight_layout()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out
