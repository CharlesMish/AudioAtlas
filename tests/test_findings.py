from __future__ import annotations

from audioatlas.analysis.findings import generate_findings


def _summary(**overrides):
    summary = {
        "levels": {
            "true_peak_dbtp": -1.0,
            "near_clipping_samples": 0,
            "clipped_samples": 0,
            "integrated_lufs": -14.0,
            "plr_db": 10.0,
        },
        "stereo_correlation": {
            "correlation_min": 0.5,
            "correlation_median": 0.9,
        },
        "mid_side_energy": {
            "side_to_mid_ratio_db_median": -12.0,
        },
        "average_spectrum": {
            "strongest_bin_hz": 1000.0,
        },
    }
    for block, values in overrides.items():
        summary[block].update(values)
    return summary


def _titles(summary):
    return [finding.title for finding in generate_findings(summary).findings]


def test_true_peak_above_zero_generates_warning():
    findings = generate_findings(_summary(levels={"true_peak_dbtp": 0.3})).findings

    assert len(findings) == 1
    assert findings[0].severity == "warning"
    assert findings[0].category == "levels"
    assert "true peak" in findings[0].title.lower()


def test_near_clipping_samples_generate_warning():
    findings = generate_findings(_summary(levels={"near_clipping_samples": 12})).findings

    assert len(findings) == 1
    assert findings[0].severity == "warning"
    assert findings[0].measured_value == 12


def test_clipped_samples_generate_issue():
    findings = generate_findings(_summary(levels={"clipped_samples": 3})).findings

    assert len(findings) == 1
    assert findings[0].severity == "issue"
    assert findings[0].category == "levels"


def test_high_integrated_lufs_generates_info():
    findings = generate_findings(_summary(levels={"integrated_lufs": -9.5})).findings

    assert len(findings) == 1
    assert findings[0].severity == "info"
    assert findings[0].unit == "LUFS"


def test_low_plr_generates_warning():
    findings = generate_findings(_summary(levels={"plr_db": 7.5})).findings

    assert len(findings) == 1
    assert findings[0].severity == "warning"
    assert findings[0].category == "dynamics"


def test_negative_minimum_correlation_generates_warning():
    findings = generate_findings(
        _summary(stereo_correlation={"correlation_min": -0.2})
    ).findings

    assert len(findings) == 1
    assert findings[0].severity == "warning"
    assert findings[0].category == "stereo"


def test_low_median_correlation_generates_warning():
    findings = generate_findings(
        _summary(stereo_correlation={"correlation_median": 0.4})
    ).findings

    assert len(findings) == 1
    assert findings[0].severity == "warning"
    assert "median" in findings[0].title.lower()


def test_high_side_to_mid_ratio_generates_info():
    findings = generate_findings(
        _summary(mid_side_energy={"side_to_mid_ratio_db_median": -4.0})
    ).findings

    assert len(findings) == 1
    assert findings[0].severity == "info"
    assert findings[0].unit == "dB"


def test_low_mid_strongest_bin_generates_info_without_muddy_claim():
    findings = generate_findings(_summary(average_spectrum={"strongest_bin_hz": 220.0})).findings

    assert len(findings) == 1
    assert findings[0].severity == "info"
    assert findings[0].category == "spectrum"
    text = " ".join(
        [
            findings[0].title,
            findings[0].evidence,
            findings[0].why_it_matters,
            " ".join(findings[0].suggested_checks),
        ]
    ).lower()
    assert "muddy" not in text


def test_multiple_rules_can_trigger_together():
    titles = _titles(
        _summary(
            levels={"clipped_samples": 1, "plr_db": 7.0},
            stereo_correlation={"correlation_min": -0.1},
        )
    )

    assert len(titles) == 3


def test_findings_result_serializes_to_json_safe_dict():
    result = generate_findings(_summary(levels={"clipped_samples": 1}))
    data = result.to_dict()

    assert data["count"] == 1
    assert data["findings"][0]["severity"] == "issue"
    assert data["findings"][0]["time_ranges"] == []
