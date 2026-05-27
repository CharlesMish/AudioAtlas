"""Spectral analysis for AudioAtlas."""

from __future__ import annotations

from dataclasses import dataclass

import librosa
import numpy as np
from numpy.typing import NDArray
from scipy import signal

from audioatlas.config import AnalysisConfig
from audioatlas.utils import EPS, power_to_db, to_mono

BANDS: tuple[tuple[str, float, float], ...] = (
    ("sub", 20.0, 60.0),
    ("bass", 60.0, 120.0),
    ("low_mid", 120.0, 350.0),
    ("mid", 350.0, 2000.0),
    ("presence", 2000.0, 5000.0),
    ("high", 5000.0, 10000.0),
    ("air", 10000.0, 20000.0),
)


@dataclass(frozen=True)
class SpectrogramResult:
    """Log-frequency spectrogram data, relative to the track's max bin.

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
    band_energies: dict[str, dict[str, float | None]]

    def to_summary_dict(self) -> dict[str, object]:
        valid = self.freqs_hz >= 20
        if not np.any(valid):
            return {
                "nperseg": self.nperseg,
                "bins": int(len(self.freqs_hz)),
                "band_energies": self.band_energies,
            }
        freqs = self.freqs_hz[valid]
        power = self.power_db[valid]
        peak_idx = int(np.argmax(power))
        strongest_band = _strongest_band(self.band_energies)
        return {
            "nperseg": self.nperseg,
            "bins": int(len(self.freqs_hz)),
            "strongest_bin_hz": float(freqs[peak_idx]),
            "strongest_bin_db": float(power[peak_idx]),
            "band_energies": self.band_energies,
            "strongest_band": strongest_band,
        }


def compute_log_spectrogram(
    y: NDArray[np.floating], sr: int, config: AnalysisConfig | None = None
) -> SpectrogramResult:
    """Compute a relative dB STFT spectrogram from a mono downmix.

    The returned dB values are relative to the maximum STFT magnitude in
    this track: the brightest bin is 0 dB and quieter bins are negative.
    This is not a calibrated dBFS meter.
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
    ref = float(np.max(magnitude)) if magnitude.size else 0.0
    if ref <= EPS:
        db = np.full(magnitude.shape, cfg.db_floor, dtype=np.float64)
    else:
        db = librosa.amplitude_to_db(magnitude, ref=ref, top_db=None).astype(np.float64)
        db = db - float(np.max(db))
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
    """Compute a relative Welch average power spectrum from a mono downmix."""

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
    if float(np.max(pxx)) <= EPS:
        power_db = np.full(len(pxx), cfg.db_floor, dtype=np.float64)
    else:
        raw_power_db = np.asarray(power_to_db(pxx, floor_db=None), dtype=np.float64)
        valid = freqs >= 20
        ref_db = float(np.max(raw_power_db[valid])) if np.any(valid) else float(np.max(raw_power_db))
        power_db = np.maximum(raw_power_db - ref_db, cfg.db_floor)
    band_energies = _compute_band_energies(
        freqs.astype(np.float64), power_db, nyquist=float(sr / 2), floor_db=cfg.db_floor
    )
    return AverageSpectrumResult(
        freqs_hz=freqs.astype(np.float64),
        power_db=power_db,
        sample_rate=int(sr),
        nperseg=int(nperseg),
        band_energies=band_energies,
    )


def _compute_band_energies(
    freqs: NDArray[np.float64],
    power_db: NDArray[np.float64],
    *,
    nyquist: float,
    floor_db: float,
) -> dict[str, dict[str, float | None]]:
    rel_power = np.power(10.0, power_db / 10.0)
    out: dict[str, dict[str, float | None]] = {}
    for name, low_hz, high_hz in BANDS:
        capped_high = min(high_hz, nyquist)
        if capped_high <= low_hz:
            energy_db = None
        else:
            mask = (freqs >= low_hz) & (freqs < capped_high)
            if not np.any(mask):
                energy_db = None
            else:
                energy_linear = float(np.mean(rel_power[mask]))
                energy_db = float(max(power_to_db(energy_linear, floor_db=floor_db), floor_db))
        out[name] = {
            "low_hz": low_hz,
            "high_hz": capped_high,
            "energy_db": energy_db,
        }
    return out


def _strongest_band(bands: dict[str, dict[str, float | None]]) -> str | None:
    valid = [
        (name, values["energy_db"])
        for name, values in bands.items()
        if isinstance(values.get("energy_db"), (int, float))
    ]
    if not valid:
        return None
    values = [float(item[1]) for item in valid]
    if max(values) == min(values):
        return None
    return max(valid, key=lambda item: float(item[1]))[0]
