from __future__ import annotations

import json

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
    for plot_path in result.plot_paths:
        assert plot_path.exists()

    summary = json.loads(result.summary_path.read_text())
    findings = json.loads(result.findings_path.read_text())
    assert "levels" in summary
    assert "metadata" in summary
    assert "peak_timeline" in summary
    assert "band_energies" in summary["average_spectrum"]
    assert "spectral_shape" in summary
    assert "band_energy_timeline" in summary
    assert "onset_density" in summary
    assert "stereo_correlation" in summary
    assert "mid_side_energy" in summary
    assert len(summary["plots"]) == 10
    assert "06_stereo_correlation.png" in summary["plots"]
    assert "07_mid_side_energy.png" in summary["plots"]
    assert "08_spectral_shape.png" in summary["plots"]
    assert "09_band_energy_timeline.png" in summary["plots"]
    assert "10_onset_density.png" in summary["plots"]
    assert "findings" in findings
    assert findings["count"] == len(result.findings["findings"])
    all_titles = [item["title"] for item in findings["all_findings"]]
    assert len(all_titles) <= 4
    assert not any("band energy" in title.lower() for title in all_titles)
