from __future__ import annotations

import numpy as np
import pytest

from audioatlas.analysis.spectral import (
    compute_average_spectrum,
    compute_band_energy_timeline,
    compute_band_power_timeline,
    compute_log_spectrogram,
    compute_spectral_shape,
)
from audioatlas.config import AnalysisConfig
from audioatlas.visualize.band_energy import (
    plot_band_energy_timeline,
    plot_band_power_timeline,
)
from audioatlas.visualize.spectral_shape import plot_spectral_shape
from audioatlas.visualize.spectrogram import plot_log_spectrogram


def test_spectrogram_shapes(sine_minus_6_dbfs, sr):
    cfg = AnalysisConfig(n_fft=2048, hop_length=512)
    spec = compute_log_spectrogram(sine_minus_6_dbfs, sr, cfg)

    assert spec.db.shape[0] == cfg.n_fft // 2 + 1
    assert spec.db.shape[1] == len(spec.times_seconds)
    assert len(spec.freqs_hz) == spec.db.shape[0]
    assert np.all(np.isfinite(spec.db))
    assert np.max(spec.db) == pytest.approx(0.0)
    assert np.min(spec.db) >= cfg.db_floor


def test_welch_average_spectrum_finds_1khz_sine(sine_minus_6_dbfs, sr):
    cfg = AnalysisConfig(welch_nperseg=4096)
    spectrum = compute_average_spectrum(sine_minus_6_dbfs, sr, cfg)

    mask = (spectrum.freqs_hz > 20) & (spectrum.freqs_hz < 20_000)
    peak_freq = spectrum.freqs_hz[mask][np.argmax(spectrum.power_db[mask])]
    assert 950 <= peak_freq <= 1050
    assert np.max(spectrum.power_db[spectrum.freqs_hz >= 20]) == pytest.approx(0.0)
    assert spectrum.to_summary_dict()["strongest_bin_db"] == pytest.approx(0.0)


def test_silent_spectral_displays_stay_at_floor(sr):
    cfg = AnalysisConfig(n_fft=2048, hop_length=512, welch_nperseg=2048)
    y = np.zeros((sr, 1), dtype=np.float32)

    spec = compute_log_spectrogram(y, sr, cfg)
    spectrum = compute_average_spectrum(y, sr, cfg)

    assert np.allclose(spec.db, cfg.db_floor)
    assert np.allclose(spectrum.power_db, cfg.db_floor)
    assert spectrum.to_summary_dict()["strongest_band"] is None


def test_mean_band_power_identifies_low_frequency_signal(sr):
    cfg = AnalysisConfig(welch_nperseg=4096)
    t = np.arange(sr, dtype=np.float64) / sr
    y = (0.5 * np.sin(2 * np.pi * 80 * t)).astype(np.float32)[:, None]

    spectrum = compute_average_spectrum(y, sr, cfg)
    summary = spectrum.to_summary_dict()

    assert summary["band_measurement"] == "relative_mean_power_per_fft_bin"
    assert summary["highest_mean_power_band"] == "bass"
    assert (
        summary["band_mean_power"]["bass"]["mean_power_db"]
        > summary["band_mean_power"]["mid"]["mean_power_db"]
    )
    # Temporary alpha aliases preserve existing consumers without redefining the metric.
    assert summary["strongest_band"] == summary["highest_mean_power_band"]
    assert summary["band_energies"] == summary["band_mean_power"]


def test_mean_band_power_identifies_high_frequency_signal(sr):
    cfg = AnalysisConfig(welch_nperseg=4096)
    t = np.arange(sr, dtype=np.float64) / sr
    y = (0.5 * np.sin(2 * np.pi * 8000 * t)).astype(np.float32)[:, None]

    spectrum = compute_average_spectrum(y, sr, cfg)
    summary = spectrum.to_summary_dict()

    assert summary["highest_mean_power_band"] == "high"
    assert (
        summary["band_mean_power"]["high"]["mean_power_db"]
        > summary["band_mean_power"]["mid"]["mean_power_db"]
    )


def test_log_spectrogram_plot_omits_zero_hz_on_log_axis(tmp_path, monkeypatch, sine_minus_6_dbfs, sr):
    cfg = AnalysisConfig(n_fft=2048, hop_length=512)
    spec = compute_log_spectrogram(sine_minus_6_dbfs, sr, cfg)
    closed = []

    def fake_close(fig):
        closed.append(fig)

    monkeypatch.setattr("matplotlib.pyplot.close", fake_close)
    plot_log_spectrogram(spec, tmp_path / "spectrogram.png")

    ax = closed[0].axes[0]
    bottom, _top = ax.get_ylim()
    assert bottom >= 20


def test_spectral_shape_higher_for_high_frequency_sine(sr):
    cfg = AnalysisConfig(n_fft=2048, hop_length=512)
    t = np.arange(sr, dtype=np.float64) / sr
    low = (0.5 * np.sin(2 * np.pi * 200 * t)).astype(np.float32)[:, None]
    high = (0.5 * np.sin(2 * np.pi * 5000 * t)).astype(np.float32)[:, None]

    low_shape = compute_spectral_shape(low, sr, cfg)
    high_shape = compute_spectral_shape(high, sr, cfg)

    assert np.nanmedian(high_shape.spectral_centroid_hz) > np.nanmedian(
        low_shape.spectral_centroid_hz
    )
    assert np.nanmedian(high_shape.spectral_rolloff_95_hz) > np.nanmedian(
        low_shape.spectral_rolloff_95_hz
    )


def test_spectral_shape_silence_is_safe(sr):
    cfg = AnalysisConfig(n_fft=2048, hop_length=512)
    y = np.zeros((sr, 1), dtype=np.float32)

    result = compute_spectral_shape(y, sr, cfg)
    summary = result.to_summary_dict()

    assert np.all(np.isnan(result.spectral_centroid_hz))
    assert summary["valid_frames"] == 0
    assert summary["centroid_median_hz"] is None
    assert result.warnings


def test_spectral_shape_high_frequency_content_raises_metrics(sr):
    cfg = AnalysisConfig(n_fft=2048, hop_length=512)
    t = np.arange(sr, dtype=np.float64) / sr
    low = 0.5 * np.sin(2 * np.pi * 300 * t)
    mixed = low + 0.25 * np.sin(2 * np.pi * 6000 * t)

    low_shape = compute_spectral_shape(low.astype(np.float32)[:, None], sr, cfg)
    mixed_shape = compute_spectral_shape(mixed.astype(np.float32)[:, None], sr, cfg)

    assert np.nanmedian(mixed_shape.spectral_centroid_hz) > np.nanmedian(
        low_shape.spectral_centroid_hz
    )
    assert np.nanmedian(mixed_shape.spectral_rolloff_85_hz) > np.nanmedian(
        low_shape.spectral_rolloff_85_hz
    )


def test_plot_spectral_shape_writes_png(tmp_path, sine_minus_6_dbfs, sr):
    cfg = AnalysisConfig(n_fft=2048, hop_length=512)
    result = compute_spectral_shape(sine_minus_6_dbfs, sr, cfg)
    path = plot_spectral_shape(result, tmp_path / "spectral_shape.png")

    assert path.exists()
    assert path.stat().st_size > 0


def test_band_power_timeline_low_frequency_signal_concentrates_lower_band(sr):
    cfg = AnalysisConfig(n_fft=2048, hop_length=512)
    t = np.arange(sr, dtype=np.float64) / sr
    y = (0.5 * np.sin(2 * np.pi * 80 * t)).astype(np.float32)[:, None]

    result = compute_band_power_timeline(y, sr, cfg)
    summary = result.to_summary_dict()

    assert summary["measurement"] == "relative_mean_power_per_fft_bin"
    assert summary["highest_mean_power_band_by_median"] == "bass"
    assert summary["bands"]["bass"]["median_db"] > summary["bands"]["mid"]["median_db"]
    assert (
        summary["strongest_band_by_median"]
        == summary["highest_mean_power_band_by_median"]
    )


def test_band_power_timeline_high_frequency_signal_concentrates_upper_band(sr):
    cfg = AnalysisConfig(n_fft=2048, hop_length=512)
    t = np.arange(sr, dtype=np.float64) / sr
    y = (0.5 * np.sin(2 * np.pi * 8000 * t)).astype(np.float32)[:, None]

    result = compute_band_power_timeline(y, sr, cfg)
    summary = result.to_summary_dict()

    assert summary["highest_mean_power_band_by_median"] in {"high", "air"}
    assert summary["bands"]["high"]["median_db"] > summary["bands"]["mid"]["median_db"]


def test_band_power_timeline_silence_is_safe(sr):
    cfg = AnalysisConfig(n_fft=2048, hop_length=512)
    y = np.zeros((sr, 1), dtype=np.float32)

    result = compute_band_power_timeline(y, sr, cfg)
    summary = result.to_summary_dict()

    assert summary["valid_frames"] == 0
    assert summary["highest_mean_power_band_by_median"] is None
    assert all(summary["bands"][band]["median_db"] is None for band in summary["band_names"])
    assert result.warnings


def test_plot_band_power_timeline_writes_png(tmp_path, sine_minus_6_dbfs, sr):
    cfg = AnalysisConfig(n_fft=2048, hop_length=512)
    result = compute_band_power_timeline(sine_minus_6_dbfs, sr, cfg)
    path = plot_band_power_timeline(result, tmp_path / "band_power.png")

    assert path.exists()
    assert path.stat().st_size > 0


def test_band_energy_compatibility_wrappers_match_canonical_api(
    tmp_path, sine_minus_6_dbfs, sr
):
    cfg = AnalysisConfig(n_fft=2048, hop_length=512)
    canonical = compute_band_power_timeline(sine_minus_6_dbfs, sr, cfg)
    legacy = compute_band_energy_timeline(sine_minus_6_dbfs, sr, cfg)

    assert legacy.to_summary_dict() == canonical.to_summary_dict()
    assert legacy.band_energy_db_by_band.keys() == canonical.band_mean_power_db_by_band.keys()
    out = plot_band_energy_timeline(legacy, tmp_path / "legacy_band_filename.png")
    assert out.exists() and out.stat().st_size > 0
