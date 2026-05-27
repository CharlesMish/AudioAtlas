"""Frequency band energy timeline visualization."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from audioatlas.analysis.spectral import BandEnergyTimelineResult


def plot_band_energy_timeline(
    band_energy: BandEnergyTimelineResult,
    out_path: str | Path,
    *,
    title: str = "Frequency Band Energy Timeline",
) -> Path:
    """Save a heatmap of relative band energy over time."""

    data = np.vstack(
        [band_energy.band_energy_db_by_band[name] for name in band_energy.band_names]
    )
    masked = np.ma.masked_invalid(data)
    fig, ax = plt.subplots(figsize=(14, 5))
    if len(band_energy.times_seconds) > 1:
        x_min = float(band_energy.times_seconds[0])
        step = float(np.median(np.diff(band_energy.times_seconds)))
        x_max = float(band_energy.times_seconds[-1] + step)
    else:
        x_min = 0.0
        x_max = 1.0
    img = ax.imshow(
        masked,
        aspect="auto",
        origin="lower",
        interpolation="nearest",
        extent=(x_min, x_max, -0.5, len(band_energy.band_names) - 0.5),
        cmap="magma",
        vmin=band_energy.db_floor,
        vmax=0.0,
    )
    ax.set_title(title)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Band")
    ax.set_yticks(np.arange(len(band_energy.band_names)))
    ax.set_yticklabels(band_energy.band_names)
    fig.colorbar(img, ax=ax, format="%+2.0f dB", label="Relative energy (dB)")
    fig.tight_layout()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out
