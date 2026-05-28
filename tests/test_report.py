"""Smoke tests for the Markdown + JSON report.

Goal: lock in the *shape* of the output so agents adding new metrics don't
silently break the contract. These tests are intentionally not strict about
exact wording - just structure and presence of key sections.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from audioatlas.html_report import write_report_html
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
        "analysis_config": {"n_fft": 4096, "hop_length": 1024, "report_max_time_ranges": 8},
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
            "correlation_below_0_time_ranges": [
                {"start": 1.0, "end": 1.5, "duration": 0.5}
            ],
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
        "band_energy_timeline": {
            "n_fft": 4096,
            "hop_length": 1024,
            "frames": 100,
            "valid_frames": 100,
            "undefined_frames": 0,
            "band_names": ["bass", "mid"],
            "strongest_band_by_median": "mid",
            "bands": {
                "bass": {
                    "median_db": -20.0,
                    "mean_db": -21.0,
                    "min_db": -40.0,
                    "max_db": -10.0,
                    "elevated_threshold_db": -14.0,
                    "reduced_threshold_db": -32.0,
                    "elevated_time_ranges": [],
                    "reduced_time_ranges": [],
                },
                "mid": {
                    "median_db": -8.0,
                    "mean_db": -9.0,
                    "min_db": -20.0,
                    "max_db": -2.0,
                    "elevated_threshold_db": -2.0,
                    "reduced_threshold_db": -20.0,
                    "elevated_time_ranges": [],
                    "reduced_time_ranges": [],
                },
            },
            "warnings": [],
        },
        "onset_density": {
            "hop_length": 1024,
            "frames": 100,
            "smoothing_window_seconds": 1.0,
            "smoothing_window_frames": 47,
            "onset_strength_mean": 0.2,
            "onset_strength_median": 0.1,
            "onset_strength_max": 1.0,
            "onset_density_mean": 0.25,
            "onset_density_median": 0.2,
            "onset_density_max": 0.8,
            "high_onset_density_threshold": 0.35,
            "high_onset_density_time_ranges": [],
            "strongest_onset_density_time": 12.0,
            "warnings": [],
        },
        "plots": [
            "01_waveform_rms.png",
            "02_rms_timeline.png",
            "03_log_spectrogram.png",
            "04_average_spectrum.png",
            "05_sample_histogram.png",
            "06_stereo_correlation.png",
            "07_mid_side_energy.png",
            "08_spectral_shape.png",
            "09_band_energy_timeline.png",
            "10_onset_density.png",
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
    assert "## Band energy timeline summary" in text
    assert "## Onset / transient density summary" in text
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
                "does_not_mean": "This does not mean the passage is clipped.",
                "suggested_checks": ["Inspect the sample histogram."],
                "time_ranges": [{"start": 1.0, "end": 1.5, "duration": 0.5}],
                "confidence": "high",
            }
        ],
    }
    path = write_report_md(summary, summary["plots"], tmp_path, findings)
    text = path.read_text(encoding="utf-8")
    assert "## Findings" in text
    assert "## Listening prompts" not in text
    assert (
        "Findings are measurement-based observations derived from the analysis. "
        "They highlight values or regions worth checking by ear; they are not quality judgments."
    ) in text
    assert "Brief low-correlation events can be normal for panned effects" in text
    assert "Near-full-scale samples detected" in text
    assert "Prompt level: worth a listen" in text
    assert "Does not mean: This does not mean the passage is clipped." in text
    assert "Suggested listening checks" in text
    assert "Time ranges" in text
    assert "1.000s-1.500s" in text


def test_report_truncates_many_time_ranges(tmp_path: Path):
    summary = _make_summary()
    ranges = [
        {"start": float(i), "end": float(i) + 0.2, "duration": 0.2}
        for i in range(12)
    ]
    findings = {
        "count": 1,
        "findings_shown": [
            {
                "severity": "warning",
                "category": "levels",
                "title": "Near-full-scale samples detected",
                "measured_value": 1482,
                "threshold": 0,
                "unit": "samples",
                "evidence": "near_clipping_samples measured 1482.",
                "why_it_matters": "Measured sample values are near full scale.",
                "suggested_checks": ["Inspect the sample histogram."],
                "time_ranges": ranges,
                "confidence": "high",
            }
        ],
    }

    path = write_report_md(summary, summary["plots"], tmp_path, findings)
    text = path.read_text(encoding="utf-8")

    assert "Time ranges: 12 regions" in text
    assert "total 2.400s" in text
    assert "longest 0.200s" in text
    assert "Showing 5 example range(s)" in text
    assert "0.000s-0.200s" in text
    assert "1.000s-1.200s" in text
    assert "4.000s-4.200s" in text
    assert "5.000s-5.200s" not in text
    assert "see findings.json for full ranges" in text


def test_findings_json_preserves_full_time_ranges(tmp_path: Path):
    ranges = [
        {"start": float(i), "end": float(i) + 0.2, "duration": 0.2}
        for i in range(12)
    ]
    findings = {
        "count": 1,
        "findings": [{"title": "Test", "time_ranges": ranges}],
    }

    path = write_findings_json(findings, tmp_path)
    parsed = json.loads(path.read_text(encoding="utf-8"))

    assert len(parsed["findings"][0]["time_ranges"]) == 12
    assert parsed["findings"][0]["time_ranges"][-1]["start"] == 11.0


def test_report_md_renders_grouped_stereo_evidence_as_bullets_and_deduped_ranges(
    tmp_path: Path,
):
    summary = _make_summary()
    findings = {
        "count": 1,
        "findings_shown": [
            {
                "severity": "warning",
                "category": "stereo",
                "title": "Stereo field shows sustained low-correlation / side-heavy regions",
                "measured_value": 0.35,
                "threshold": 0.5,
                "unit": "mixed stereo metrics",
                "evidence": "summary evidence",
                "evidence_items": [
                    "Median L/R correlation: 0.350.",
                    "Minimum frame correlation: -0.400.",
                    "Total time below 0 correlation: 5.000 seconds across 1 region(s).",
                    "Total time below 0.3 correlation: 20.000 seconds across 1 region(s).",
                    "Median side/mid ratio: -4.000 dB.",
                ],
                "why_it_matters": "Mono playback may change tone or apparent width.",
                "does_not_mean": "This does not mean the stereo image is incorrect.",
                "suggested_checks": [
                    "Inspect the stereo correlation timeline around the lowest-correlation regions.",
                    "Listen in mono around sustained low-correlation regions if mono compatibility matters.",
                    "Inspect the mid/side energy plot around side-heavy regions.",
                ],
                "time_ranges": [
                    {"start": 10.0, "end": 30.0, "duration": 20.0},
                ],
                "confidence": "medium",
            }
        ],
    }
    path = write_report_md(summary, summary["plots"], tmp_path, findings)
    text = path.read_text(encoding="utf-8")

    assert "- Evidence:" in text
    assert "  - Median L/R correlation: 0.350." in text
    assert "summary evidence" not in text
    assert text.count("10.000s-30.000s") == 1


def test_report_summary_sections_show_range_counts_not_raw_lists(tmp_path: Path):
    summary = _make_summary()
    path = write_report_md(summary, summary["plots"], tmp_path)
    text = path.read_text(encoding="utf-8")

    assert "correlation_below_0_ranges: 1" in text
    assert "correlation_below_0_time_ranges" not in text
    assert "{'start':" not in text


def test_report_repeats_relative_db_explanation_near_relative_sections(tmp_path: Path):
    summary = _make_summary()
    path = write_report_md(summary, summary["plots"], tmp_path)
    text = path.read_text(encoding="utf-8")
    note = (
        "Relative dB values use this track's strongest measured content as 0 dB. "
        "They show shape within this song and are not calibrated dBFS."
    )

    assert text.count(note) >= 4
    assert text.index(note) > text.index("## Average spectrum summary")
    assert text.index(note) < text.index("- nperseg:")


def test_write_report_md_reports_suppressed_findings(tmp_path: Path):
    summary = _make_summary()
    findings = {
        "count": 1,
        "all_count": 2,
        "max_findings": 1,
        "findings_suppressed_count": 1,
        "findings_shown": [
            {
                "severity": "issue",
                "category": "levels",
                "title": "Sample clipping detected",
                "measured_value": 3,
                "threshold": 0,
                "unit": "samples",
                "evidence": "clipped_samples measured 3.",
                "why_it_matters": "Measured sample values reached the clipping threshold.",
                "suggested_checks": ["Inspect the waveform."],
                "time_ranges": [],
                "confidence": "high",
            }
        ],
        "findings": [],
        "all_findings": [],
    }

    path = write_report_md(summary, summary["plots"], tmp_path, findings)
    text = path.read_text(encoding="utf-8")

    assert "1 lower-priority finding(s) suppressed" in text
    assert "Sample clipping detected" in text
    assert "Prompt level: check before delivery" in text


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


def test_report_uses_friendly_prompt_labels_not_internal_severity_labels(
    tmp_path: Path,
):
    summary = _make_summary()
    findings = {
        "count": 1,
        "findings": [
            {
                "severity": "info",
                "category": "levels",
                "title": "Integrated loudness is above -10 LUFS",
                "measured_value": -9.5,
                "threshold": -10.0,
                "unit": "LUFS",
                "evidence": "integrated_lufs measured -9.500 LUFS.",
                "why_it_matters": "Delivery systems may apply loudness normalization.",
                "does_not_mean": "This does not mean the measured loudness is unsuitable.",
                "suggested_checks": ["Compare with the intended delivery context."],
                "time_ranges": [],
                "confidence": "high",
            }
        ],
    }
    path = write_report_md(summary, summary["plots"], tmp_path, findings)
    text = path.read_text(encoding="utf-8")

    assert "Prompt level: for reference" in text
    assert "Severity:" not in text
    assert "Suggested checks:" not in text


def test_report_md_lufs_context_not_finding(tmp_path: Path):
    summary = _make_summary()
    summary["levels"]["integrated_lufs"] = -8.2
    findings = {"count": 0, "findings": [], "findings_shown": []}
    path = write_report_md(summary, summary["plots"], tmp_path, findings)
    text = path.read_text(encoding="utf-8")

    assert "Integrated loudness: -8.200 LUFS" in text
    assert "streaming normalization reference levels" in text
    assert "streaming normalization targets" not in text
    assert "platforms that normalize playback may reduce level" in text
    assert "### Integrated loudness is above -10 LUFS" not in text


def test_report_renders_plot_links_in_order(tmp_path: Path):
    summary = _make_summary()
    plot_files = ["01_waveform_rms.png", "02_rms_timeline.png"]
    path = write_report_md(summary, plot_files, tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "Waveform + RMS Envelope" in text
    assert "Frame RMS Timeline" in text
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


def test_report_md_renders_friendly_no_findings_state(tmp_path: Path):
    summary = _make_summary()
    findings = {"count": 0, "findings": [], "findings_shown": []}
    path = write_report_md(summary, summary["plots"], tmp_path, findings)
    text = path.read_text(encoding="utf-8")

    assert (
        "No prioritized findings surfaced. The plots and technical details still "
        "describe the track's measured shape."
    ) in text


def _html_findings() -> dict:
    return {
        "count": 1,
        "all_count": 2,
        "max_findings": 1,
        "findings_suppressed_count": 1,
        "findings_shown": [
            {
                "severity": "warning",
                "category": "levels",
                "title": "Near-full-scale samples detected",
                "measured_value": 12,
                "threshold": 0,
                "unit": "samples",
                "evidence": "near_clipping_samples measured 12.",
                "why_it_matters": "Measured samples are close to the configured ceiling.",
                "does_not_mean": "This does not mean the passage is clipped.",
                "suggested_checks": ["Inspect the sample histogram."],
                "time_ranges": [{"start": 1.0, "end": 1.5, "duration": 0.5}],
                "confidence": "high",
            }
        ],
    }


def test_write_report_html_contains_key_sections_and_metrics(tmp_path: Path):
    summary = _make_summary()
    summary["levels"]["integrated_lufs"] = -8.2
    path = write_report_html(summary, summary["plots"], tmp_path, _html_findings())
    text = path.read_text(encoding="utf-8")

    assert path.name == "report.html"
    assert "Measurement-based findings, not quality judgments." in text
    assert ">Findings<" in text
    assert "Listening prompts" not in text
    assert "Integrated LUFS" in text
    assert "True peak" in text
    assert "Median stereo correlation" in text
    assert "Does not mean:" in text
    assert "This does not mean the passage is clipped." in text
    assert "Suggested listening checks" in text
    assert "1 lower-priority finding(s) suppressed" in text
    assert "Delivery / headroom context" in text
    assert "streaming normalization reference levels" in text
    assert "streaming normalization targets" not in text


def test_write_report_html_contains_glossary_and_explanations(tmp_path: Path):
    summary = _make_summary()
    path = write_report_html(summary, summary["plots"], tmp_path, _html_findings())
    text = path.read_text(encoding="utf-8")

    assert "Understanding these numbers" in text
    assert "Onset density is an attack/activity map for this track" in text
    assert "It is not punch, groove quality, drum hits per second, or mix quality." in text
    assert "Relative dB plots show shape within this track." in text
    assert "PLR is the relationship between true peak and integrated loudness" in text
    assert "Higher PLR means more peak headroom relative to loudness" in text
    assert "+1 means nearly identical channels" in text
    assert "0 dB means side and mid energy are similar" in text
    assert "moves higher when energy shifts upward in frequency" in text
    assert "not comparable to dBFS values from meters or other songs" in text


def test_write_report_html_renders_relative_plot_links_and_curated_names(
    tmp_path: Path,
):
    summary = _make_summary()
    path = write_report_html(summary, summary["plots"], tmp_path, _html_findings())
    text = path.read_text(encoding="utf-8")

    assert '<img src="03_log_spectrogram.png" alt="Log-Frequency Spectrogram">' in text
    assert '<img src="04_average_spectrum.png" alt="Welch Average Spectrum">' in text
    assert '<img src="09_band_energy_timeline.png" alt="Frequency Band Energy Timeline">' in text
    assert "plot-card plot-card-wide" in text
    assert "What this shows:" in text


def test_write_report_html_keeps_polished_visual_structure(tmp_path: Path):
    summary = _make_summary()
    path = write_report_html(summary, summary["plots"], tmp_path, _html_findings())
    text = path.read_text(encoding="utf-8")

    assert "--shadow-card:" in text
    assert ".metric-card { min-height:" in text
    assert ".finding-card { padding:" in text
    assert ".plot-image-wrapper { background: var(--surface-muted)" in text
    assert ".priority-warning { background: #ccfbf1" in text
    assert ".priority-warning { background: #fef3c7" not in text
    assert "letter-spacing: 0;" in text


def test_write_report_html_escapes_filename_and_finding_text(tmp_path: Path):
    summary = _make_summary()
    summary["metadata"]["filename"] = '<track & "mix">.wav'
    findings = _html_findings()
    findings["findings_shown"][0]["title"] = "<script>alert(1)</script>"
    findings["findings_shown"][0]["evidence"] = "value < 1 & value > 0"
    findings["findings_shown"][0]["suggested_checks"] = ['Inspect "A&B" <now>.']

    path = write_report_html(
        summary,
        ['03_log_spectrogram.png', 'bad"name.png'],
        tmp_path,
        findings,
    )
    text = path.read_text(encoding="utf-8")

    assert '<track & "mix">.wav' not in text
    assert "&lt;track &amp; &quot;mix&quot;&gt;.wav" in text
    assert "<script>alert(1)</script>" not in text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in text
    assert "value &lt; 1 &amp; value &gt; 0" in text
    assert "Inspect &quot;A&amp;B&quot; &lt;now&gt;." in text
    assert 'src="bad&quot;name.png"' in text


def test_write_report_html_avoids_banned_judgment_words(tmp_path: Path):
    summary = _make_summary()
    path = write_report_html(summary, summary["plots"], tmp_path, _html_findings())
    text = path.read_text(encoding="utf-8")

    for word in ("bad", "good", "professional", "amateur", "ai", "score", "fix", "broken"):
        assert not re.search(rf"\b{word}\b", text, flags=re.IGNORECASE), word


def test_write_report_html_renders_friendly_no_findings_state(tmp_path: Path):
    summary = _make_summary()
    findings = {"count": 0, "findings": [], "findings_shown": []}
    path = write_report_html(summary, summary["plots"], tmp_path, findings)
    text = path.read_text(encoding="utf-8")

    assert (
        "No prioritized findings surfaced. The plots and technical details still "
        "describe the track's measured shape."
    ) in text


def test_write_report_html_how_to_read_and_notes_persistence(tmp_path: Path):
    summary = _make_summary()
    path = write_report_html(summary, summary["plots"], tmp_path, _html_findings())
    text = path.read_text(encoding="utf-8")

    assert (
        "Check before delivery / worth a listen / for reference indicate priority, not quality."
        in text
    )
    assert (
        "A report can have no prioritized findings; the plots still describe the track"
        in text
    )
    assert (
        "Notes typed here are temporary in this browser page and are not saved into the report files."
        in text
    )


def test_write_report_html_renders_grouped_stereo_evidence_and_capped_ranges(
    tmp_path: Path,
):
    summary = _make_summary()
    ranges = [{"start": float(i), "end": float(i) + 0.5, "duration": 0.5} for i in range(8)]
    ranges[5] = {"start": 20.0, "end": 24.0, "duration": 4.0}
    ranges[6] = {"start": 30.0, "end": 33.0, "duration": 3.0}
    ranges[7] = {"start": 40.0, "end": 42.0, "duration": 2.0}
    findings = {
        "count": 1,
        "findings_shown": [
            {
                "severity": "warning",
                "category": "stereo",
                "title": "Stereo field shows sustained low-correlation / side-heavy regions",
                "measured_value": 0.35,
                "threshold": 0.5,
                "unit": "mixed stereo metrics",
                "evidence": "summary evidence",
                "evidence_items": [
                    "Median L/R correlation: 0.350.",
                    "Minimum frame correlation: -0.400.",
                    "Total time below 0.3 correlation: 20.000 seconds across 8 region(s).",
                ],
                "why_it_matters": "Mono playback may change tone or apparent width.",
                "does_not_mean": "This does not mean the stereo image is incorrect.",
                "suggested_checks": [
                    "Inspect the stereo correlation timeline around the lowest-correlation regions.",
                    "Listen in mono around sustained low-correlation regions if mono compatibility matters.",
                    "Inspect the mid/side energy plot around side-heavy regions.",
                ],
                "time_ranges": ranges,
                "confidence": "medium",
            }
        ],
    }
    path = write_report_html(summary, summary["plots"], tmp_path, findings)
    text = path.read_text(encoding="utf-8")

    assert "<li>Median L/R correlation: 0.350.</li>" in text
    assert "summary evidence" not in text
    assert "20.000s-24.000s" in text
    assert "30.000s-33.000s" in text
    assert "40.000s-42.000s" in text
    assert "0.000s-0.500s" in text
    assert "1.000s-1.500s" in text
    assert "2.000s-2.500s" not in text
    assert "see findings.json for full ranges" in text
