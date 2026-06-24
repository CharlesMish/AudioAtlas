from __future__ import annotations

import json
import re

import numpy as np
import soundfile as sf

from audioatlas.config import AnalysisConfig
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
    assert len(summary["plots"]) == 13
    assert "03_crest_factor_timeline.png" in summary["plots"]
    assert "07_stereo_correlation.png" in summary["plots"]
    assert "08_mid_side_energy.png" in summary["plots"]
    assert "09_spectral_shape.png" in summary["plots"]
    assert "10_band_energy_timeline.png" in summary["plots"]
    assert "11_onset_density.png" in summary["plots"]
    assert "12_chroma_cqt.png" in summary["plots"]
    assert "13_short_term_lufs.png" in summary["plots"]
    assert "findings" in findings
    assert "Findings" in html
    assert "Key metrics" in html
    assert "01_waveform_rms.png" in html
    image_srcs = re.findall(r'<img src="([^"]+)"', html)
    assert len(image_srcs) == 13
    assert sorted(image_srcs) == sorted(summary["plots"])
    for src in image_srcs:
        assert "://" not in src
        assert not src.startswith(("/", "\\"))
        assert (result.out_dir / src).exists()
    assert findings["count"] == len(result.findings["findings"])
    all_titles = [item["title"] for item in findings["all_findings"]]
    assert len(all_titles) <= 4
    assert not any("band energy" in title.lower() for title in all_titles)
