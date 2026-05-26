from __future__ import annotations

import numpy as np

from audioatlas.analysis.spectral import compute_average_spectrum, compute_log_spectrogram
from audioatlas.config import AnalysisConfig


def test_spectrogram_shapes(sine_minus_6_dbfs, sr):
    cfg = AnalysisConfig(n_fft=2048, hop_length=512)
    spec = compute_log_spectrogram(sine_minus_6_dbfs, sr, cfg)

    assert spec.db.shape[0] == cfg.n_fft // 2 + 1
    assert spec.db.shape[1] == len(spec.times_seconds)
    assert len(spec.freqs_hz) == spec.db.shape[0]
    assert np.all(np.isfinite(spec.db))


def test_welch_average_spectrum_finds_1khz_sine(sine_minus_6_dbfs, sr):
    cfg = AnalysisConfig(welch_nperseg=4096)
    spectrum = compute_average_spectrum(sine_minus_6_dbfs, sr, cfg)

    mask = (spectrum.freqs_hz > 20) & (spectrum.freqs_hz < 20_000)
    peak_freq = spectrum.freqs_hz[mask][np.argmax(spectrum.power_db[mask])]
    assert 950 <= peak_freq <= 1050
