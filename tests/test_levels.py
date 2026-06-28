from __future__ import annotations

import numpy as np
import pytest

from audioatlas.analysis.levels import (
    compute_crest_factor_timeline,
    compute_peak_timeline,
    compute_rms_envelope,
    compute_scalar_levels,
)
from audioatlas.config import AnalysisConfig
from audioatlas.visualize.waveform import (
    plot_crest_factor_timeline,
    plot_peak_timeline,
    plot_peak_vs_rms,
    plot_rms_histogram,
)


def test_sine_minus_6_dbfs_peak_and_rms(sine_minus_6_dbfs, sr):
    result = compute_scalar_levels(sine_minus_6_dbfs, sr, AnalysisConfig(true_peak_oversample=1))

    assert result.sample_peak_dbfs == pytest.approx(-6.0, abs=0.1)
    # Math-RMS of a sine is peak - 3.01 dB.
    assert result.rms_dbfs == pytest.approx(-9.01, abs=0.15)
    assert result.crest_factor_db == pytest.approx(3.01, abs=0.15)


def test_clipped_sine_counts_clipping(clipped_sine, sr):
    result = compute_scalar_levels(clipped_sine, sr, AnalysisConfig(true_peak_oversample=1))

    assert result.clipped_samples > 0
    assert result.near_clipping_samples >= result.clipped_samples
    assert result.sample_peak_dbfs == pytest.approx(0.0, abs=0.01)


def test_rms_envelope_has_time_axis(sine_minus_6_dbfs, sr):
    cfg = AnalysisConfig(n_fft=2048, hop_length=512, rms_frame_length=2048)
    result = compute_rms_envelope(sine_minus_6_dbfs, sr, cfg)

    assert len(result.times_seconds) == len(result.rms_dbfs)
    assert len(result.rms_dbfs) > 0
    assert np.all(np.isfinite(result.rms_dbfs))


def test_silent_input_respects_db_floor(sr):
    """A silent file should not produce wildly negative dBFS values; the
    configured db_floor should clamp scalar level metrics consistently with
    the RMS envelope floor."""
    cfg = AnalysisConfig(true_peak_oversample=1, db_floor=-100.0)
    silent = np.zeros((sr, 2), dtype=np.float32)
    result = compute_scalar_levels(silent, sr, cfg)

    assert result.sample_peak_dbfs == pytest.approx(cfg.db_floor, abs=0.01)
    assert result.rms_dbfs == pytest.approx(cfg.db_floor, abs=0.01)


def test_true_peak_per_channel_matches_global_and_reflects_asymmetry(sr):
    """The per-channel true-peak fields must exist whenever the global one
    does, be in input channel order, and reflect channel asymmetry. Without
    this, agents have no way to tell a quiet-left / loud-right file from a
    balanced one even though the global scalar is identical for both."""

    # L at -6 dBFS, R at -12 dBFS, both 1 kHz sines.
    duration = 1.0
    t = np.arange(int(sr * duration), dtype=np.float64) / sr
    amp_l = 10 ** (-6.0 / 20.0)
    amp_r = 10 ** (-12.0 / 20.0)
    left = (amp_l * np.sin(2 * np.pi * 1000 * t)).astype(np.float32)
    right = (amp_r * np.sin(2 * np.pi * 1000 * t)).astype(np.float32)
    stereo = np.stack([left, right], axis=1)

    cfg = AnalysisConfig(true_peak_oversample=4)
    result = compute_scalar_levels(stereo, sr, cfg)

    # Symmetry: per-channel field exists exactly when global does.
    assert (result.true_peak_dbtp is None) == (result.true_peak_dbtp_per_channel is None)
    assert (result.true_peak_linear is None) == (result.true_peak_linear_per_channel is None)

    # Shape: one entry per input channel, in input order.
    assert result.true_peak_dbtp_per_channel is not None
    assert len(result.true_peak_dbtp_per_channel) == 2

    ch0, ch1 = result.true_peak_dbtp_per_channel
    assert ch0 == pytest.approx(-6.0, abs=0.3)
    assert ch1 == pytest.approx(-12.0, abs=0.3)

    # The global true peak should be the louder of the two channels.
    assert result.true_peak_dbtp == pytest.approx(max(ch0, ch1), abs=0.01)


def test_true_peak_per_channel_is_none_when_oversample_disabled_and_too_short(sr):
    """Per-channel must follow the same nullability rule as the global value."""
    cfg = AnalysisConfig(true_peak_oversample=4)  # >1 but audio too short
    tiny = np.zeros((4, 2), dtype=np.float32)
    result = compute_scalar_levels(tiny, sr, cfg)
    assert result.true_peak_dbtp is None
    assert result.true_peak_dbtp_per_channel is None
    assert result.true_peak_linear_per_channel is None


def test_crest_factor_timeline_sine_is_near_3_db(sine_minus_6_dbfs, sr):
    cfg = AnalysisConfig(n_fft=2048, hop_length=512, rms_frame_length=2048)
    result = compute_crest_factor_timeline(sine_minus_6_dbfs, sr, cfg)
    rms = compute_rms_envelope(sine_minus_6_dbfs, sr, cfg)

    assert len(result.times_seconds) == len(result.crest_factor_db)
    assert len(result.times_seconds) == len(rms.times_seconds)
    finite = result.crest_factor_db[np.isfinite(result.crest_factor_db)]
    assert len(finite) > 0
    assert float(np.median(finite)) == pytest.approx(3.01, abs=0.2)


def test_crest_factor_timeline_impulse_is_higher_than_sine(sine_minus_6_dbfs, sr):
    cfg = AnalysisConfig(n_fft=2048, hop_length=512, rms_frame_length=2048)
    clicks = np.zeros((sr * 2, 1), dtype=np.float32)
    click_len = max(1, int(0.002 * sr))
    for start in np.arange(0.1, 2.0, 0.125):
        idx = int(start * sr)
        clicks[idx : idx + click_len, 0] = 0.8

    sine_result = compute_crest_factor_timeline(sine_minus_6_dbfs, sr, cfg)
    click_result = compute_crest_factor_timeline(clicks, sr, cfg)
    sine_median = float(np.median(sine_result.crest_factor_db[np.isfinite(sine_result.crest_factor_db)]))
    click_median = float(np.median(click_result.crest_factor_db[np.isfinite(click_result.crest_factor_db)]))

    assert click_median > sine_median


def test_crest_factor_timeline_silence_is_nan_safe(sr):
    cfg = AnalysisConfig(n_fft=2048, hop_length=512, rms_frame_length=2048)
    silent = np.zeros((sr, 1), dtype=np.float32)

    result = compute_crest_factor_timeline(silent, sr, cfg)
    summary = result.to_summary_dict()

    assert summary["crest_factor_db_min"] is None
    assert summary["crest_factor_db_median"] is None
    assert summary["crest_factor_db_max"] is None
    assert result.warnings
    assert not np.any(np.isfinite(result.crest_factor_db))


def test_plot_crest_factor_timeline_writes_png(tmp_path, sine_minus_6_dbfs, sr):
    cfg = AnalysisConfig(n_fft=2048, hop_length=512, rms_frame_length=2048)
    result = compute_crest_factor_timeline(sine_minus_6_dbfs, sr, cfg)
    path = plot_crest_factor_timeline(result, tmp_path / "crest_factor_timeline.png")

    assert path.exists()
    assert path.stat().st_size > 0


def test_peak_timeline_finds_near_clipping_bursts(sr):
    cfg = AnalysisConfig(n_fft=100, hop_length=100, true_peak_oversample=1)
    y = np.zeros((1_000, 1), dtype=np.float32)
    y[200:250, 0] = 0.995
    y[700:720, 0] = -0.995

    result = compute_peak_timeline(y, sr, cfg)

    assert result.near_clipping_counts[2] == 50
    assert result.near_clipping_counts[7] == 20
    assert np.count_nonzero(result.near_clipping_counts) == 2
    summary = result.to_summary_dict()
    assert summary["frames_with_near_clipping"] == 2
    assert summary["near_clipping_counts"][2] == 50
    assert summary["near_clipping_counts"][7] == 20
    assert len(result.near_clipping_time_ranges) == 2
    assert result.near_clipping_time_ranges[0]["start"] == pytest.approx(200 / sr)
    assert result.near_clipping_time_ranges[0]["end"] == pytest.approx(300 / sr)
    assert result.near_clipping_time_ranges[0]["duration"] == pytest.approx(100 / sr)
    assert result.near_clipping_time_ranges[1]["start"] == pytest.approx(700 / sr)
    assert result.near_clipping_time_ranges[1]["end"] == pytest.approx(800 / sr)
    assert result.near_clipping_time_ranges[1]["duration"] == pytest.approx(100 / sr)


def test_peak_timeline_records_frame_peak_dbfs_for_minus_6_dbfs_sine(
    sine_minus_6_dbfs, sr
):
    cfg = AnalysisConfig(n_fft=2048, hop_length=512, rms_frame_length=2048, db_floor=-100.0)

    result = compute_peak_timeline(sine_minus_6_dbfs, sr, cfg)
    summary = result.to_summary_dict()

    assert len(result.frame_peak_linear) == len(result.times_seconds)
    assert len(result.frame_peak_dbfs) == len(result.times_seconds)
    assert float(np.max(result.frame_peak_dbfs)) == pytest.approx(-6.0, abs=0.25)
    assert "frame_peak_linear" in summary
    assert "frame_peak_dbfs" in summary
    assert max(summary["frame_peak_dbfs"]) == pytest.approx(-6.0, abs=0.25)


def test_peak_timeline_silence_clamps_frame_peak_dbfs_to_floor(sr):
    cfg = AnalysisConfig(n_fft=2048, hop_length=512, rms_frame_length=2048, db_floor=-96.0)
    silent = np.zeros((sr, 1), dtype=np.float32)

    result = compute_peak_timeline(silent, sr, cfg)

    assert np.all(result.frame_peak_linear == 0.0)
    assert np.allclose(result.frame_peak_dbfs, cfg.db_floor)


def test_new_peak_and_rms_distribution_plots_write_png(tmp_path, sine_minus_6_dbfs, sr):
    cfg = AnalysisConfig(n_fft=2048, hop_length=512, rms_frame_length=2048)
    peaks = compute_peak_timeline(sine_minus_6_dbfs, sr, cfg)
    rms = compute_rms_envelope(sine_minus_6_dbfs, sr, cfg)

    paths = [
        plot_peak_timeline(peaks, tmp_path / "peak_timeline.png", cfg),
        plot_peak_vs_rms(peaks, rms, tmp_path / "peak_vs_rms.png", cfg),
        plot_rms_histogram(rms, tmp_path / "rms_histogram.png", cfg),
    ]

    for path in paths:
        assert path.exists()
        assert path.stat().st_size > 0
