"""Spectral analysis for AudioAtlas."""

from __future__ import annotations

from dataclasses import dataclass

import librosa
import numpy as np
from numpy.typing import NDArray
from scipy import signal

from audioatlas.config import AnalysisConfig
from audioatlas.utils import power_to_db, to_mono


@dataclass(frozen=True)
class SpectrogramResult:
    """Log-frequency spectrogram data.

    ``sample_rate`` is carried on the dataclass so visualization functions
    don't need ``sr`` threaded through them separately - this enforces the
    "visualization should not recompute analysis" principle in the brief.
    """

    db: NDArray[np.float64]
    freqs_hz: NDArray[np.float64]
    times_seconds: NDArray[np.float64]
    sample_rate: int
    n_fft: int
    hop_length: int
    db_floor: float


@dataclass(frozen=True)
class AverageSpectrumResult:
    """Welch average spectrum data."""

    freqs_hz: NDArray[np.float64]
    power_db: NDArray[np.float64]
    sample_rate: int
    nperseg: int

    def to_summary_dict(self) -> dict[str, object]:
        valid = self.freqs_hz >= 20
        if not np.any(valid):
            return {"nperseg": self.nperseg, "bins": int(len(self.freqs_hz))}
        freqs = self.freqs_hz[valid]
        power = self.power_db[valid]
        peak_idx = int(np.argmax(power))
        return {
            "nperseg": self.nperseg,
            "bins": int(len(self.freqs_hz)),
            "strongest_bin_hz": float(freqs[peak_idx]),
            "strongest_bin_db": float(power[peak_idx]),
        }


def compute_log_spectrogram(
    y: NDArray[np.floating], sr: int, config: AnalysisConfig | None = None
) -> SpectrogramResult:
    """Compute a dB STFT spectrogram from a mono downmix.

    The returned dB values are relative to STFT magnitude with ``ref=1.0``
    and are not a calibrated dBFS meter because raw STFT magnitudes depend
    on FFT/window scaling. Values are floored by ``config.db_floor`` so
    different tracks remain visually comparable.
    """

    cfg = config or AnalysisConfig()
    cfg.validate()
    mono = to_mono(y)
    stft = librosa.stft(
        mono,
        n_fft=cfg.n_fft,
        hop_length=cfg.hop_length,
        window=cfg.window,
        center=True,
    )
    magnitude = np.abs(stft)
    db = librosa.amplitude_to_db(magnitude, ref=1.0, top_db=None).astype(np.float64)
    db = np.maximum(db, cfg.db_floor)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=cfg.n_fft).astype(np.float64)
    times = librosa.frames_to_time(
        np.arange(db.shape[1]), sr=sr, hop_length=cfg.hop_length
    ).astype(np.float64)
    return SpectrogramResult(
        db=db,
        freqs_hz=freqs,
        times_seconds=times,
        sample_rate=int(sr),
        n_fft=cfg.n_fft,
        hop_length=cfg.hop_length,
        db_floor=cfg.db_floor,
    )


def compute_average_spectrum(
    y: NDArray[np.floating], sr: int, config: AnalysisConfig | None = None
) -> AverageSpectrumResult:
    """Compute a Welch average power spectrum from a mono downmix."""

    cfg = config or AnalysisConfig()
    cfg.validate()
    mono = to_mono(y).astype(np.float64)
    if len(mono) < 2:
        raise ValueError("Need at least two samples for spectrum")
    nperseg = min(cfg.welch_nperseg, len(mono))
    noverlap = nperseg // 2 if nperseg >= 4 else 0
    freqs, pxx = signal.welch(
        mono,
        fs=sr,
        window="hann",
        nperseg=nperseg,
        noverlap=noverlap,
        detrend="constant",
        scaling="spectrum",
        average="mean",
    )
    power_db = np.asarray(power_to_db(pxx, floor_db=cfg.db_floor), dtype=np.float64)
    return AverageSpectrumResult(
        freqs_hz=freqs.astype(np.float64),
        power_db=power_db,
        sample_rate=int(sr),
        nperseg=int(nperseg),
    )
