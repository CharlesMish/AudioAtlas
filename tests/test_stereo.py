from __future__ import annotations

import numpy as np
import pytest

from audioatlas.analysis.stereo import compute_stereo_correlation
from audioatlas.config import AnalysisConfig
from audioatlas.visualize.stereo import plot_stereo_correlation


def _cfg() -> AnalysisConfig:
    return AnalysisConfig(n_fft=1024, hop_length=256)


def test_mono_input_reports_constant_positive_correlation(sine_minus_6_dbfs, sr):
    result = compute_stereo_correlation(sine_minus_6_dbfs, sr, _cfg())

    assert len(result.correlation) > 0
    assert np.allclose(result.correlation, 1.0)
    assert result.overall_correlation == pytest.approx(1.0)
    assert len(result.warnings) == 1
    assert "mono input" in result.warnings[0]

    summary = result.to_summary_dict()
    assert summary["frames"] == len(result.correlation)
    assert summary["correlation_min"] == pytest.approx(1.0)
    assert summary["warnings"] == result.warnings


def test_phase_inverted_stereo_has_negative_correlation(stereo_phase_inverted, sr):
    result = compute_stereo_correlation(stereo_phase_inverted, sr, _cfg())

    assert len(result.correlation) > 0
    assert np.all(result.correlation <= -0.95)
    assert result.overall_correlation <= -0.95
    assert result.warnings == []


def test_correlated_stereo_has_positive_correlation(stereo_correlated, sr):
    result = compute_stereo_correlation(stereo_correlated, sr, _cfg())

    assert len(result.correlation) > 0
    assert np.all(result.correlation >= 0.95)
    assert result.overall_correlation >= 0.95
    assert result.warnings == []


def test_silent_stereo_reports_undefined_correlation(sr):
    y = np.zeros((sr // 10, 2), dtype=np.float32)

    result = compute_stereo_correlation(y, sr, _cfg())

    assert np.all(np.isnan(result.correlation))
    assert result.overall_correlation is None
    assert len(result.warnings) == 1
    assert "undefined" in result.warnings[0]

    summary = result.to_summary_dict()
    assert summary["defined_frames"] == 0
    assert summary["undefined_frames"] == len(result.correlation)
    assert summary["correlation_min"] is None
    assert summary["correlation_mean"] is None


def test_one_silent_channel_reports_undefined_correlation(sr):
    t = np.arange(sr, dtype=np.float64) / sr
    left = (0.5 * np.sin(2 * np.pi * 1000 * t)).astype(np.float32)
    right = np.zeros_like(left)
    y = np.stack([left, right], axis=1)

    result = compute_stereo_correlation(y, sr, _cfg())

    assert np.all(np.isnan(result.correlation))
    assert result.overall_correlation is None
    assert len(result.warnings) == 1
    assert "undefined" in result.warnings[0]


def test_plot_stereo_correlation_writes_png(tmp_path, stereo_correlated, sr):
    result = compute_stereo_correlation(stereo_correlated, sr, _cfg())
    path = plot_stereo_correlation(result, tmp_path / "stereo.png")

    assert path.exists()
    assert path.stat().st_size > 0
