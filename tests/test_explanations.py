"""Explanation coverage and empirical validation of the selected-range time origin."""
from __future__ import annotations

import copy
from html import escape
from pathlib import Path

import numpy as np
import soundfile as sf

from audioatlas.analysis.bundle import _COMPUTE, AnalysisBundle
from audioatlas.analysis.findings import generate_findings
from audioatlas.config import AnalysisConfig
from audioatlas.execution import SUMMARY_BLOCKS
from audioatlas.explanations import ANALYZED_SCOPE_NOTE, RANGE_TIME_NOTE, measurement_note
from audioatlas.html_report import write_report_html
from audioatlas.io import load_audio
from audioatlas.report import write_report_md


def test_shared_explanations_and_range_context_preserve_measurement_inputs(tmp_path: Path):
    summary = {
        "metadata": {"filename": "range.wav", "source_start_seconds": 10.0,
                     "source_end_seconds": 14.0, "source_duration_seconds": 16.0},
        "levels": {}, "rms_envelope": {"frames": 5},
        **{key: {"frames": 5} for key in (
            "crest_factor_timeline", "average_spectrum", "spectral_shape",
            "onset_density", "chroma_cqt", "short_term_lufs",
            "stereo_correlation", "mid_side_energy",
        )},
    }
    before = copy.deepcopy(summary)
    html = write_report_html(summary, [], tmp_path).read_text()
    md = write_report_md(summary, [], tmp_path).read_text()
    assert summary == before
    for text in (ANALYZED_SCOPE_NOTE, RANGE_TIME_NOTE):
        assert text in md
        assert escape(text) in html
    for key in ("rms", "crest-factor", "average-spectrum", "spectral-centroid",
                "rolloff", "spectral-bandwidth", "onset-density", "chroma-cqt",
                "short-term-lufs", "stereo-correlation", "side-mid-ratio"):
        text = measurement_note(key)
        assert text in md
        assert escape(text) in html
    summary["metadata"].update(source_start_seconds=0.0, source_end_seconds=16.0)
    assert RANGE_TIME_NOTE not in write_report_md(summary, [], tmp_path).read_text()
    assert RANGE_TIME_NOTE not in write_report_html(summary, [], tmp_path).read_text()


def test_range_time_origin_matches_standalone_slice_for_all_families(tmp_path: Path):
    sr = 22050
    t = np.arange(16 * sr) / sr
    left = 0.4 * np.sin(2 * np.pi * 440 * t)
    right = left.copy()
    right[(t >= 11) & (t < 13)] *= -1
    stereo = np.column_stack((left, right))
    source = tmp_path / "source.wav"
    sf.write(source, stereo, sr, subtype="DOUBLE")
    cropped = load_audio(source, start_seconds=10.0, end_seconds=14.0)
    standalone = tmp_path / "slice.wav"
    sf.write(standalone, cropped.y, sr, subtype="DOUBLE")
    sliced = load_audio(standalone)
    cfg = AnalysisConfig(n_fft=1024, rms_frame_length=1024, hop_length=256,
                         welch_nperseg=1024, true_peak_oversample=1)
    bundles = (AnalysisBundle(cropped, cfg), AnalysisBundle(sliced, cfg))
    blocks = [{}, {}]
    time_families = []
    for name in _COMPUTE:
        results = [bundle.get(name) for bundle in bundles]
        for attr, value in vars(results[0]).items():
            other = getattr(results[1], attr)
            if isinstance(value, np.ndarray):
                assert value.dtype == other.dtype
                assert value.shape == other.shape
                assert value.tobytes() == other.tobytes(), (name, attr)
        if hasattr(results[0], "times_seconds"):
            times = results[0].times_seconds
            assert len(times) > 0
            assert 0 <= times.min() < 4.0
            assert times.max() <= 4.0 + cfg.hop_length / sr
            time_families.append(name)
        for i, result in enumerate(results):
            if name in SUMMARY_BLOCKS:
                blocks[i][SUMMARY_BLOCKS[name]] = (
                    result.to_dict() if name == "levels" else result.to_summary_dict()
                )
    assert len(time_families) == 11
    findings = [generate_findings(block).to_dict() for block in blocks]
    assert findings[0] == findings[1]
    ranges = [region for finding in findings[0]["findings"]
              for region in finding.get("time_ranges", [])]
    assert ranges  # Exercise a real finding, not just the empty-findings case.
    assert all(0 <= region["start"] <= region["end"] <= 4.1 for region in ranges)


def test_user_guide_explains_scope_and_scale_without_reclassifying_measurements():
    guide = (Path(__file__).resolve().parents[1] / "docs" / "USER_GUIDE.md").read_text()
    for phrase in (
        "plot and finding times start from that range",
        "RMS** measures amplitude, not energy",
        "crest timeline is not derived from the mono RMS timeline",
        "0 relative dB", "85% or 95% of summed magnitude",
        "independently normalized", "not exact note pitch (F0)",
        "Neither metric\n  directly measures perceived width",
    ):
        assert phrase in guide
