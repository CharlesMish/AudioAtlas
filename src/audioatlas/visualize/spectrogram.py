"""Spectrogram visualization."""

from __future__ import annotations

from pathlib import Path

import librosa.display
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from audioatlas.analysis.spectral import SpectrogramResult


def plot_log_spectrogram(
    spec: SpectrogramResult,
    out_path: str | Path,
    *,
    title: str = "Log-Frequency Spectrogram (relative to track max, dB)",
) -> Path:
    """Save a log-frequency dB spectrogram.

    The color scale is relative to the maximum STFT magnitude in this
    track, not a calibrated dBFS meter.
    """

    fig, ax = plt.subplots(figsize=(14, 6))
    img = librosa.display.specshow(
        spec.db,
        sr=spec.sample_rate,
        hop_length=spec.hop_length,
        x_axis="time",
        y_axis="log",
        cmap="magma",
        ax=ax,
        vmin=spec.db_floor,
        vmax=0.0,
    )
    ax.set_title(title)
    ax.set_xlabel("Time")
    ax.set_ylabel("Frequency (Hz)")
    ax.set_ylim(20, spec.sample_rate / 2)
    fig.colorbar(img, ax=ax, format="%+2.0f dB")
    fig.tight_layout()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out
