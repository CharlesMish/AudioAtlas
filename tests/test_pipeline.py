from __future__ import annotations

import json
import re
from dataclasses import asdict

import numpy as np
import soundfile as sf

from audioatlas.config import AnalysisConfig
from audioatlas.graphs import all_graphs
from audioatlas.graphs.selection import GraphSelection
from audioatlas.pipeline import analyze_file


def test_pipeline_writes_expected_outputs(tmp_path, sr):
    path = tmp_path / "song.wav"
    t = np.arange(sr, dtype=np.float64) / sr
    y = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sf.write(path, y, sr)

    result = analyze_file(path, tmp_path / "report", config=AnalysisConfig(n_fft=1024, hop_length=256, rms_frame_length=1024, welch_nperseg=1024, true_peak_oversample=1))

    assert result.summary_path.exists()
    assert result.findings_path.exists()
    assert result.report_path.exists()
    assert result.html_report_path.exists()
    assert result.html_report_path.name == "report.html"
    for plot_path in result.plot_paths:
        assert plot_path.exists()

    summary = json.loads(result.summary_path.read_text())
    findings = json.loads(result.findings_path.read_text())
    html = result.html_report_path.read_text(encoding="utf-8")
    assert "levels" in summary
    assert "metadata" in summary
    assert "peak_timeline" in summary
    assert "band_energies" in summary["average_spectrum"]
    assert "spectral_shape" in summary
    assert "band_energy_timeline" in summary
    assert "onset_density" in summary
    assert "chroma_cqt" in summary
    assert "short_term_lufs" in summary
    assert "stereo_correlation" in summary
    assert "mid_side_energy" in summary
    assert "crest_factor_timeline" in summary
    selected_graphs = GraphSelection().resolve(all_graphs())
    expected_plots = [graph.filename for graph in selected_graphs]
    assert summary["plots"] == expected_plots
    assert summary["graphs"] == {
        "profile": "standard",
        "selected": [graph.key for graph in selected_graphs],
        "available": [graph.key for graph in all_graphs()],
        "selected_filenames": expected_plots,
    }
    assert len(summary["plots"]) == 14
    assert "findings" in findings
    assert "Findings" in html
    assert "Key metrics" in html
    assert "waveform_rms.png" in html
    image_srcs = re.findall(r'<img src="([^"]+)"', html)
    assert sorted(image_srcs) == sorted(expected_plots)
    for src in image_srcs:
        assert "://" not in src
        assert not src.startswith(("/", "\\"))
        assert (result.out_dir / src).exists()
    assert findings["count"] == len(result.findings["findings"])
    all_titles = [item["title"] for item in findings["all_findings"]]
    assert len(all_titles) <= 4
    assert not any("band energy" in title.lower() for title in all_titles)


def test_pipeline_reduced_graph_selection_keeps_summary_complete(tmp_path, sr):
    path = tmp_path / "song.wav"
    t = np.arange(sr, dtype=np.float64) / sr
    y = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sf.write(path, y, sr)
    cfg = AnalysisConfig(
        n_fft=1024,
        hop_length=256,
        rms_frame_length=1024,
        welch_nperseg=1024,
        true_peak_oversample=1,
    )

    result = analyze_file(
        path,
        tmp_path / "report",
        config=cfg,
        selection=GraphSelection(profile="minimal"),
    )

    assert result.summary["plots"] == [
        "waveform_rms.png",
        "rms_timeline.png",
        "log_spectrogram.png",
        "sample_histogram.png",
    ]
    assert result.summary["graphs"] == {
        "profile": "minimal",
        "selected": ["waveform_rms", "rms_timeline", "log_spectrogram", "sample_histogram"],
        "available": [graph.key for graph in all_graphs()],
        "selected_filenames": [
            "waveform_rms.png",
            "rms_timeline.png",
            "log_spectrogram.png",
            "sample_histogram.png",
        ],
    }
    assert result.summary["analysis_config"] == asdict(cfg)
    for block in [
        "levels",
        "rms_envelope",
        "crest_factor_timeline",
        "peak_timeline",
        "average_spectrum",
        "spectral_shape",
        "band_energy_timeline",
        "onset_density",
        "chroma_cqt",
        "short_term_lufs",
        "stereo_correlation",
        "mid_side_energy",
    ]:
        assert block in result.summary
    assert "frame_peak_dbfs" in result.summary["peak_timeline"]
    assert "frame_peak_linear" in result.summary["peak_timeline"]
