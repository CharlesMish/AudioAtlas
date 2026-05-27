"""Spectral analysis for AudioAtlas."""

from __future__ import annotations

from dataclasses import dataclass

import librosa
import numpy as np
from numpy.typing import NDArray
from scipy import signal

from audioatlas.config import AnalysisConfig
from audioatlas.utils import EPS, mask_to_time_ranges, power_to_db, to_mono

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


@dataclass(frozen=True)
class SpectralShapeResult:
    """Time-varying spectral shape features from a mono channel average."""

    times_seconds: NDArray[np.float64]
    spectral_centroid_hz: NDArray[np.float64]
    spectral_rolloff_85_hz: NDArray[np.float64]
    spectral_rolloff_95_hz: NDArray[np.float64]
    spectral_bandwidth_hz: NDArray[np.float64]
    valid_frames: NDArray[np.bool_]
    sample_rate: int
    n_fft: int
    hop_length: int
    warnings: list[str]

    def to_summary_dict(self) -> dict[str, object]:
        centroid = self.spectral_centroid_hz[self.valid_frames]
        rolloff_85 = self.spectral_rolloff_85_hz[self.valid_frames]
        rolloff_95 = self.spectral_rolloff_95_hz[self.valid_frames]
        bandwidth = self.spectral_bandwidth_hz[self.valid_frames]
        summary: dict[str, object] = {
            "n_fft": self.n_fft,
            "hop_length": self.hop_length,
            "frames": int(len(self.times_seconds)),
            "valid_frames": int(np.count_nonzero(self.valid_frames)),
            "undefined_frames": int(len(self.valid_frames) - np.count_nonzero(self.valid_frames)),
            "warnings": self.warnings,
        }
        if len(centroid) == 0:
            summary.update(
                {
                    "centroid_mean_hz": None,
                    "centroid_median_hz": None,
                    "centroid_min_hz": None,
                    "centroid_max_hz": None,
                    "rolloff_85_median_hz": None,
                    "rolloff_95_median_hz": None,
                    "bandwidth_median_hz": None,
                    "centroid_elevated_time_ranges": [],
                    "centroid_reduced_time_ranges": [],
                    "centroid_large_shift_time_ranges": [],
                }
            )
            return summary

        centroid_median = float(np.median(centroid))
        high_threshold = centroid_median + max(1000.0, 0.5 * centroid_median)
        low_threshold = max(0.0, centroid_median - max(1000.0, 0.5 * centroid_median))
        jump_threshold = max(2000.0, 0.75 * centroid_median)
        centroid_jumps = np.zeros(len(self.spectral_centroid_hz), dtype=bool)
        if len(self.spectral_centroid_hz) > 1:
            diffs = np.abs(np.diff(self.spectral_centroid_hz))
            valid_pairs = self.valid_frames[1:] & self.valid_frames[:-1]
            centroid_jumps[1:] = valid_pairs & (diffs > jump_threshold)

        summary.update(
            {
                "centroid_mean_hz": float(np.mean(centroid)),
                "centroid_median_hz": centroid_median,
                "centroid_min_hz": float(np.min(centroid)),
                "centroid_max_hz": float(np.max(centroid)),
                "rolloff_85_median_hz": float(np.median(rolloff_85)),
                "rolloff_95_median_hz": float(np.median(rolloff_95)),
                "bandwidth_median_hz": float(np.median(bandwidth)),
                "centroid_elevated_threshold_hz": high_threshold,
                "centroid_reduced_threshold_hz": low_threshold,
                "centroid_large_shift_threshold_hz": jump_threshold,
                "centroid_elevated_time_ranges": mask_to_time_ranges(
                    self.valid_frames & (self.spectral_centroid_hz > high_threshold),
                    self.times_seconds,
                ),
                "centroid_reduced_time_ranges": mask_to_time_ranges(
                    self.valid_frames & (self.spectral_centroid_hz < low_threshold),
                    self.times_seconds,
                ),
                "centroid_large_shift_time_ranges": mask_to_time_ranges(
                    centroid_jumps, self.times_seconds
                ),
            }
        )
        return summary


@dataclass(frozen=True)
class BandEnergyTimelineResult:
    """Time-varying relative energy for broad frequency bands."""

    times_seconds: NDArray[np.float64]
    band_names: list[str]
    band_energy_db_by_band: dict[str, NDArray[np.float64]]
    valid_frames: NDArray[np.bool_]
    sample_rate: int
    n_fft: int
    hop_length: int
    db_floor: float
    warnings: list[str]

    def to_summary_dict(self) -> dict[str, object]:
        bands: dict[str, dict[str, object]] = {}
        strongest_band: str | None = None
        strongest_median = -np.inf
        for name in self.band_names:
            values = self.band_energy_db_by_band[name]
            valid_values = values[self.valid_frames & np.isfinite(values)]
            if len(valid_values):
                median = float(np.median(valid_values))
                mean = float(np.mean(valid_values))
                max_value = float(np.max(valid_values))
                min_value = float(np.min(valid_values))
                elevated_threshold = median + 6.0
                reduced_threshold = median - 12.0
                elevated_ranges = mask_to_time_ranges(
                    self.valid_frames & np.isfinite(values) & (values > elevated_threshold),
                    self.times_seconds,
                )
                reduced_ranges = mask_to_time_ranges(
                    self.valid_frames & np.isfinite(values) & (values < reduced_threshold),
                    self.times_seconds,
                )
                if median > strongest_median:
                    strongest_median = median
                    strongest_band = name
            else:
                median = None
                mean = None
                max_value = None
                min_value = None
                elevated_threshold = None
                reduced_threshold = None
                elevated_ranges = []
                reduced_ranges = []
            bands[name] = {
                "median_db": median,
                "mean_db": mean,
                "max_db": max_value,
                "min_db": min_value,
                "elevated_threshold_db": elevated_threshold,
                "reduced_threshold_db": reduced_threshold,
                "elevated_time_ranges": elevated_ranges,
                "reduced_time_ranges": reduced_ranges,
            }

        if strongest_median == -np.inf:
            strongest_band = None
        return {
            "n_fft": self.n_fft,
            "hop_length": self.hop_length,
            "frames": int(len(self.times_seconds)),
            "valid_frames": int(np.count_nonzero(self.valid_frames)),
            "undefined_frames": int(len(self.valid_frames) - np.count_nonzero(self.valid_frames)),
            "band_names": self.band_names,
            "bands": bands,
            "strongest_band_by_median": strongest_band,
            "warnings": self.warnings,
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


def compute_band_energy_timeline(
    y: NDArray[np.floating], sr: int, config: AnalysisConfig | None = None
) -> BandEnergyTimelineResult:
    """Compute frame-wise relative energy in broad frequency bands."""

    cfg = config or AnalysisConfig()
    cfg.validate()
    mono = to_mono(y).astype(np.float64)
    if sr <= 0:
        raise ValueError("sr must be positive")
    if len(mono) == 0:
        raise ValueError("audio has zero samples")

    stft = librosa.stft(
        mono,
        n_fft=cfg.n_fft,
        hop_length=cfg.hop_length,
        window=cfg.window,
        center=True,
    )
    power = np.square(np.abs(stft)).astype(np.float64)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=cfg.n_fft).astype(np.float64)
    times = librosa.frames_to_time(
        np.arange(power.shape[1]), sr=sr, hop_length=cfg.hop_length
    ).astype(np.float64)
    frame_power = np.sum(power, axis=0)
    valid_frames = frame_power > EPS
    warnings: list[str] = []
    if not np.all(valid_frames):
        warnings.append("one or more silent frames; band energy values are undefined there")

    band_linear: dict[str, NDArray[np.float64]] = {}
    for name, low_hz, high_hz in BANDS:
        capped_high = min(high_hz, sr / 2)
        mask = (freqs >= low_hz) & (freqs < capped_high)
        values = np.full(power.shape[1], np.nan, dtype=np.float64)
        if np.any(mask):
            values[valid_frames] = np.mean(power[mask][:, valid_frames], axis=0)
        band_linear[name] = values

    reference = 0.0
    finite_values = np.concatenate(
        [values[np.isfinite(values)] for values in band_linear.values()]
    )
    if len(finite_values):
        reference = float(np.max(finite_values))
    band_db: dict[str, NDArray[np.float64]] = {}
    for name, values in band_linear.items():
        out = np.full(len(times), np.nan, dtype=np.float64)
        finite = np.isfinite(values)
        if reference > EPS and np.any(finite):
            out[finite] = np.maximum(
                np.asarray(power_to_db(values[finite] / reference, floor_db=None), dtype=np.float64),
                cfg.db_floor,
            )
        band_db[name] = out

    return BandEnergyTimelineResult(
        times_seconds=times,
        band_names=[name for name, _low, _high in BANDS],
        band_energy_db_by_band=band_db,
        valid_frames=valid_frames.astype(bool),
        sample_rate=int(sr),
        n_fft=cfg.n_fft,
        hop_length=cfg.hop_length,
        db_floor=cfg.db_floor,
        warnings=warnings,
    )


def compute_spectral_shape(
    y: NDArray[np.floating], sr: int, config: AnalysisConfig | None = None
) -> SpectralShapeResult:
    """Compute time-varying spectral shape features from a mono channel average.

    Spectral centroid is a frequency-distribution statistic, not a definitive
    brightness judgment. Silent frames are represented as ``NaN`` and excluded
    from summary statistics.
    """

    cfg = config or AnalysisConfig()
    cfg.validate()
    mono = to_mono(y).astype(np.float64)
    if sr <= 0:
        raise ValueError("sr must be positive")
    if len(mono) == 0:
        raise ValueError("audio has zero samples")

    centroid = librosa.feature.spectral_centroid(
        y=mono,
        sr=sr,
        n_fft=cfg.n_fft,
        hop_length=cfg.hop_length,
        window=cfg.window,
        center=True,
    )[0].astype(np.float64)
    rolloff_85 = librosa.feature.spectral_rolloff(
        y=mono,
        sr=sr,
        n_fft=cfg.n_fft,
        hop_length=cfg.hop_length,
        window=cfg.window,
        center=True,
        roll_percent=0.85,
    )[0].astype(np.float64)
    rolloff_95 = librosa.feature.spectral_rolloff(
        y=mono,
        sr=sr,
        n_fft=cfg.n_fft,
        hop_length=cfg.hop_length,
        window=cfg.window,
        center=True,
        roll_percent=0.95,
    )[0].astype(np.float64)
    bandwidth = librosa.feature.spectral_bandwidth(
        y=mono,
        sr=sr,
        n_fft=cfg.n_fft,
        hop_length=cfg.hop_length,
        window=cfg.window,
        center=True,
    )[0].astype(np.float64)
    rms = librosa.feature.rms(
        y=mono,
        frame_length=cfg.n_fft,
        hop_length=cfg.hop_length,
        center=True,
    )[0].astype(np.float64)
    valid = rms > EPS
    warnings: list[str] = []
    if not np.all(valid):
        warnings.append("one or more silent frames; spectral shape values are undefined there")
    for arr in (centroid, rolloff_85, rolloff_95, bandwidth):
        arr[~valid] = np.nan
    times = librosa.frames_to_time(
        np.arange(len(centroid)), sr=sr, hop_length=cfg.hop_length
    ).astype(np.float64)
    return SpectralShapeResult(
        times_seconds=times,
        spectral_centroid_hz=centroid,
        spectral_rolloff_85_hz=rolloff_85,
        spectral_rolloff_95_hz=rolloff_95,
        spectral_bandwidth_hz=bandwidth,
        valid_frames=valid.astype(bool),
        sample_rate=int(sr),
        n_fft=cfg.n_fft,
        hop_length=cfg.hop_length,
        warnings=warnings,
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
