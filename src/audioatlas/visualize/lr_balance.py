"""Neutral signed channel RMS timeline; undefined frames remain gaps."""

from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from audioatlas.analysis.lr_balance import LRBalanceResult
from audioatlas.plot_theme import plot_role


def plot_lr_balance(result: LRBalanceResult, out_path: str | Path) -> Path:
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.plot(
        result.times_seconds,
        result.balance_db,
        linewidth=1.2,
        marker=".",
        markersize=2,
        **plot_role("s1"),
    )
    ax.axhline(0, linewidth=0.9, linestyle="--", **plot_role("reference"))
    values = result.balance_db[np.isfinite(result.balance_db)]
    extent = max(1.0, float(np.max(np.abs(values))) * 1.15) if len(values) else 1.0
    ax.set_ylim(-extent, extent)
    ax.set_title("L/R RMS Balance Timeline")
    ax.set_xlabel("Time in analyzed audio (s; frame centers)")
    ax.set_ylabel("L/R RMS balance (dB)")
    ax.text(
        1,
        1.02,
        "+ Left higher RMS   /   − Right higher RMS",
        transform=ax.transAxes,
        ha="right",
        fontsize=9,
    )
    if not len(values):
        message = {
            "not_applicable_mono": "Not applicable: mono audio",
            "not_applicable_multichannel": "Not applicable: no semantic L/R mapping for multichannel audio",
            "insufficient_samples": "No complete analysis frames",
        }.get(result.status, "No defined frames: one or both channels below the RMS floor")
        ax.text(0.5, 0.65, message, transform=ax.transAxes, ha="center", fontsize=10)
    ax.text(0, 1.02, "Gaps: undefined frames", transform=ax.transAxes, fontsize=9)
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out
