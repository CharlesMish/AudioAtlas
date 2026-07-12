from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from click.testing import CliRunner

from audioatlas.cli import main
from audioatlas.config import AnalysisConfig
from audioatlas.errors import RevisionDiffError
from audioatlas.output import OUTPUT_MARKER_FILENAME
from audioatlas.provenance import build_analysis_provenance, track_identity_block
from audioatlas.revision_diff import generate_revision_diff, write_revision_diff


def _finding(rule_id: str, *, title: str | None = None) -> dict[str, object]:
    return {
        "rule_id": rule_id,
        "rule_version": 1,
        "severity": "warning",
        "category": "levels",
        "title": title or rule_id.replace(".", " "),
        "measured_value": 1.0,
        "threshold": 0.0,
        "unit": "dBTP",
        "evidence": "Measured evidence.",
        "why_it_matters": "Delivery context.",
        "does_not_mean": "This is not a quality judgment.",
        "suggested_checks": ["Listen and inspect."],
        "associated_graphs": ["peak_timeline"],
        "time_ranges": [],
        "evidence_items": [],
    }


def _summary(
    filename: str,
    *,
    track_id: str | None = "same-song",
    provenance: dict[str, object] | None = None,
    lufs: float = -12.0,
    true_peak: float = -1.0,
    band_median: float = -6.0,
) -> dict[str, object]:
    return {
        "schema_version": "0.2.1",
        "metadata": {
            "filename": filename,
            "samplerate": 48_000,
            "channels": 2,
            "source_start_seconds": 0.0,
        },
        "source_identity": track_identity_block(track_id),
        "analysis_provenance": provenance or build_analysis_provenance(AnalysisConfig()),
        "analysis_config": {"max_findings": 8},
        "levels": {
            "duration_seconds": 180.0,
            "integrated_lufs": lufs,
            "true_peak_dbtp": true_peak,
            "sample_peak_dbfs": true_peak - 0.2,
            "rms_dbfs": lufs - 2.0,
            "plr_db": true_peak - lufs,
            "crest_factor_db": 8.0,
            "clipped_samples": 0,
            "near_clipping_samples": 0,
        },
        "stereo_correlation": {"correlation_median": 0.72},
        "mid_side_energy": {"side_to_mid_ratio_db_median": -9.0},
        "spectral_shape": {
            "centroid_median_hz": 2400.0,
            "rolloff_95_median_hz": 11_000.0,
            "bandwidth_median_hz": 3200.0,
        },
        "onset_density": {"onset_density_median": 0.17},
        "band_power_timeline": {
            "measurement": "relative_mean_power_per_fft_bin",
            "bands": {"mid": {"median_db": band_median}},
        },
    }


def _write_report(
    root: Path,
    *,
    summary: dict[str, object],
    all_findings: list[dict[str, object]],
) -> Path:
    root.mkdir(parents=True)
    (root / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    (root / "findings.json").write_text(
        json.dumps(
            {
                "schema_version": "0.2.0",
                "ruleset_version": "0.2.0a2",
                "findings": all_findings,
                "findings_shown": all_findings,
                "all_findings": all_findings,
            }
        ),
        encoding="utf-8",
    )
    return root


def test_same_track_diff_emits_only_descriptive_deltas_and_prompt_churn(tmp_path: Path) -> None:
    common = _finding("levels.common")
    changed_a = _finding("levels.changed", title="Earlier wording")
    changed_b = _finding("levels.changed", title="Later wording")
    report_a = _write_report(
        tmp_path / "a",
        summary=_summary("mix-v3.wav", lufs=-12.0, true_peak=-1.0, band_median=-7.0),
        all_findings=[common, changed_a, _finding("levels.disappeared")],
    )
    report_b = _write_report(
        tmp_path / "b",
        summary=_summary("mix-v4.wav", lufs=-10.5, true_peak=-0.4, band_median=-4.5),
        all_findings=[common, changed_b, _finding("levels.appeared")],
    )

    payload = generate_revision_diff(report_a, report_b)

    assert payload["comparison_kind"] == "same-track-revision"
    assert payload["same_track"]["status"] == "matched"
    assert payload["comparability"]["status"] == "exact"
    metric = next(item for item in payload["metric_deltas"] if item["metric"] == "levels.integrated_lufs")
    assert metric["delta_b_minus_a"] == pytest.approx(1.5)
    assert payload["band_power_median_deltas"][0]["delta_b_minus_a_db"] == pytest.approx(2.5)
    for side in ("a", "b"):
        context = payload["source_context"][side]
        assert len(context["summary_sha256"]) == 64
        assert len(context["findings_sha256"]) == 64
        assert len(context["report_snapshot_sha256"]) == 64
    changes = payload["finding_changes"]
    assert {item["rule_id"] for item in changes["appeared"]} == {"levels.appeared"}
    assert {item["rule_id"] for item in changes["disappeared"]} == {"levels.disappeared"}
    assert [item["rule_id"] for item in changes["changed"]] == ["levels.changed"]
    assert changes["changed"][0]["changed_fields"] == ["title"]
    assert changes["unchanged_count"] == 1
    text = json.dumps(payload).lower()
    for forbidden in (" better ", " worse ", "winner", "grade", "leaderboard"):
        assert forbidden not in f" {text} "


def test_diff_requires_identity_or_explicit_same_track_confirmation(tmp_path: Path) -> None:
    report_a = _write_report(tmp_path / "a", summary=_summary("a.wav", track_id=None), all_findings=[])
    report_b = _write_report(tmp_path / "b", summary=_summary("b.wav", track_id=None), all_findings=[])

    with pytest.raises(RevisionDiffError, match="Same-track identity is not established"):
        generate_revision_diff(report_a, report_b)

    payload = generate_revision_diff(report_a, report_b, confirm_same_track=True)
    assert payload["same_track"]["status"] == "asserted"
    assert payload["same_track"]["explicit_confirmation_used"] is True


def test_conflicting_track_ids_are_never_overridden(tmp_path: Path) -> None:
    report_a = _write_report(tmp_path / "a", summary=_summary("a.wav", track_id="song-one"), all_findings=[])
    report_b = _write_report(tmp_path / "b", summary=_summary("b.wav", track_id="song-two"), all_findings=[])

    with pytest.raises(RevisionDiffError, match="different track-identity digests"):
        generate_revision_diff(
            report_a,
            report_b,
            confirm_same_track=True,
            allow_incomparable=True,
        )


def test_comparability_levels_and_override_are_explicit(tmp_path: Path) -> None:
    provenance_a = build_analysis_provenance(AnalysisConfig(true_peak_oversample=1))
    provenance_compatible = deepcopy(provenance_a)
    provenance_compatible["environment"] = {"python_version": "different"}
    provenance_compatible["exact_environment_sha256"] = "f" * 64
    report_a = _write_report(
        tmp_path / "a",
        summary=_summary("a.wav", provenance=provenance_a),
        all_findings=[],
    )
    report_b = _write_report(
        tmp_path / "b",
        summary=_summary("b.wav", provenance=provenance_compatible),
        all_findings=[],
    )
    compatible = generate_revision_diff(report_a, report_b)
    assert compatible["comparability"]["status"] == "compatible"
    assert compatible["comparability"]["finding_rules"]["status"] == "matching"

    different_rules = deepcopy(provenance_a)
    different_rules["finding_rule_code_sha256"] = "d" * 64
    different_rules["finding_ruleset_version"] = "candidate-rules"
    report_rules = _write_report(
        tmp_path / "rules",
        summary=_summary("rules.wav", provenance=different_rules),
        all_findings=[],
    )
    rule_caveat = generate_revision_diff(report_a, report_rules)
    assert rule_caveat["comparability"]["status"] == "exact"
    assert rule_caveat["comparability"]["finding_rules"]["status"] == "differing"
    assert rule_caveat["finding_changes"]["attribution"] == (
        "source-and-or-rule-implementation"
    )

    different = deepcopy(provenance_a)
    different["analysis_config_sha256"] = "a" * 64
    different["compatible_analysis_sha256"] = "b" * 64
    different["exact_environment_sha256"] = "c" * 64
    report_c = _write_report(
        tmp_path / "c",
        summary=_summary("c.wav", provenance=different),
        all_findings=[],
    )
    with pytest.raises(RevisionDiffError, match="do not carry matching analysis provenance"):
        generate_revision_diff(report_a, report_c)

    overridden = generate_revision_diff(report_a, report_c, allow_incomparable=True)
    assert overridden["comparability"]["status"] == "incomparable"
    assert overridden["comparability"]["override_used"] is True
    assert "Analysis configuration differs." in overridden["comparability"]["reasons"]


def test_revision_diff_writes_static_owned_report_and_cli_uses_guardrails(tmp_path: Path) -> None:
    report_a = _write_report(tmp_path / "a", summary=_summary("a.wav", lufs=-12), all_findings=[])
    report_b = _write_report(tmp_path / "b", summary=_summary("b.wav", lufs=-11), all_findings=[])
    out = tmp_path / "delta"
    human = out / "notes.txt"
    out.mkdir()
    human.write_text("keep", encoding="utf-8")
    (out / "summary.json").write_text("stale report", encoding="utf-8")
    (out / "waveform_rms.png").write_bytes(b"stale plot")

    payload = generate_revision_diff(report_a, report_b, label_a="Revision 3", label_b="Revision 4")
    paths = write_revision_diff(payload, out)

    assert all(path.exists() for path in paths.values())
    assert human.read_text(encoding="utf-8") == "keep"
    assert not (out / "summary.json").exists()
    assert not (out / "waveform_rms.png").exists()
    manifest = json.loads((out / OUTPUT_MARKER_FILENAME).read_text(encoding="utf-8"))
    assert manifest["kind"] == "same-track-revision-diff"
    assert manifest["audioatlas_version"] == "0.2.0a5"
    markdown = paths["markdown"].read_text(encoding="utf-8").lower()
    html = paths["html"].read_text(encoding="utf-8").lower()
    assert "deltas are b minus a" in markdown
    assert "interpretation boundary" in html
    for text in (markdown, html):
        for forbidden in ("better", "worse", "winner", "leaderboard"):
            assert forbidden not in text

    cli_out = tmp_path / "cli-delta"
    result = CliRunner().invoke(
        main,
        ["diff", str(report_a), str(report_b), "--out", str(cli_out)],
    )
    assert result.exit_code == 0, result.output
    assert "revision delta written to" in result.output.lower()
    assert (cli_out / "revision_diff.html").exists()


def test_diff_cli_refuses_to_overwrite_either_source_report(tmp_path: Path) -> None:
    report_a = _write_report(
        tmp_path / "a",
        summary=_summary("a.wav"),
        all_findings=[],
    )
    report_b = _write_report(
        tmp_path / "b",
        summary=_summary("b.wav"),
        all_findings=[],
    )
    original_summary = (report_a / "summary.json").read_bytes()
    original_findings = (report_a / "findings.json").read_bytes()

    result = CliRunner().invoke(
        main,
        ["diff", str(report_a), str(report_b), "--out", str(report_a)],
    )

    assert result.exit_code != 0
    assert "output must be separate" in result.output
    assert (report_a / "summary.json").read_bytes() == original_summary
    assert (report_a / "findings.json").read_bytes() == original_findings
    assert not (report_a / "revision_diff.json").exists()
