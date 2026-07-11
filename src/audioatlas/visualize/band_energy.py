"""Broad-band relative mean-power visualization."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from audioatlas.analysis.spectral import BandPowerTimelineResult


def plot_band_power_timeline(result: BandPowerTimelineResult, out_path: Path) -> Path:
    """Render relative mean spectral power per FFT bin for broad bands."""

    matrix = np.vstack(
        [result.band_mean_power_db_by_band[name] for name in result.band_names]
    )
    plot_matrix = np.nan_to_num(matrix, nan=result.db_floor)
    if len(result.times_seconds):
        x_min = float(result.times_seconds[0])
        x_max = float(result.times_seconds[-1])
        if x_max <= x_min:
            x_max = x_min + result.hop_length / result.sample_rate
    else:
        x_min = 0.0
        x_max = 1.0

    fig, ax = plt.subplots(figsize=(12, 5))
    image = ax.imshow(
        plot_matrix,
        origin="lower",
        aspect="auto",
        interpolation="nearest",
        extent=(x_min, x_max, -0.5, len(result.band_names) - 0.5),
        vmin=result.db_floor,
        vmax=0.0,
    )
    ax.set_yticks(range(len(result.band_names)))
    ax.set_yticklabels([name.replace("_", " ").title() for name in result.band_names])
    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel("Frequency band")
    ax.set_title("Relative Mean Band Power Timeline")
    colorbar = fig.colorbar(image, ax=ax)
    colorbar.set_label("Relative mean power per FFT bin (dB)")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160)
    plt.close(fig)
    return out_path


def plot_band_energy_timeline(result: BandPowerTimelineResult, out_path: Path) -> Path:
    """Deprecated compatibility wrapper for :func:`plot_band_power_timeline`."""

    return plot_band_power_timeline(result, out_path)
