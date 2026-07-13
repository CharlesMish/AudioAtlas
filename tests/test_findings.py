from __future__ import annotations

from audioatlas.analysis.findings import generate_findings
from audioatlas.release import FINDING_RULESET_VERSION, FINDINGS_SCHEMA_VERSION


def _summary(**overrides):
    summary = {
        "metadata": {
            "filename": "test.wav",
            "format": "WAV",
            "subtype": "PCM_16",
        },
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
    assert findings[0].does_not_mean


def test_near_clipping_samples_generate_info_for_small_counts():
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
    assert findings[0].severity == "info"
    assert findings[0].measured_value == 12
    assert findings[0].time_ranges == [{"start": 1.0, "end": 1.5, "duration": 0.5}]


def test_tiny_near_clipping_count_with_true_peak_below_zero_is_suppressed():
    findings = generate_findings(
        _summary(
            levels={"near_clipping_samples": 1, "true_peak_dbtp": -0.4},
            peak_timeline={
                "near_clipping_time_ranges": [
                    {"start": 1.0, "end": 1.1, "duration": 0.1}
                ]
            },
        )
    ).findings

    assert findings == []


def test_many_near_clipping_samples_generate_warning():
    findings = generate_findings(
        _summary(
            levels={"near_clipping_samples": 1482, "true_peak_dbtp": -0.4},
            peak_timeline={
                "near_clipping_time_ranges": [
                    {"start": 1.0, "end": 2.0, "duration": 1.0}
                ]
            },
        )
    ).findings

    assert len(findings) == 1
    assert findings[0].severity == "warning"


def test_tiny_near_clipping_with_true_peak_merges_into_true_peak_finding():
    findings = generate_findings(
        _summary(
            levels={"near_clipping_samples": 3, "true_peak_dbtp": 0.2},
            peak_timeline={
                "near_clipping_time_ranges": [
                    {"start": 1.0, "end": 1.1, "duration": 0.1}
                ]
            },
        )
    ).findings

    assert len(findings) == 1
    assert "true peak" in findings[0].title.lower()
    assert "Near-clipping count measured 3" in findings[0].evidence
    near_clip = [finding for finding in findings if "Near-full-scale" in finding.title]
    assert near_clip == []


def test_tiny_decoded_near_clipping_wording_is_singular():
    findings = generate_findings(
        _summary(
            metadata={"filename": "song.mp3", "format": "MP3", "subtype": "MPEG_LAYER_III"},
            levels={"near_clipping_samples": 1, "true_peak_dbtp": 0.2},
        )
    ).findings

    assert len(findings) == 1
    assert "1 decoded near-clipping sample" in findings[0].evidence
    assert "1 in decoded samples" not in findings[0].evidence


def test_substantial_near_clipping_with_true_peak_keeps_separate_finding():
    findings = generate_findings(
        _summary(
            levels={"near_clipping_samples": 200, "true_peak_dbtp": 0.2},
            peak_timeline={
                "near_clipping_time_ranges": [
                    {"start": 1.0, "end": 2.0, "duration": 1.0}
                ]
            },
        )
    ).findings

    titles = [finding.title for finding in findings]
    assert "Approximate true peak is above 0 dBTP" in titles
    assert "Near-full-scale samples detected" in titles


def test_lossy_metadata_uses_decoded_sample_wording_for_level_findings():
    findings = generate_findings(
        _summary(
            metadata={"filename": "song.mp3", "format": "MP3", "subtype": "MPEG_LAYER_III"},
            levels={"near_clipping_samples": 200, "clipped_samples": 4},
        )
    ).findings

    text = " ".join(
        " ".join([finding.evidence, finding.why_it_matters, finding.does_not_mean])
        for finding in findings
    ).lower()
    assert "decoded near-clipping samples" in text
    assert "decoded audio" in text
    assert "does not establish whether the original master clipped" in text


def test_clipped_samples_generate_issue():
    findings = generate_findings(_summary(levels={"clipped_samples": 3})).findings

    assert len(findings) == 1
    assert findings[0].severity == "issue"
    assert findings[0].category == "levels"


def test_high_integrated_lufs_does_not_generate_top_level_finding():
    findings = generate_findings(_summary(levels={"integrated_lufs": -9.5})).findings

    assert findings == []


def test_low_plr_alone_does_not_generate_default_finding():
    """PLR is context unless an independent high-level measurement also fires."""
    findings = generate_findings(_summary(levels={"plr_db": 7.5})).findings

    assert findings == []


def test_low_plr_with_independent_high_level_evidence_generates_warning():
    findings = generate_findings(
        _summary(levels={"plr_db": 7.5, "true_peak_dbtp": 0.2})
    ).findings

    plr = [
        finding
        for finding in findings
        if finding.rule_id == "dynamics.low_plr_with_level_pressure"
    ]
    assert len(plr) == 1
    assert plr[0].severity == "warning"
    assert plr[0].rule_version == 2
    assert {item.metric for item in plr[0].evidence_items} == {
        "levels.plr_db",
        "levels.true_peak_dbtp",
    }
    assert "Loudness normalization" in plr[0].does_not_mean
    assert "does not change PLR" in plr[0].does_not_mean


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


def test_high_median_low_side_brief_negative_correlation_is_not_warning():
    findings = generate_findings(
        _summary(
            levels={"duration_seconds": 180.0},
            stereo_correlation={
                "correlation_min": -0.15,
                "correlation_median": 0.92,
                "correlation_below_0_time_ranges": [
                    {"start": 42.0, "end": 42.3, "duration": 0.3}
                ],
                "correlation_below_0_3_time_ranges": [
                    {"start": 42.0, "end": 42.3, "duration": 0.3}
                ],
            },
            mid_side_energy={"side_to_mid_ratio_db_median": -14.0},
        )
    ).findings

    assert not any(finding.severity == "warning" for finding in findings)
    assert [finding.title for finding in findings] == [
        "Stereo field shows sustained low-correlation / side-heavy regions"
    ]


def test_centered_track_with_tiny_negative_correlation_blip_is_suppressed():
    findings = generate_findings(
        _summary(
            levels={"duration_seconds": 180.0},
            stereo_correlation={
                "correlation_min": -0.02,
                "correlation_median": 0.95,
                "correlation_below_0_time_ranges": [
                    {"start": 42.0, "end": 42.08, "duration": 0.08}
                ],
            },
            mid_side_energy={"side_to_mid_ratio_db_median": -16.0},
        )
    ).findings

    assert findings == []


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


def test_brief_below_0_3_correlation_is_suppressed_when_median_is_high():
    findings = generate_findings(
        _summary(
            levels={"duration_seconds": 180.0},
            stereo_correlation={
                "correlation_median": 0.9,
                "correlation_below_0_3_time_ranges": [
                    {"start": 4.0, "end": 4.3, "duration": 0.3}
                ],
            },
            mid_side_energy={"side_to_mid_ratio_db_median": -12.0},
        )
    ).findings

    assert findings == []


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
    assert "Median L/R correlation" in findings[0].evidence


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
    assert findings[0].rule_id == "stereo.low_correlation_or_side_heavy"
    # Multiple supporting measurements deliberately have no single synthetic unit.
    assert findings[0].measured_value is None
    assert findings[0].threshold is None
    assert findings[0].unit == ""
    assert [item.metric for item in findings[0].evidence_items] == [
        "mid_side_energy.side_to_mid_ratio_db_median",
        "mid_side_energy.side_to_mid_ratio_above_minus_6_regions",
    ]
    assert findings[0].time_ranges == [{"start": 6.0, "end": 7.0, "duration": 1.0}]


def test_wide_low_correlation_track_retains_stereo_warnings_and_info():
    findings = generate_findings(
        _summary(
            levels={"duration_seconds": 120.0},
            stereo_correlation={
                "correlation_min": -0.4,
                "correlation_median": 0.35,
                "correlation_below_0_time_ranges": [
                    {"start": 10.0, "end": 15.0, "duration": 5.0}
                ],
                "correlation_below_0_3_time_ranges": [
                    {"start": 10.0, "end": 30.0, "duration": 20.0}
                ],
            },
            mid_side_energy={
                "side_to_mid_ratio_db_median": -4.0,
                "side_to_mid_ratio_above_minus_6_time_ranges": [
                    {"start": 10.0, "end": 30.0, "duration": 20.0}
                ],
            },
        )
    ).findings

    titles = [finding.title for finding in findings]
    assert titles == ["Stereo field shows sustained low-correlation / side-heavy regions"]
    assert "Minimum frame correlation" in findings[0].evidence
    assert "Median L/R correlation" in findings[0].evidence
    assert "Median side/mid ratio" in findings[0].evidence
    assert [item.label for item in findings[0].evidence_items] == [
        "Minimum frame correlation: -0.400.",
        "Total time below 0 correlation: 5.000 seconds across 1 region(s).",
        "Total time below 0.3 correlation: 20.000 seconds across 1 region(s).",
        "Median L/R correlation: 0.350.",
        "Median side/mid ratio: -4.000 dB.",
        "Side/mid ratio above -6 dB: 1 region(s).",
    ]
    assert all(item.metric for item in findings[0].evidence_items)
    assert findings[0].associated_graphs == ["stereo_correlation", "mid_side_energy"]
    assert findings[0].suggested_checks == [
        "Inspect the stereo correlation timeline around the lowest-correlation regions.",
        "Listen in mono around sustained low-correlation regions if mono compatibility matters.",
        "Inspect the mid/side energy plot around side-heavy regions.",
    ]
    assert findings[0].time_ranges == [
        {"start": 10.0, "end": 30.0, "duration": 20.0}
    ]
    assert any(finding.severity == "warning" for finding in findings)


def test_low_mid_strongest_bin_does_not_generate_default_finding():
    findings = generate_findings(_summary(average_spectrum={"strongest_bin_hz": 220.0})).findings

    assert findings == []


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


def test_spectral_centroid_elevated_ranges_do_not_generate_default_prompt():
    findings = generate_findings(
        _summary(
            spectral_shape={
                "centroid_elevated_time_ranges": [
                    {"start": 8.0, "end": 9.0, "duration": 1.0}
                ]
            }
        )
    ).findings

    assert findings == []


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


def test_spectral_centroid_reduced_ranges_do_not_generate_default_prompt():
    findings = generate_findings(
        _summary(
            spectral_shape={
                "centroid_reduced_time_ranges": [
                    {"start": 10.0, "end": 11.0, "duration": 1.0}
                ]
            }
        )
    ).findings

    assert findings == []


def test_low_rolloff_95_remains_summary_context_not_a_default_finding():
    """An absolute rolloff value cannot establish missing air, vocals, or cymbals."""
    findings = generate_findings(
        _summary(spectral_shape={"rolloff_95_median_hz": 6500.0})
    ).findings

    assert findings == []


def test_large_centroid_shift_ranges_do_not_generate_default_prompt():
    findings = generate_findings(
        _summary(
            spectral_shape={
                "centroid_large_shift_time_ranges": [
                    {"start": 12.0, "end": 13.0, "duration": 1.0}
                ]
            }
        )
    ).findings

    assert findings == []


def test_other_absolute_rolloff_values_also_do_not_generate_findings():
    findings = generate_findings(
        _summary(spectral_shape={"rolloff_95_median_hz": 7200.0})
    ).findings
    assert findings == []


def test_plr_explanation_states_normalization_invariance_without_claiming_damage():
    findings = generate_findings(
        _summary(levels={"plr_db": 6.0, "near_clipping_samples": 250})
    ).findings
    plr = next(
        finding
        for finding in findings
        if finding.rule_id == "dynamics.low_plr_with_level_pressure"
    )
    why = plr.why_it_matters.lower()
    boundary = plr.does_not_mean.lower()
    assert "sits relatively close to integrated loudness" in why
    assert "normalization" not in why
    assert "loudness normalization" in boundary
    assert "does not change plr" in boundary
    assert "reduces dynamic contrast" not in (why + boundary)


def test_band_energy_elevated_ranges_do_not_generate_default_prompt():
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

    assert findings == []


def test_high_band_reduced_ranges_do_not_generate_default_prompt():
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

    assert findings == []


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


def test_onset_density_elevated_ranges_do_not_generate_default_prompt():
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

    assert findings == []


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


def test_multiple_relative_band_ranges_do_not_generate_grouped_prompt():
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

    assert findings == []


def test_relative_to_track_shape_prompts_are_not_generated_for_normal_movement():
    findings = generate_findings(
        _summary(
            spectral_shape={
                "centroid_elevated_time_ranges": [
                    {"start": 8.0, "end": 10.0, "duration": 2.0}
                ],
                "centroid_reduced_time_ranges": [
                    {"start": 12.0, "end": 14.0, "duration": 2.0}
                ],
                "centroid_large_shift_time_ranges": [
                    {"start": 16.0, "end": 18.0, "duration": 2.0}
                ],
            },
            band_energy_timeline={
                "bands": {
                    "presence": {
                        "median_db": -16.0,
                        "max_db": -4.0,
                        "elevated_threshold_db": -10.0,
                        "elevated_time_ranges": [
                            {"start": 20.0, "end": 22.0, "duration": 2.0}
                        ],
                        "reduced_time_ranges": [],
                    }
                }
            },
            onset_density={
                "onset_density_median": 0.25,
                "high_onset_density_threshold": 0.5,
                "high_onset_density_time_ranges": [
                    {"start": 24.0, "end": 26.0, "duration": 2.0}
                ],
            },
        )
    ).findings

    assert findings == []


def test_findings_are_sorted_deterministically_by_priority():
    findings = generate_findings(
        _summary(
            levels={
                "clipped_samples": 2,
                "near_clipping_samples": 300,
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
                "true_peak_dbtp": 0.2,
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

    assert len(titles) == 2


def test_findings_result_serializes_to_json_safe_dict():
    result = generate_findings(_summary(levels={"clipped_samples": 1}))
    data = result.to_dict()

    assert data["schema_version"] == FINDINGS_SCHEMA_VERSION
    assert data["ruleset_version"] == FINDING_RULESET_VERSION
    assert data["count"] == 1
    finding = data["findings"][0]
    assert finding["rule_id"] == "levels.sample_clipping"
    assert finding["rule_version"] == 1
    assert finding["severity"] == "issue"
    assert finding["time_ranges"] == []
    assert finding["does_not_mean"]
    assert finding["evidence_items"][0]["metric"] == "levels.clipped_samples"
    assert finding["associated_graphs"] == [
        "peak_timeline",
        "waveform_rms",
        "sample_histogram",
    ]


def test_generated_findings_include_does_not_mean_field():
    result = generate_findings(
        _summary(
            levels={
                "true_peak_dbtp": 0.2,
                "near_clipping_samples": 200,
                "clipped_samples": 2,
                "integrated_lufs": -9.0,
                "plr_db": 7.0,
            },
            stereo_correlation={
                "correlation_min": -0.2,
                "correlation_median": 0.4,
                "correlation_below_0_time_ranges": [
                    {"start": 2.0, "end": 3.0, "duration": 1.0}
                ],
                "correlation_below_0_3_time_ranges": [
                    {"start": 4.0, "end": 5.0, "duration": 1.0}
                ],
            },
            mid_side_energy={
                "side_to_mid_ratio_db_median": -4.0,
                "side_to_mid_ratio_above_minus_6_time_ranges": [
                    {"start": 6.0, "end": 7.0, "duration": 1.0}
                ],
            },
            average_spectrum={"strongest_bin_hz": 220.0},
            spectral_shape={"rolloff_95_median_hz": 7000.0},
        )
    )

    assert result.all_findings
    assert all(finding.does_not_mean for finding in result.all_findings)
