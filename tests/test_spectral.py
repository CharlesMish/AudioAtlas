from __future__ import annotations

import numpy as np
import pytest

from audioatlas.analysis.spectral import compute_average_spectrum, compute_log_spectrogram
from audioatlas.config import AnalysisConfig
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
