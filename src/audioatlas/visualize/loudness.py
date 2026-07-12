"""Short-term LUFS visualization."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from audioatlas.analysis.loudness import ShortTermLufsResult


def plot_short_term_lufs(
    lufs_result: ShortTermLufsResult,
    out_path: str | Path,
    *,
    title: str = "Short-term LUFS Timeline",
) -> Path:
    """Save a short-term (K-weighted) LUFS timeline plot."""
    fig, ax = plt.subplots(figsize=(14, 4))

    if len(lufs_result.lufs) > 0:
        ax.plot(
            lufs_result.times_seconds,
            lufs_result.lufs,
            linewidth=1.2,
            label="Short-term LUFS (3 s)",
        )
        if lufs_result.integrated_lufs is not None and np.isfinite(lufs_result.integrated_lufs):
            ax.axhline(
                lufs_result.integrated_lufs,
                linestyle="--",
                linewidth=1.0,
                alpha=0.7,
                color="C1",
                label=f"Integrated: {lufs_result.integrated_lufs:.1f} LUFS",
            )
        # Reasonable y range for music
        lmin = float(np.min(lufs_result.lufs))
        lmax = float(np.max(lufs_result.lufs))
        pad = max(1.0, (lmax - lmin) * 0.1)
        ax.set_ylim(lmin - pad, lmax + pad)
    else:
        ax.text(0.5, 0.5, "No short-term LUFS data (file < 3 s)",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_ylim(-70, -10)

    ax.set_title(title)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("LUFS")
    ax.grid(True, alpha=0.25)
    if len(lufs_result.lufs) > 0:
        ax.legend(fontsize=9, loc="upper right")
    fig.tight_layout()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out
