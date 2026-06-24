from __future__ import annotations

import numpy as np

from audioatlas.analysis.tonal import PITCH_CLASSES, compute_chroma_cqt
from audioatlas.config import AnalysisConfig
from audioatlas.visualize.chroma import plot_chroma_cqt


def test_chroma_cqt_a4_sine_peaks_on_a(sr):
    cfg = AnalysisConfig(hop_length=1024)
    t = np.arange(sr * 2, dtype=np.float64) / sr
    y = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)[:, None]

    result = compute_chroma_cqt(y, sr, cfg)
    summary = result.to_summary_dict()

    assert result.chroma.shape[0] == 12
    assert result.chroma.shape[1] == len(result.times_seconds)
    assert len(result.times_seconds) > 0
    assert summary["dominant_pitch_class"] == "A"
    assert PITCH_CLASSES.index(summary["dominant_pitch_class"]) == 9


def test_chroma_cqt_c_major_triad_elevates_c_e_g(sr):
    cfg = AnalysisConfig(hop_length=1024)
    t = np.arange(sr * 2, dtype=np.float64) / sr
    y = (
        0.3 * np.sin(2 * np.pi * 261.63 * t)
        + 0.3 * np.sin(2 * np.pi * 329.63 * t)
        + 0.3 * np.sin(2 * np.pi * 392.0 * t)
    ).astype(np.float32)[:, None]

    result = compute_chroma_cqt(y, sr, cfg)
    mean_chroma = np.asarray(result.to_summary_dict()["mean_chroma"], dtype=np.float64)
    top_three = {
        PITCH_CLASSES[idx]
        for idx in np.argsort(mean_chroma)[-3:]
    }

    assert top_three == {"C", "E", "G"}


def test_chroma_cqt_silence_is_safe(sr):
    cfg = AnalysisConfig(hop_length=1024)
    silent = np.zeros((sr, 1), dtype=np.float32)

    result = compute_chroma_cqt(silent, sr, cfg)
    summary = result.to_summary_dict()

    assert summary["dominant_pitch_class"] is None
    assert summary["warnings"]
    assert np.allclose(result.chroma, 0.0)


def test_plot_chroma_cqt_writes_png(tmp_path, sr):
    cfg = AnalysisConfig(hop_length=1024)
    t = np.arange(sr, dtype=np.float64) / sr
    y = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)[:, None]
    result = compute_chroma_cqt(y, sr, cfg)

    path = plot_chroma_cqt(result, tmp_path / "chroma_cqt.png")

    assert path.exists()
    assert path.stat().st_size > 0