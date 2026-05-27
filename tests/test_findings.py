from __future__ import annotations

from audioatlas.analysis.findings import generate_findings


def _summary(**overrides):
    summary = {
        "analysis_config": {
            "db_floor": -100.0,
            "max_findings": 8,
            "band_finding_min_duration_seconds": 0.5,
            "band_finding_min_relative_db": -80.0,
            "finding_min_time_range_seconds": 0.25,
        },
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
        "band_energy_timeline": {
            "strongest_band_by_median": None,
            "bands": {},
        },
        "onset_density": {
            "onset_density_median": 0.2,
            "onset_density_max": 0.0,
            "high_onset_density_threshold": 0.35,
            "high_onset_density_time_ranges": [],
            "strongest_onset_density_time": None,
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


def test_tiny_low_correlation_range_is_filtered():
    findings = generate_findings(
        _summary(
            stereo_correlation={
                "correlation_below_0_3_time_ranges": [
                    {"start": 4.0, "end": 4.08, "duration": 0.08}
                ]
            }
        )
    ).findings

    assert findings == []


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


def test_strongest_band_summary_fact_does_not_generate_default_finding():
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

    assert findings == []


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


def test_tiny_spectral_centroid_range_is_filtered():
    findings = generate_findings(
        _summary(
            spectral_shape={
                "centroid_elevated_time_ranges": [
                    {"start": 8.0, "end": 8.1, "duration": 0.1}
                ]
            }
        )
    ).findings

    assert findings == []


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


def test_band_energy_elevated_ranges_generate_info():
    findings = generate_findings(
        _summary(
            band_energy_timeline={
                "bands": {
                    "low_mid": {
                        "median_db": -18.0,
                        "max_db": -8.0,
                        "elevated_threshold_db": -12.0,
                        "reduced_threshold_db": -30.0,
                        "elevated_time_ranges": [
                            {"start": 14.0, "end": 15.0, "duration": 1.0}
                        ],
                        "reduced_time_ranges": [],
                    }
                }
            }
        )
    ).findings

    assert len(findings) == 1
    assert "low_mid band energy is elevated" in findings[0].title
    assert findings[0].time_ranges == [{"start": 14.0, "end": 15.0, "duration": 1.0}]
    text = " ".join([findings[0].title, " ".join(findings[0].suggested_checks)]).lower()
    assert "muddy" not in text and "too much" not in text


def test_high_band_reduced_ranges_generate_info():
    findings = generate_findings(
        _summary(
            band_energy_timeline={
                "bands": {
                    "high": {
                        "median_db": -20.0,
                        "max_db": -6.0,
                        "elevated_threshold_db": -14.0,
                        "reduced_threshold_db": -32.0,
                        "elevated_time_ranges": [],
                        "reduced_time_ranges": [
                            {"start": 16.0, "end": 17.0, "duration": 1.0}
                        ],
                    }
                }
            }
        )
    ).findings

    assert len(findings) == 1
    assert "high band energy is reduced" in findings[0].title
    assert findings[0].time_ranges == [{"start": 16.0, "end": 17.0, "duration": 1.0}]


def test_strongest_time_varying_band_does_not_generate_default_finding():
    findings = generate_findings(
        _summary(
            band_energy_timeline={
                "strongest_band_by_median": "presence",
                "bands": {
                    "presence": {
                        "median_db": -8.0,
                        "elevated_time_ranges": [],
                        "reduced_time_ranges": [],
                    }
                },
            }
        )
    ).findings

    assert findings == []


def test_onset_density_elevated_ranges_generate_info():
    findings = generate_findings(
        _summary(
            onset_density={
                "onset_density_median": 0.25,
                "onset_density_max": 0.9,
                "high_onset_density_threshold": 0.5,
                "high_onset_density_time_ranges": [
                    {"start": 18.0, "end": 19.0, "duration": 1.0}
                ],
                "strongest_onset_density_time": 18.5,
            }
        )
    ).findings

    assert len(findings) == 1
    assert "Onset density is elevated" in findings[0].title
    assert findings[0].category == "dynamics"
    assert findings[0].time_ranges == [{"start": 18.0, "end": 19.0, "duration": 1.0}]
    text = " ".join([findings[0].title, " ".join(findings[0].suggested_checks)]).lower()
    assert "punch" not in text and "bad transients" not in text


def test_tiny_onset_density_range_is_filtered():
    findings = generate_findings(
        _summary(
            onset_density={
                "onset_density_median": 0.25,
                "onset_density_max": 0.9,
                "high_onset_density_threshold": 0.5,
                "high_onset_density_time_ranges": [
                    {"start": 18.0, "end": 18.1, "duration": 0.1}
                ],
            }
        )
    ).findings

    assert findings == []


def test_strongest_onset_density_frame_does_not_generate_default_finding():
    findings = generate_findings(
        _summary(
            onset_density={
                "onset_density_median": 0.1,
                "onset_density_max": 0.75,
                "high_onset_density_time_ranges": [],
                "strongest_onset_density_time": 21.0,
            }
        )
    ).findings

    assert findings == []


def test_floor_level_band_ranges_do_not_generate_findings():
    findings = generate_findings(
        _summary(
            band_energy_timeline={
                "bands": {
                    "sub": {
                        "median_db": -100.0,
                        "max_db": -96.0,
                        "elevated_threshold_db": -94.0,
                        "reduced_threshold_db": -100.0,
                        "elevated_time_ranges": [
                            {"start": 0.0, "end": 1.0, "duration": 1.0}
                        ],
                        "reduced_time_ranges": [],
                    },
                    "bass": {
                        "median_db": -99.0,
                        "max_db": -92.0,
                        "elevated_threshold_db": -93.0,
                        "reduced_threshold_db": -100.0,
                        "elevated_time_ranges": [
                            {"start": 1.0, "end": 2.0, "duration": 1.0}
                        ],
                        "reduced_time_ranges": [],
                    },
                }
            }
        )
    ).findings

    assert findings == []


def test_tiny_band_edge_ranges_are_filtered():
    findings = generate_findings(
        _summary(
            band_energy_timeline={
                "bands": {
                    "presence": {
                        "median_db": -20.0,
                        "max_db": -5.0,
                        "elevated_threshold_db": -14.0,
                        "reduced_threshold_db": -32.0,
                        "elevated_time_ranges": [
                            {"start": 0.0, "end": 0.043, "duration": 0.043}
                        ],
                        "reduced_time_ranges": [],
                    }
                }
            }
        )
    ).findings

    assert findings == []


def test_multiple_band_findings_are_grouped():
    findings = generate_findings(
        _summary(
            band_energy_timeline={
                "bands": {
                    "low_mid": {
                        "median_db": -18.0,
                        "max_db": -5.0,
                        "elevated_threshold_db": -12.0,
                        "reduced_threshold_db": -30.0,
                        "elevated_time_ranges": [
                            {"start": 14.0, "end": 15.0, "duration": 1.0}
                        ],
                        "reduced_time_ranges": [],
                    },
                    "presence": {
                        "median_db": -16.0,
                        "max_db": -4.0,
                        "elevated_threshold_db": -10.0,
                        "reduced_threshold_db": -28.0,
                        "elevated_time_ranges": [
                            {"start": 14.5, "end": 15.5, "duration": 1.0}
                        ],
                        "reduced_time_ranges": [],
                    },
                }
            }
        )
    ).findings

    assert len(findings) == 1
    assert findings[0].title == "Multiple band-energy changes detected"
    assert findings[0].measured_value == 2


def test_findings_are_sorted_deterministically_by_priority():
    findings = generate_findings(
        _summary(
            levels={
                "clipped_samples": 2,
                "near_clipping_samples": 3,
                "integrated_lufs": -9.0,
                "plr_db": 7.0,
            },
            stereo_correlation={
                "correlation_min": -0.2,
                "correlation_median": 0.4,
            },
            average_spectrum={"strongest_bin_hz": 220.0},
        )
    ).findings

    assert [finding.severity for finding in findings[:4]] == [
        "issue",
        "warning",
        "warning",
        "warning",
    ]
    assert findings[0].title == "Sample clipping detected"
    assert findings[1].title == "Near-full-scale samples detected"


def test_max_findings_caps_shown_and_records_suppressed_count():
    result = generate_findings(
        _summary(
            analysis_config={"max_findings": 3},
            levels={
                "clipped_samples": 2,
                "near_clipping_samples": 3,
                "integrated_lufs": -9.0,
                "plr_db": 7.0,
            },
            stereo_correlation={
                "correlation_min": -0.2,
                "correlation_median": 0.4,
            },
            average_spectrum={"strongest_bin_hz": 220.0},
        )
    )
    data = result.to_dict()

    assert data["count"] == 3
    assert len(data["findings"]) == 3
    assert len(data["all_findings"]) > 3
    assert data["findings_suppressed_count"] == len(data["all_findings"]) - 3
    assert data["findings"][0]["title"] == "Sample clipping detected"


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
