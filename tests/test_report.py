"""Smoke tests for the Markdown + JSON report.

Goal: lock in the *shape* of the output so agents adding new metrics don't
silently break the contract. These tests are intentionally not strict about
exact wording - just structure and presence of key sections.
"""

from __future__ import annotations

import json
from pathlib import Path

from audioatlas.report import (
    LEVEL_METRIC_DISPLAY,
    write_findings_json,
    write_report_md,
    write_summary_json,
)


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
            "strongest_band": "mid",
            "band_energies": {
                "bass": {"low_hz": 60.0, "high_hz": 120.0, "energy_db": -18.0},
                "mid": {"low_hz": 350.0, "high_hz": 2000.0, "energy_db": -6.0},
            },
        },
        "stereo_correlation": {
            "frame_length": 4096,
            "hop_length": 1024,
            "frames": 100,
            "defined_frames": 100,
            "undefined_frames": 0,
            "correlation_min": 0.9,
            "correlation_max": 1.0,
            "correlation_mean": 0.98,
            "correlation_median": 0.99,
            "overall_correlation": 0.98,
            "correlation_below_0_time_ranges": [],
            "correlation_below_0_3_time_ranges": [],
            "warnings": [],
        },
        "mid_side_energy": {
            "frame_length": 4096,
            "hop_length": 1024,
            "frames": 100,
            "mid_rms_dbfs_min": -20.0,
            "mid_rms_dbfs_max": -10.0,
            "mid_rms_dbfs_mean": -14.0,
            "side_rms_dbfs_min": -40.0,
            "side_rms_dbfs_max": -25.0,
            "side_rms_dbfs_mean": -30.0,
            "side_to_mid_ratio_db_median": -16.0,
            "side_to_mid_ratio_db_mean": -15.5,
            "undefined_ratio_frames": 0,
            "side_to_mid_ratio_above_minus_6_time_ranges": [],
            "warnings": [],
        },
        "peak_timeline": {
            "frame_length": 4096,
            "hop_length": 1024,
            "frames": 100,
            "near_clipping_time_ranges": [],
        },
        "spectral_shape": {
            "n_fft": 4096,
            "hop_length": 1024,
            "frames": 100,
            "valid_frames": 100,
            "undefined_frames": 0,
            "centroid_mean_hz": 2200.0,
            "centroid_median_hz": 2000.0,
            "centroid_min_hz": 900.0,
            "centroid_max_hz": 5000.0,
            "rolloff_85_median_hz": 5000.0,
            "rolloff_95_median_hz": 9000.0,
            "bandwidth_median_hz": 1500.0,
            "centroid_elevated_threshold_hz": 3000.0,
            "centroid_reduced_threshold_hz": 1000.0,
            "centroid_large_shift_threshold_hz": 2000.0,
            "centroid_elevated_time_ranges": [],
            "centroid_reduced_time_ranges": [],
            "centroid_large_shift_time_ranges": [],
            "warnings": [],
        },
        "plots": [
            "01_waveform_rms.png",
            "02_rms_timeline.png",
            "06_stereo_correlation.png",
            "07_mid_side_energy.png",
            "08_spectral_shape.png",
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


def test_write_findings_json_roundtrips(tmp_path: Path):
    findings = {
        "count": 1,
        "findings": [
            {
                "severity": "info",
                "category": "spectrum",
                "title": "Test finding",
                "measured_value": 220.0,
                "threshold": 120.0,
                "unit": "Hz",
                "evidence": "test evidence",
                "why_it_matters": "test context",
                "suggested_checks": ["inspect the plot"],
                "time_ranges": [],
                "confidence": "medium",
            }
        ],
    }
    path = write_findings_json(findings, tmp_path)
    assert path.name == "findings.json"
    parsed = json.loads(path.read_text(encoding="utf-8"))
    assert parsed == findings


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
    assert "## Frame RMS envelope summary" in text
    assert "## Average spectrum summary" in text
    assert "## Band energy summary" in text
    assert "## Spectral shape summary" in text
    assert "## Stereo correlation summary" in text
    assert "## Mid/side energy summary" in text
    assert "## Plots" in text
    assert "## Human notes" in text


def test_write_report_md_contains_findings_section(tmp_path: Path):
    summary = _make_summary()
    findings = {
        "count": 1,
        "findings": [
            {
                "severity": "warning",
                "category": "levels",
                "title": "Near-full-scale samples detected",
                "measured_value": 12,
                "threshold": 0,
                "unit": "samples",
                "evidence": "near_clipping_samples measured 12.",
                "why_it_matters": "Measured sample values are near full scale.",
                "suggested_checks": ["Inspect the sample histogram."],
                "time_ranges": [{"start": 1.0, "end": 1.5, "duration": 0.5}],
                "confidence": "high",
            }
        ],
    }
    path = write_report_md(summary, summary["plots"], tmp_path, findings)
    text = path.read_text(encoding="utf-8")
    assert "## Findings" in text
    assert "Near-full-scale samples detected" in text
    assert "Suggested checks" in text
    assert "Time ranges" in text
    assert "1.000s-1.500s" in text


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
    findings = {
        "count": 1,
        "findings": [
            {
                "severity": "info",
                "category": "spectrum",
                "title": "Strongest average-spectrum bin is in the low-mid region",
                "measured_value": 220.0,
                "threshold": 120,
                "unit": "Hz",
                "evidence": "strongest_bin_hz measured 220.000 Hz.",
                "why_it_matters": "This identifies where the strongest bin falls.",
                "suggested_checks": ["Inspect the average spectrum plot."],
                "time_ranges": [],
                "confidence": "medium",
            }
        ],
    }
    path = write_report_md(summary, summary["plots"], tmp_path, findings)
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
