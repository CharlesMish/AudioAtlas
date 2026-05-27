"""Stereo-field visualization."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from audioatlas.analysis.stereo import MidSideEnergyResult, StereoCorrelationResult
from audioatlas.config import AnalysisConfig


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


def plot_mid_side_energy(
    mid_side: MidSideEnergyResult,
    out_path: str | Path,
    config: AnalysisConfig | None = None,
    *,
    title: str = "Mid/Side RMS Energy Timeline",
) -> Path:
    """Save a mid/side RMS timeline plot."""

    cfg = config or AnalysisConfig()
    fig, (ax_energy, ax_ratio) = plt.subplots(
        2, 1, figsize=(14, 6), sharex=True, height_ratios=(2, 1)
    )
    ax_energy.plot(
        mid_side.times_seconds, mid_side.mid_rms_dbfs, linewidth=1.2, label="Mid RMS"
    )
    ax_energy.plot(
        mid_side.times_seconds, mid_side.side_rms_dbfs, linewidth=1.2, label="Side RMS"
    )
    ax_energy.set_title(title)
    ax_energy.set_ylabel("RMS (dBFS)")
    ax_energy.set_ylim(cfg.db_floor, 0)
    ax_energy.grid(True, alpha=0.25)
    ax_energy.legend(fontsize=9)

    ax_ratio.plot(
        mid_side.times_seconds, mid_side.side_to_mid_ratio_db, linewidth=1.0
    )
    ax_ratio.axhline(0.0, linestyle="--", linewidth=0.8, alpha=0.45)
    ax_ratio.set_xlabel("Time (s)")
    ax_ratio.set_ylabel("Side-to-mid ratio (dB)")
    ax_ratio.set_ylim(cfg.db_floor, 12)
    ax_ratio.grid(True, alpha=0.25)
    fig.tight_layout()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out
