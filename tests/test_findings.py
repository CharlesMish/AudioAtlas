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
            "correlation_below_0_time_ranges": [],
            "correlation_below_0_3_time_ranges": [],
        },
        "mid_side_energy": {
            "side_to_mid_ratio_db_median": -12.0,
            "side_to_mid_ratio_above_minus_6_time_ranges": [],
        },
        "peak_timeline": {
            "near_clipping_time_ranges": [],
        },
        "average_spectrum": {
            "strongest_bin_hz": 1000.0,
            "strongest_band": None,
            "band_energies": {},
        },
        "spectral_shape": {
            "centroid_median_hz": 2000.0,
            "rolloff_95_median_hz": 12000.0,
            "centroid_elevated_threshold_hz": 3000.0,
            "centroid_reduced_threshold_hz": 1000.0,
            "centroid_large_shift_threshold_hz": 2000.0,
            "centroid_elevated_time_ranges": [],
            "centroid_reduced_time_ranges": [],
            "centroid_large_shift_time_ranges": [],
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
    findings = generate_findings(
        _summary(
            levels={"near_clipping_samples": 12},
            peak_timeline={
                "near_clipping_time_ranges": [
                    {"start": 1.0, "end": 1.5, "duration": 0.5}
                ]
            },
        )
    ).findings

    assert len(findings) == 1
    assert findings[0].severity == "warning"
    assert findings[0].measured_value == 12
    assert findings[0].time_ranges == [{"start": 1.0, "end": 1.5, "duration": 0.5}]


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
        _summary(
            stereo_correlation={
                "correlation_min": -0.2,
                "correlation_below_0_time_ranges": [
                    {"start": 2.0, "end": 3.0, "duration": 1.0}
                ],
            }
        )
    ).findings

    assert len(findings) == 1
    assert findings[0].severity == "warning"
    assert findings[0].category == "stereo"
    assert findings[0].time_ranges == [{"start": 2.0, "end": 3.0, "duration": 1.0}]


def test_low_correlation_time_ranges_generate_info():
    findings = generate_findings(
        _summary(
            stereo_correlation={
                "correlation_below_0_3_time_ranges": [
                    {"start": 4.0, "end": 5.0, "duration": 1.0}
                ]
            }
        )
    ).findings

    assert len(findings) == 1
    assert findings[0].severity == "info"
    assert findings[0].time_ranges == [{"start": 4.0, "end": 5.0, "duration": 1.0}]


def test_low_median_correlation_generates_warning():
    findings = generate_findings(
        _summary(stereo_correlation={"correlation_median": 0.4})
    ).findings

    assert len(findings) == 1
    assert findings[0].severity == "warning"
    assert "median" in findings[0].title.lower()


def test_high_side_to_mid_ratio_generates_info():
    findings = generate_findings(
        _summary(
            mid_side_energy={
                "side_to_mid_ratio_db_median": -4.0,
                "side_to_mid_ratio_above_minus_6_time_ranges": [
                    {"start": 6.0, "end": 7.0, "duration": 1.0}
                ],
            }
        )
    ).findings

    assert len(findings) == 1
    assert findings[0].severity == "info"
    assert findings[0].unit == "dB"
    assert findings[0].time_ranges == [{"start": 6.0, "end": 7.0, "duration": 1.0}]


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


def test_strongest_band_generates_factual_info():
    findings = generate_findings(
        _summary(
            average_spectrum={
                "strongest_band": "bass",
                "band_energies": {
                    "bass": {"low_hz": 60.0, "high_hz": 120.0, "energy_db": -3.0}
                },
            }
        )
    ).findings

    assert len(findings) == 1
    assert findings[0].category == "spectrum"
    assert "bass" in findings[0].title


def test_spectral_centroid_elevated_ranges_generate_info():
    findings = generate_findings(
        _summary(
            spectral_shape={
                "centroid_elevated_time_ranges": [
                    {"start": 8.0, "end": 9.0, "duration": 1.0}
                ]
            }
        )
    ).findings

    assert len(findings) == 1
    assert findings[0].category == "spectrum"
    assert "elevated" in findings[0].title
    assert findings[0].time_ranges == [{"start": 8.0, "end": 9.0, "duration": 1.0}]
    assert "proxy" in " ".join(findings[0].suggested_checks)


def test_spectral_centroid_reduced_ranges_generate_info():
    findings = generate_findings(
        _summary(
            spectral_shape={
                "centroid_reduced_time_ranges": [
                    {"start": 10.0, "end": 11.0, "duration": 1.0}
                ]
            }
        )
    ).findings

    assert len(findings) == 1
    assert "reduced" in findings[0].title
    assert findings[0].time_ranges == [{"start": 10.0, "end": 11.0, "duration": 1.0}]


def test_low_rolloff_95_generates_factual_info():
    findings = generate_findings(
        _summary(spectral_shape={"rolloff_95_median_hz": 7000.0})
    ).findings

    assert len(findings) == 1
    assert "rolloff" in findings[0].title.lower()
    assert findings[0].unit == "Hz"


def test_large_centroid_shift_ranges_generate_info():
    findings = generate_findings(
        _summary(
            spectral_shape={
                "centroid_large_shift_time_ranges": [
                    {"start": 12.0, "end": 13.0, "duration": 1.0}
                ]
            }
        )
    ).findings

    assert len(findings) == 1
    assert "changes sharply" in findings[0].title
    assert findings[0].time_ranges == [{"start": 12.0, "end": 13.0, "duration": 1.0}]


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
