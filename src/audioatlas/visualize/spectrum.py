"""Average spectrum visualization."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from audioatlas.analysis.spectral import AverageSpectrumResult
from audioatlas.config import AnalysisConfig


def plot_average_spectrum(
    spectrum: AverageSpectrumResult,
    out_path: str | Path,
    config: AnalysisConfig | None = None,
    *,
    title: str = "Welch Average Spectrum",
) -> Path:
    """Save an average spectrum plot."""

    cfg = config or AnalysisConfig()
    fig, ax = plt.subplots(figsize=(14, 5))
    freqs = spectrum.freqs_hz
    mask = freqs >= 20
    ax.semilogx(freqs[mask], spectrum.power_db[mask], linewidth=1.1)
    ax.set_title(title)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Welch power (relative to track max, dB)")
    ax.set_xlim(20, max(20, float(freqs[-1])))
    ax.set_ylim(cfg.db_floor, 3)
    ax.grid(True, which="both", alpha=0.25)

    for freq, label in [
        (60, "60"), (120, "120"), (250, "250"), (500, "500"),
        (1000, "1k"), (2000, "2k"), (5000, "5k"), (10000, "10k"),
    ]:
        if 20 <= freq <= freqs[-1]:
            ax.axvline(freq, linestyle="--", linewidth=0.6, alpha=0.45)
            ax.text(
                freq, ax.get_ylim()[1], label,
                rotation=90, va="top", ha="right", fontsize=8, alpha=0.7,
            )

    fig.tight_layout()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out
