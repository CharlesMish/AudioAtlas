from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREPARE = ROOT / "scripts" / "prepare_calibration_review.py"
REPLAY = ROOT / "scripts" / "replay_calibration_rules.py"


def _write_report(
    report_dir: Path,
    *,
    true_peak: float,
    baseline_findings: list[dict] | None = None,
) -> None:
    report_dir.mkdir(parents=True)
    summary = {
        "schema_version": "0.2.1",
        "metadata": {
            "filename": "private descriptive mix name.wav",
            "path": "private descriptive mix name.wav",
            "path_kind": "basename",
            "local_paths_included": False,
            "format": "WAV",
            "subtype": "PCM_24",
            "samplerate": 48_000,
            "channels": 2,
        },
        "analysis_config": {
            "max_findings": 8,
            "finding_min_time_range_seconds": 0.25,
        },
        "analysis_provenance": {
            "compatible_analysis_sha256": "a" * 64,
            "finding_rule_code_sha256": "b" * 64,
        },
        "levels": {
            "duration_seconds": 90.0,
            "true_peak_dbtp": true_peak,
            "near_clipping_samples": 0,
            "clipped_samples": 0,
            "plr_db": 10.0,
        },
        "peak_timeline": {"near_clipping_time_ranges": []},
        "stereo_correlation": {},
        "mid_side_energy": {},
    }
    (report_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    findings = baseline_findings or []
    (report_dir / "findings.json").write_text(
        json.dumps(
            {
                "schema_version": "0.2.0",
                "ruleset_version": "baseline-test",
                "findings": findings,
                "findings_shown": findings,
                "all_findings": findings,
            }
        ),
        encoding="utf-8",
    )
    (report_dir / ".audioatlas-output.json").write_text(
        json.dumps(
            {
                "format": "audioatlas-output-manifest",
                "manifest_version": 1,
                "audioatlas_version": "0.2.0a3",
                "kind": "single-track-report",
                "generated_files": [],
                "generated_directories": [],
            }
        ),
        encoding="utf-8",
    )


def _prepare(reports: Path, review: Path, private_map: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(PREPARE),
            str(reports),
            "--out",
            str(review),
            "--private-map",
            str(private_map),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_replay_verifies_frozen_evidence_and_reports_anonymous_prompt_churn(
    tmp_path: Path,
) -> None:
    reports = tmp_path / "private-reports"
    _write_report(reports / "mix-a", true_peak=0.3)
    review = tmp_path / "finding_review.csv"
    private_map = tmp_path / "private_asset_map.csv"
    prepared = _prepare(reports, review, private_map)
    assert prepared.returncode == 0, prepared.stderr

    out = tmp_path / "replay.json"
    csv_out = tmp_path / "replay.csv"
    replayed = subprocess.run(
        [
            sys.executable,
            str(REPLAY),
            str(reports),
            "--asset-map",
            str(private_map),
            "--review-ledger",
            str(review),
            "--out",
            str(out),
            "--csv",
            str(csv_out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert replayed.returncode == 0, replayed.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["frozen_evidence_verified"] is True
    assert payload["generated_at"].endswith("Z")
    assert payload["asset_count"] == 1
    assert payload["summary"]["status_counts"] == {"appeared": 1}
    assert payload["changes"][0]["asset_id"] == "asset-001"
    assert payload["changes"][0]["rule_id"] == "levels.true_peak_above_zero"
    assert payload["changes"][0]["status"] == "appeared"
    assert payload["changes"][0]["candidate_ruleset_version"] == "0.2.0a2"
    assert payload["changes"][0]["baseline_finding_rule_code_sha256"] == "b" * 64
    assert len(payload["changes"][0]["candidate_finding_rule_code_sha256"]) == 64
    assert payload["changes"][0]["candidate_finding_rule_code_sha256"] == payload[
        "candidate_finding_rule_code_sha256"
    ]
    public_text = out.read_text(encoding="utf-8") + csv_out.read_text(encoding="utf-8")
    assert "private descriptive mix name.wav" not in public_text
    assert str(reports) not in public_text
    rows = list(csv.DictReader(csv_out.read_text(encoding="utf-8").splitlines()))
    assert rows[0]["status"] == "appeared"
    assert rows[0]["candidate_shown"] == "true"


def test_replay_refuses_when_reviewed_report_evidence_has_changed(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    report_dir = reports / "mix-a"
    _write_report(report_dir, true_peak=-1.0)
    review = tmp_path / "finding_review.csv"
    private_map = tmp_path / "private_asset_map.csv"
    prepared = _prepare(reports, review, private_map)
    assert prepared.returncode == 0, prepared.stderr

    summary_path = report_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["levels"]["true_peak_dbtp"] = 0.4
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    out = tmp_path / "replay.json"

    replayed = subprocess.run(
        [
            sys.executable,
            str(REPLAY),
            str(reports),
            "--asset-map",
            str(private_map),
            "--review-ledger",
            str(review),
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert replayed.returncode == 2
    assert "frozen evidence mismatch for asset-001" in replayed.stderr
    assert not out.exists()
    assert not out.with_suffix(".csv").exists()


def test_replay_force_cannot_replace_frozen_map_or_review_ledger(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    _write_report(reports / "mix-a", true_peak=-1.0)
    review = tmp_path / "finding_review.csv"
    private_map = tmp_path / "private_asset_map.csv"
    prepared = _prepare(reports, review, private_map)
    assert prepared.returncode == 0, prepared.stderr
    original_map = private_map.read_bytes()
    csv_out = tmp_path / "replay.csv"

    replayed = subprocess.run(
        [
            sys.executable,
            str(REPLAY),
            str(reports),
            "--asset-map",
            str(private_map),
            "--review-ledger",
            str(review),
            "--out",
            str(private_map),
            "--csv",
            str(csv_out),
            "--force",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert replayed.returncode == 2
    assert "must not replace the frozen asset map or review ledger" in replayed.stderr
    assert private_map.read_bytes() == original_map
    assert not csv_out.exists()
