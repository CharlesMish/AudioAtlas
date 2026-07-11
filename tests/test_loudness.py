"""Tests for short-term LUFS timeline."""

from __future__ import annotations

import numpy as np
import pytest

from audioatlas.analysis.levels import compute_scalar_levels
from audioatlas.analysis.loudness import compute_short_term_lufs
from audioatlas.config import AnalysisConfig
from audioatlas.visualize.loudness import plot_short_term_lufs


def test_short_term_lufs_empty_for_short_audio(sr: int):
    # 1 s < 3 s
    y = np.zeros((sr, 1), dtype=np.float32)
    res = compute_short_term_lufs(y, sr)
    assert len(res.times_seconds) == 0
    assert len(res.lufs) == 0
    assert len(res.warnings) > 0
    assert "shorter than the short-term window" in res.warnings[0]


def test_short_term_lufs_higher_for_louder_signal(sr: int):
    cfg = AnalysisConfig(short_term_lufs_hop_seconds=0.5)
    t = np.arange(int(sr * 4), dtype=np.float64) / sr
    quiet = (0.1 * np.sin(2 * np.pi * 1000 * t))[:, None].astype(np.float32)
    loud = (0.5 * np.sin(2 * np.pi * 1000 * t))[:, None].astype(np.float32)

    quiet_res = compute_short_term_lufs(quiet, sr, cfg)
    loud_res = compute_short_term_lufs(loud, sr, cfg)

    assert len(quiet_res.lufs) > 0
    assert len(loud_res.lufs) > 0
    assert np.median(loud_res.lufs) > np.median(quiet_res.lufs) + 10  # ~14 dB difference expected


def test_short_term_lufs_timeline_increases_for_louder_section(sr: int):
    cfg = AnalysisConfig(short_term_lufs_hop_seconds=0.5)
    t = np.arange(int(sr * 6), dtype=np.float64) / sr
    y = np.zeros((len(t), 1), dtype=np.float32)
    y[: int(sr * 3)] = 0.1 * np.sin(2 * np.pi * 1000 * t[: int(sr * 3)])[:, None]
    y[int(sr * 3) :] = 0.5 * np.sin(2 * np.pi * 1000 * t[int(sr * 3) :])[:, None]
    y = y.astype(np.float32)

    res = compute_short_term_lufs(y, sr, cfg)
    assert len(res.lufs) > 4

    quiet_mask = res.times_seconds <= 3.5
    loud_mask = res.times_seconds >= 5.0
    assert np.count_nonzero(quiet_mask) > 0
    assert np.count_nonzero(loud_mask) > 0
    early_med = float(np.median(res.lufs[quiet_mask]))
    late_med = float(np.median(res.lufs[loud_mask]))
    assert late_med > early_med + 5


def test_short_term_lufs_integrated_reference_matches_scalar_levels(sr: int):
    cfg = AnalysisConfig(short_term_lufs_hop_seconds=0.5, true_peak_oversample=1)
    t = np.arange(int(sr * 5), dtype=np.float64) / sr
    y = (0.3 * np.sin(2 * np.pi * 1000 * t))[:, None].astype(np.float32)

    short_term = compute_short_term_lufs(y, sr, cfg)
    levels = compute_scalar_levels(y, sr, cfg)

    assert short_term.integrated_lufs == pytest.approx(levels.integrated_lufs, abs=1e-6)


def test_short_term_lufs_plot_writes_png_and_handles_empty(tmp_path, sr: int):
    y = np.zeros((sr * 2, 1), dtype=np.float32)  # short
    res = compute_short_term_lufs(y, sr)
    out = tmp_path / "short_lufs.png"
    p = plot_short_term_lufs(res, out)
    assert p.exists()
    assert p.stat().st_size > 1000


def test_short_term_lufs_in_pipeline_summary_and_report(tmp_path, sr: int):
    # Minimal end-to-end via pipeline is covered by higher level tests;
    # here we just confirm the result shape is summary-safe.
    y = (0.3 * np.sin(2 * np.pi * 1000 * np.arange(sr * 5) / sr))[:, None].astype(np.float32)
    res = compute_short_term_lufs(y, sr)
    d = res.to_summary_dict()
    assert d["frames"] > 0
    assert d["lufs_median"] is not None
    assert "warnings" in d
