from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prepare_calibration_review.py"


def _write_report(
    report_dir: Path,
    *,
    filename: str,
    all_findings: list[dict],
    shown_findings: list[dict] | None = None,
) -> None:
    report_dir.mkdir(parents=True)
    (report_dir / "summary.json").write_text(
        json.dumps(
            {
                "schema_version": "0.2.0",
                "metadata": {
                    "filename": filename,
                    "path": filename,
                    "path_kind": "basename",
                    "local_paths_included": False,
                },
            }
        ),
        encoding="utf-8",
    )
    shown = all_findings if shown_findings is None else shown_findings
    (report_dir / "findings.json").write_text(
        json.dumps(
            {
                "schema_version": "0.2.0",
                "ruleset_version": "0.2.0a2",
                "findings": shown,
                "findings_shown": shown,
                "all_findings": all_findings,
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
                "kind": "single-report",
                "generated_files": [],
                "generated_directories": [],
            }
        ),
        encoding="utf-8",
    )


def _finding(rule_id: str, *, rule_version: int = 1) -> dict:
    return {
        "rule_id": rule_id,
        "rule_version": rule_version,
        "severity": "warning",
        "category": "levels",
        "title": "Approximate true peak is above 0 dBTP",
        "confidence": "medium",
        "measured_value": 0.2,
        "threshold": 0.0,
        "unit": "dBTP",
        "evidence": "Approximate true peak measured 0.2 dBTP.",
        "why_it_matters": "Reconstructed peaks can exceed nominal full scale.",
        "does_not_mean": "This does not mean the file is audibly distorting.",
        "suggested_checks": ["Check a dedicated true-peak meter."],
        "associated_graphs": ["peak_timeline", "waveform_rms"],
    }


def test_prepare_calibration_review_is_anonymous_and_captures_suppressed_findings(tmp_path):
    reports = tmp_path / "private-reports"
    first = _finding("levels.true_peak_above_zero")
    suppressed = _finding("levels.near_full_scale_samples")
    _write_report(
        reports / "song-one",
        filename="descriptive_private_name.wav",
        all_findings=[first, suppressed],
        shown_findings=[first],
    )
    _write_report(
        reports / "song-two",
        filename="another_private_name.wav",
        all_findings=[],
    )
    out = tmp_path / "review.csv"
    private_map = tmp_path / "private_map.csv"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(reports),
            "--out",
            str(out),
            "--private-map",
            str(private_map),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Prepared 2 asset(s)" in result.stdout
    review_text = out.read_text(encoding="utf-8")
    assert str(tmp_path) not in review_text
    assert "descriptive_private_name.wav" not in review_text
    rows = list(csv.DictReader(review_text.splitlines()))
    assert len(rows) == 3
    assert [row["asset_id"] for row in rows] == ["asset-001", "asset-001", "asset-002"]
    assert rows[0]["triggered"] == "true"
    assert rows[0]["shown_in_report"] == "true"
    assert rows[1]["shown_in_report"] == "false"
    assert rows[2]["triggered"] == "false"
    assert len(rows[0]["report_evidence_sha256"]) == 64
    assert len(rows[0]["finding_payload_sha256"]) == 64
    assert rows[0]["audioatlas_version"] == "0.2.0a3"
    assert rows[0]["ruleset_version"] == "0.2.0a2"
    assert rows[0]["title"] == "Approximate true peak is above 0 dBTP"
    assert rows[0]["does_not_mean"] == (
        "This does not mean the file is audibly distorting."
    )
    assert rows[0]["suggested_checks"] == "Check a dedicated true-peak meter."

    private_text = private_map.read_text(encoding="utf-8")
    assert str(tmp_path) not in private_text
    private_rows = list(csv.DictReader(private_text.splitlines()))
    assert private_rows == [
        {
            "asset_id": "asset-001",
            "source_filename": "descriptive_private_name.wav",
            "report_directory_relative": "song-one",
        },
        {
            "asset_id": "asset-002",
            "source_filename": "another_private_name.wav",
            "report_directory_relative": "song-two",
        },
    ]


def test_prepare_calibration_review_refuses_to_overwrite_without_force(tmp_path):
    reports = tmp_path / "reports"
    _write_report(reports / "one", filename="one.wav", all_findings=[])
    out = tmp_path / "review.csv"
    out.write_text("human labels already here\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(reports), "--out", str(out)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "use --force" in result.stderr
    assert out.read_text(encoding="utf-8") == "human labels already here\n"


def test_prepare_calibration_review_preflights_all_outputs_before_writing(tmp_path):
    reports = tmp_path / "reports"
    _write_report(reports / "one", filename="one.wav", all_findings=[])
    out = tmp_path / "review.csv"
    private_map = tmp_path / "private_map.csv"
    private_map.write_text("private labels already here\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(reports),
            "--out",
            str(out),
            "--private-map",
            str(private_map),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "use --force" in result.stderr
    assert not out.exists()
    assert private_map.read_text(encoding="utf-8") == "private labels already here\n"


def test_prepare_calibration_review_rejects_same_public_and_private_path(tmp_path):
    reports = tmp_path / "reports"
    _write_report(reports / "one", filename="one.wav", all_findings=[])
    out = tmp_path / "review.csv"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(reports),
            "--out",
            str(out),
            "--private-map",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "different output paths" in result.stderr
    assert not out.exists()


def test_finding_review_template_matches_preparation_script_schema():
    import importlib.util

    spec = importlib.util.spec_from_file_location("prepare_calibration_review", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    template = ROOT / "docs" / "calibration" / "finding_review_template.csv"
    header = next(csv.reader(template.read_text(encoding="utf-8").splitlines()))
    assert tuple(header) == module.REVIEW_FIELDS
