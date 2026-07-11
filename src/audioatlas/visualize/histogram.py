"""Sample histogram visualization."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from numpy.typing import NDArray

from audioatlas.config import AnalysisConfig
from audioatlas.utils import ensure_2d_audio


def plot_sample_histogram(
    y: NDArray[np.floating],
    out_path: str | Path,
    config: AnalysisConfig | None = None,
    *,
    title: str = "Sample Histogram",
) -> Path:
    """Save a histogram of sample amplitudes."""

    cfg = config or AnalysisConfig()
    audio = ensure_2d_audio(y)
    flattened = audio.reshape(-1)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(flattened, bins=200, log=True)
    ax.axvline(cfg.near_clipping_threshold, linestyle="--", linewidth=1, label="near clip +")
    ax.axvline(-cfg.near_clipping_threshold, linestyle="--", linewidth=1, label="near clip -")
    ax.axvline(cfg.clipping_threshold, linestyle=":", linewidth=1, label="clip +")
    ax.axvline(-cfg.clipping_threshold, linestyle=":", linewidth=1, label="clip -")
    ax.set_title(title)
    ax.set_xlabel("Sample amplitude (1.0 = nominal full scale)")
    ax.set_ylabel("Count (log scale)")
    max_abs = float(np.nanmax(np.abs(flattened))) if flattened.size else 1.0
    x_limit = max(1.05, max_abs * 1.05)
    ax.set_xlim(-x_limit, x_limit)
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out
