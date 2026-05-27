from __future__ import annotations

import numpy as np

from audioatlas.analysis.dynamics import compute_onset_density
from audioatlas.config import AnalysisConfig
from audioatlas.visualize.onset import plot_onset_density


def _click_train(sr: int, duration: float, interval_seconds: float) -> np.ndarray:
    y = np.zeros(int(sr * duration), dtype=np.float32)
    click_len = max(1, int(0.002 * sr))
    for start in np.arange(0.1, duration, interval_seconds):
        idx = int(start * sr)
        y[idx : idx + click_len] = 0.8
    return y[:, None]


def test_click_train_has_higher_onset_density_than_sustained_sine(sr):
    cfg = AnalysisConfig(n_fft=2048, hop_length=512, onset_density_window_seconds=0.25)
    t = np.arange(int(sr * 2.0), dtype=np.float64) / sr
    sustained = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)[:, None]
    clicks = _click_train(sr, duration=2.0, interval_seconds=0.125)

    sustained_result = compute_onset_density(sustained, sr, cfg)
    clicks_result = compute_onset_density(clicks, sr, cfg)

    assert clicks_result.to_summary_dict()["onset_density_mean"] > (
        sustained_result.to_summary_dict()["onset_density_mean"]
    )
    assert clicks_result.to_summary_dict()["onset_density_max"] > (
        sustained_result.to_summary_dict()["onset_density_max"]
    )


def test_onset_density_silence_is_safe(sr):
    cfg = AnalysisConfig(n_fft=2048, hop_length=512)
    y = np.zeros((sr, 1), dtype=np.float32)

    result = compute_onset_density(y, sr, cfg)
    summary = result.to_summary_dict()

    assert np.allclose(result.onset_strength, 0.0)
    assert np.allclose(result.normalized_onset_strength, 0.0)
    assert np.allclose(result.smoothed_onset_density, 0.0)
    assert summary["onset_density_max"] == 0.0
    assert summary["high_onset_density_time_ranges"] == []
    assert result.warnings


def test_dense_clicks_have_higher_density_than_sparse_clicks(sr):
    cfg = AnalysisConfig(n_fft=2048, hop_length=512, onset_density_window_seconds=0.5)
    sparse = _click_train(sr, duration=2.0, interval_seconds=0.5)
    dense = _click_train(sr, duration=2.0, interval_seconds=0.1)

    sparse_result = compute_onset_density(sparse, sr, cfg)
    dense_result = compute_onset_density(dense, sr, cfg)

    assert dense_result.to_summary_dict()["onset_density_mean"] > (
        sparse_result.to_summary_dict()["onset_density_mean"]
    )


def test_plot_onset_density_writes_png(tmp_path, sr):
    cfg = AnalysisConfig(n_fft=2048, hop_length=512)
    result = compute_onset_density(_click_train(sr, duration=1.0, interval_seconds=0.1), sr, cfg)
    path = plot_onset_density(result, tmp_path / "onset_density.png")

    assert path.exists()
    assert path.stat().st_size > 0
