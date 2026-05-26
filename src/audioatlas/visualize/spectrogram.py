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
    title: str = "Log-Frequency Spectrogram (relative STFT magnitude, dB)",
) -> Path:
    """Save a log-frequency dB spectrogram.

    The color scale is relative STFT magnitude in dB, not a calibrated
    dBFS meter. Sample rate is taken from ``spec.sample_rate`` so no extra argument is
    needed - this is the v0.2 contract for visualization functions.
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
    )
    ax.set_title(title)
    ax.set_xlabel("Time")
    ax.set_ylabel("Frequency")
    fig.colorbar(img, ax=ax, format="%+2.0f dB")
    fig.tight_layout()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out
