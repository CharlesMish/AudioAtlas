#!/usr/bin/env python3
"""Prepare a privacy-conscious human review sheet from AudioAtlas reports.

This is a maintainer tool, not part of the end-user CLI. It reads completed
report folders, assigns anonymous asset IDs, and emits one row per triggered
finding. Audio files are never opened or copied.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

OUTPUT_MARKER_FILENAME = ".audioatlas-output.json"
REVIEW_FIELDS = (
    "asset_id",
    "audioatlas_version",
    "summary_schema_version",
    "findings_schema_version",
    "ruleset_version",
    "analysis_config_sha256",
    "measurement_code_sha256",
    "finding_rule_code_sha256",
    "compatible_analysis_sha256",
    "exact_environment_sha256",
    "report_evidence_sha256",
    "finding_payload_sha256",
    "triggered",
    "shown_in_report",
    "rule_id",
    "rule_version",
    "severity",
    "category",
    "title",
    "confidence",
    "measured_value",
    "threshold",
    "unit",
    "triggering_evidence",
    "why_it_matters",
    "does_not_mean",
    "suggested_checks",
    "associated_graphs",
    "outcome",
    "evidence_easy_to_trace",
    "listening_check_completed",
    "listening_check_useful",
    "non_claim_effective",
    "proposed_action",
    "reviewer",
    "review_date",
    "notes",
)
PRIVATE_MAP_FIELDS = ("asset_id", "source_filename", "report_directory_relative")


class CalibrationPreparationError(ValueError):
    """Raised when a report set cannot be converted safely."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create an anonymous calibration worksheet from completed AudioAtlas reports."
        )
    )
    parser.add_argument(
        "report_root",
        type=Path,
        help="Folder containing one report or nested report folders.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="CSV worksheet to create.",
    )
    parser.add_argument(
        "--private-map",
        type=Path,
        default=None,
        help=(
            "Optional private CSV mapping anonymous asset IDs to source basenames and "
            "report folders. Keep this file out of version control."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace existing output CSV files.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        rows, private_rows = prepare_review_rows(args.report_root)
        output_targets = [args.out]
        if args.private_map is not None:
            output_targets.append(args.private_map)
        _validate_output_targets(output_targets, force=args.force)
        _write_csv(args.out, REVIEW_FIELDS, rows, force=args.force)
        if args.private_map is not None:
            _write_csv(
                args.private_map,
                PRIVATE_MAP_FIELDS,
                private_rows,
                force=args.force,
            )
    except (CalibrationPreparationError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    triggered = sum(row["triggered"] == "true" for row in rows)
    untriggered = sum(row["triggered"] == "false" for row in rows)
    print(
        f"Prepared {len(private_rows)} asset(s): {triggered} triggered row(s), "
        f"{untriggered} no-finding row(s)."
    )
    print(f"Review worksheet: {args.out}")
    if args.private_map is not None:
        print(f"Private asset map: {args.private_map}")
    return 0


def prepare_review_rows(
    report_root: Path,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    root = report_root.expanduser()
    if not root.exists():
        raise CalibrationPreparationError(f"report root does not exist: {root}")
    if not root.is_dir():
        raise CalibrationPreparationError(f"report root is not a folder: {root}")

    report_dirs = _discover_report_directories(root)
    if not report_dirs:
        raise CalibrationPreparationError(
            "no completed AudioAtlas report folders were found (expected findings.json, "
            "summary.json, and .audioatlas-output.json)"
        )

    rows: list[dict[str, str]] = []
    private_rows: list[dict[str, str]] = []
    for index, report_dir in enumerate(report_dirs, start=1):
        asset_id = f"asset-{index:03d}"
        summary_path = report_dir / "summary.json"
        findings_path = report_dir / "findings.json"
        marker_path = report_dir / OUTPUT_MARKER_FILENAME
        summary = _read_object(summary_path)
        findings_payload = _read_object(findings_path)
        marker = _read_object(marker_path)

        source_filename = _source_filename(summary)
        relative_dir = _relative_report_directory(root, report_dir)
        private_rows.append(
            {
                "asset_id": asset_id,
                "source_filename": source_filename,
                "report_directory_relative": relative_dir,
            }
        )

        provenance = (
            summary.get("analysis_provenance")
            if isinstance(summary.get("analysis_provenance"), dict)
            else {}
        )
        common = {
            "asset_id": asset_id,
            "audioatlas_version": _string(marker.get("audioatlas_version")),
            "summary_schema_version": _string(summary.get("schema_version")),
            "findings_schema_version": _string(findings_payload.get("schema_version")),
            "ruleset_version": _string(findings_payload.get("ruleset_version")),
            "analysis_config_sha256": _string(provenance.get("analysis_config_sha256")),
            "measurement_code_sha256": _string(provenance.get("measurement_code_sha256")),
            "finding_rule_code_sha256": _string(
                provenance.get("finding_rule_code_sha256")
            ),
            "compatible_analysis_sha256": _string(
                provenance.get("compatible_analysis_sha256")
            ),
            "exact_environment_sha256": _string(
                provenance.get("exact_environment_sha256")
            ),
            "report_evidence_sha256": _report_digest(
                summary_path, findings_path, marker_path
            ),
        }
        all_findings = _finding_list(findings_payload, "all_findings")
        if not all_findings:
            all_findings = _finding_list(findings_payload, "findings")
        shown_keys = {
            _finding_key(item)
            for item in _finding_list(findings_payload, "findings_shown")
            or _finding_list(findings_payload, "findings")
        }

        if not all_findings:
            rows.append(_empty_review_row(common, triggered=False))
            continue

        for finding in all_findings:
            row = _empty_review_row(common, triggered=True)
            row.update(
                {
                    "finding_payload_sha256": _finding_digest(finding),
                    "shown_in_report": _bool_text(_finding_key(finding) in shown_keys),
                    "rule_id": _string(finding.get("rule_id")),
                    "rule_version": _string(finding.get("rule_version")),
                    "severity": _string(finding.get("severity")),
                    "category": _string(finding.get("category")),
                    "title": _string(finding.get("title")),
                    "confidence": _string(finding.get("confidence")),
                    "measured_value": _string(finding.get("measured_value")),
                    "threshold": _string(finding.get("threshold")),
                    "unit": _string(finding.get("unit")),
                    "triggering_evidence": _string(finding.get("evidence")),
                    "why_it_matters": _string(finding.get("why_it_matters")),
                    "does_not_mean": _string(finding.get("does_not_mean")),
                    "suggested_checks": _string_list(finding.get("suggested_checks")),
                    "associated_graphs": _string_list(finding.get("associated_graphs")),
                }
            )
            rows.append(row)

    return rows, private_rows


def _discover_report_directories(root: Path) -> list[Path]:
    candidates: set[Path] = set()
    if (root / "findings.json").is_file():
        candidates.add(root)
    for findings_path in root.rglob("findings.json"):
        candidates.add(findings_path.parent)

    completed = [
        path
        for path in candidates
        if (path / "summary.json").is_file()
        and (path / OUTPUT_MARKER_FILENAME).is_file()
    ]
    return sorted(completed, key=lambda path: path.relative_to(root).as_posix().casefold())


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CalibrationPreparationError(f"expected a JSON object in {path.name}")
    return value


def _finding_list(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _finding_key(finding: dict[str, Any]) -> tuple[str, str]:
    return (_string(finding.get("rule_id")), _string(finding.get("rule_version")))


def _source_filename(summary: dict[str, Any]) -> str:
    metadata = summary.get("metadata")
    if not isinstance(metadata, dict):
        return ""
    return _string(metadata.get("filename"))


def _relative_report_directory(root: Path, report_dir: Path) -> str:
    relative = report_dir.relative_to(root)
    return "." if not relative.parts else relative.as_posix()


def _report_digest(*paths: Path) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _finding_digest(finding: dict[str, Any]) -> str:
    canonical = json.dumps(
        finding,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _empty_review_row(common: dict[str, str], *, triggered: bool) -> dict[str, str]:
    row = {field: "" for field in REVIEW_FIELDS}
    row.update(common)
    row["triggered"] = _bool_text(triggered)
    row["shown_in_report"] = _bool_text(triggered)
    return row


def _string(value: object) -> str:
    if value is None or isinstance(value, bool):
        return ""
    return str(value)


def _string_list(value: object) -> str:
    if not isinstance(value, list):
        return ""
    return ";".join(str(item) for item in value if isinstance(item, str))


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _write_csv(
    path: Path,
    fields: tuple[str, ...],
    rows: list[dict[str, str]],
    *,
    force: bool,
) -> None:
    target = path.expanduser()
    if target.exists() and not force:
        raise CalibrationPreparationError(
            f"output already exists: {target} (use --force to replace it)"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _validate_output_targets(paths: list[Path], *, force: bool) -> None:
    normalized = [path.expanduser().absolute() for path in paths]
    if len(set(normalized)) != len(normalized):
        raise CalibrationPreparationError(
            "review worksheet and private map must use different output paths"
        )
    if force:
        return
    existing = [path for path in normalized if path.exists()]
    if existing:
        names = ", ".join(path.name for path in existing)
        raise CalibrationPreparationError(
            f"output already exists: {names} (use --force to replace it)"
        )


if __name__ == "__main__":
    raise SystemExit(main())
