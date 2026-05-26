"""Smoke tests for the Markdown + JSON report.

Goal: lock in the *shape* of the output so agents adding new metrics don't
silently break the contract. These tests are intentionally not strict about
exact wording - just structure and presence of key sections.
"""

from __future__ import annotations

import json
from pathlib import Path

from audioatlas.report import LEVEL_METRIC_DISPLAY, write_report_md, write_summary_json


def _make_summary() -> dict:
    return {
        "schema_version": "0.1.0",
        "metadata": {
            "filename": "test.wav",
            "samplerate": 48000,
            "channels": 2,
            "format": "WAV",
            "subtype": "PCM_16",
        },
        "analysis_config": {"n_fft": 4096, "hop_length": 1024},
        "levels": {
            "duration_seconds": 65.5,
            "sample_peak_dbfs": -0.2,
            "true_peak_dbtp": -0.1,
            "rms_dbfs": -14.3,
            "crest_factor_db": 14.1,
            "integrated_lufs": -10.8,
            "plr_db": 10.7,
            "clipped_samples": 0,
            "near_clipping_samples": 342,
            "dc_offset_per_channel": [0.0001, -0.0002],
            "peak_dbfs_per_channel": [-0.21, -0.25],
            "rms_dbfs_per_channel": [-14.5, -14.1],
            "true_peak_linear_per_channel": [0.977, 0.973],
            "true_peak_dbtp_per_channel": [-0.20, -0.24],
            "warnings": ["test warning for rendering"],
        },
        "rms_envelope": {
            "frames": 100,
            "rms_dbfs_min": -30.0,
            "rms_dbfs_max": -10.0,
            "rms_dbfs_mean": -14.5,
        },
        "average_spectrum": {
            "nperseg": 8192,
            "bins": 4097,
            "strongest_bin_hz": 1000.0,
            "strongest_bin_db": -12.0,
        },
        "stereo_correlation": {
            "frame_length": 4096,
            "hop_length": 1024,
            "frames": 100,
            "correlation_min": 0.9,
            "correlation_max": 1.0,
            "correlation_mean": 0.98,
            "correlation_median": 0.99,
            "overall_correlation": 0.98,
            "warnings": [],
        },
        "plots": [
            "01_waveform_rms.png",
            "02_rms_timeline.png",
            "06_stereo_correlation.png",
        ],
    }


def test_write_summary_json_roundtrips(tmp_path: Path):
    summary = _make_summary()
    path = write_summary_json(summary, tmp_path)
    assert path.name == "summary.json"
    assert path.exists()

    parsed = json.loads(path.read_text(encoding="utf-8"))
    assert parsed["schema_version"] == "0.1.0"
    assert parsed["levels"]["integrated_lufs"] == -10.8
    assert parsed["plots"] == summary["plots"]


def test_write_report_md_contains_expected_sections(tmp_path: Path):
    summary = _make_summary()
    plot_files = ["01_waveform_rms.png", "02_rms_timeline.png"]
    path = write_report_md(summary, plot_files, tmp_path)
    assert path.name == "report.md"
    text = path.read_text(encoding="utf-8")

    # Top-level headings
    assert "# AudioAtlas Report: test.wav" in text
    assert "## File" in text
    assert "## Level metrics" in text
    assert "## Per-channel breakdown" in text
    assert "## Warnings / caveats" in text
    assert "## RMS envelope summary" in text
    assert "## Average spectrum summary" in text
    assert "## Stereo correlation summary" in text
    assert "## Plots" in text
    assert "## Human notes" in text


def test_report_per_channel_section_has_one_column_per_channel(tmp_path: Path):
    summary = _make_summary()
    path = write_report_md(summary, summary["plots"], tmp_path)
    text = path.read_text(encoding="utf-8")
    # Two channels in the test fixture -> ch 0 and ch 1 headers must appear.
    assert "ch 0" in text and "ch 1" in text
    # True-peak per channel must be present in the per-channel section.
    assert "True-peak (approx.)" in text


def test_report_omits_per_channel_section_when_arrays_missing(tmp_path: Path):
    summary = _make_summary()
    # Strip every per-channel array.
    for key in (
        "dc_offset_per_channel",
        "peak_dbfs_per_channel",
        "rms_dbfs_per_channel",
        "true_peak_linear_per_channel",
        "true_peak_dbtp_per_channel",
    ):
        summary["levels"][key] = None
    path = write_report_md(summary, summary["plots"], tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "## Per-channel breakdown" not in text


def test_report_includes_all_documented_metrics(tmp_path: Path):
    summary = _make_summary()
    path = write_report_md(summary, summary["plots"], tmp_path)
    text = path.read_text(encoding="utf-8")
    # The display table should list every metric we registered.
    for _key, label, _unit in LEVEL_METRIC_DISPLAY:
        assert label in text, f"Missing label in report.md: {label}"


def test_report_does_not_make_verdicts(tmp_path: Path):
    """AudioAtlas must not produce judgmental language. See AGENT_BRIEF.md."""
    summary = _make_summary()
    path = write_report_md(summary, summary["plots"], tmp_path)
    text = path.read_text(encoding="utf-8").lower()
    banned = ["mix is bad", "fix your mud", "well mastered", "needs more", "too loud", "mix health"]
    for phrase in banned:
        assert phrase not in text, f"Banned verdict phrase appeared in report.md: {phrase!r}"


def test_report_renders_plot_links_in_order(tmp_path: Path):
    summary = _make_summary()
    plot_files = ["01_waveform_rms.png", "02_rms_timeline.png"]
    path = write_report_md(summary, plot_files, tmp_path)
    text = path.read_text(encoding="utf-8")
    idx_a = text.index("01_waveform_rms.png")
    idx_b = text.index("02_rms_timeline.png")
    assert idx_a < idx_b


def test_report_handles_missing_optional_metrics(tmp_path: Path):
    summary = _make_summary()
    # Wipe out the optionals that are legitimately None in some files
    summary["levels"]["integrated_lufs"] = None
    summary["levels"]["plr_db"] = None
    summary["levels"]["true_peak_dbtp"] = None
    path = write_report_md(summary, summary["plots"], tmp_path)
    text = path.read_text(encoding="utf-8")
    # em dash placeholder must appear at least once
    assert "—" in text
