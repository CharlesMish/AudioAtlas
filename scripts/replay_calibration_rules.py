#!/usr/bin/env python3
"""Replay the current finding rules over a frozen calibration report corpus.

The tool never opens or copies audio. It verifies each completed report against
its anonymous human-review ledger, regenerates findings from the saved
``summary.json`` using the current checkout, and records prompt-level churn.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if (ROOT / "src").is_dir():
    sys.path.insert(0, str(ROOT / "src"))

from audioatlas import __version__  # noqa: E402
from audioatlas.analysis.findings import generate_findings  # noqa: E402
from audioatlas.provenance import finding_rule_code_sha256  # noqa: E402
from audioatlas.release import CALIBRATION_REPLAY_SCHEMA_VERSION  # noqa: E402

OUTPUT_MARKER_FILENAME = ".audioatlas-output.json"
ASSET_MAP_FIELDS = ("asset_id", "source_filename", "report_directory_relative")
CSV_FIELDS = (
    "asset_id",
    "status",
    "rule_id",
    "baseline_rule_version",
    "candidate_rule_version",
    "baseline_title",
    "candidate_title",
    "baseline_shown",
    "candidate_shown",
    "changed_fields",
    "baseline_finding_sha256",
    "candidate_finding_sha256",
    "summary_sha256",
    "compatible_analysis_sha256",
    "baseline_finding_rule_code_sha256",
    "candidate_finding_rule_code_sha256",
    "baseline_ruleset_version",
    "candidate_ruleset_version",
)
SNAPSHOT_FIELDS = (
    "rule_id",
    "rule_version",
    "severity",
    "category",
    "title",
    "measured_value",
    "threshold",
    "unit",
    "evidence",
    "why_it_matters",
    "does_not_mean",
    "suggested_checks",
    "associated_graphs",
    "time_ranges",
    "evidence_items",
)


class CalibrationReplayError(ValueError):
    """Raised when the frozen calibration evidence cannot be replayed safely."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Replay the current AudioAtlas finding rules over frozen, previously reviewed "
            "summary.json files without opening the source audio."
        )
    )
    parser.add_argument("report_root", type=Path, help="Root containing completed reports.")
    parser.add_argument(
        "--asset-map",
        type=Path,
        required=True,
        help="Private asset map created by prepare_calibration_review.py.",
    )
    parser.add_argument(
        "--review-ledger",
        type=Path,
        required=True,
        help=(
            "Frozen anonymous finding_review.csv. Its report hashes are checked before replay."
        ),
    )
    parser.add_argument("--out", type=Path, required=True, help="JSON replay report to create.")
    parser.add_argument(
        "--csv",
        dest="csv_path",
        type=Path,
        default=None,
        help="Optional row-level CSV. Defaults to the JSON path with a .csv suffix.",
    )
    parser.add_argument("--force", action="store_true", help="Replace existing outputs.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    csv_path = args.csv_path or args.out.with_suffix(".csv")
    try:
        _preflight_outputs(
            [args.out, csv_path],
            force=args.force,
            protected_paths=[args.asset_map, args.review_ledger],
        )
        payload = replay_calibration_rules(
            args.report_root,
            asset_map_path=args.asset_map,
            review_ledger_path=args.review_ledger,
        )
        _write_json(args.out, payload)
        _write_csv(csv_path, payload["changes"])
    except (
        CalibrationReplayError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        csv.Error,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    counts = payload["summary"]["status_counts"]
    print(
        f"Replayed {payload['asset_count']} asset(s): "
        f"{counts.get('appeared', 0)} appeared, "
        f"{counts.get('disappeared', 0)} disappeared, "
        f"{counts.get('changed', 0)} changed, "
        f"{counts.get('unchanged', 0)} unchanged."
    )
    print(f"Replay JSON: {args.out}")
    print(f"Replay CSV:  {csv_path}")
    return 0


def replay_calibration_rules(
    report_root: Path,
    *,
    asset_map_path: Path,
    review_ledger_path: Path,
) -> dict[str, Any]:
    """Replay the current rules and return an anonymous churn report."""

    root = report_root.expanduser()
    if not root.is_dir():
        raise CalibrationReplayError(f"report root is not a folder: {root}")
    asset_rows = _read_csv(asset_map_path)
    expected_hashes = _review_hashes(review_ledger_path)
    if not asset_rows:
        raise CalibrationReplayError("asset map contains no assets")

    changes: list[dict[str, Any]] = []
    candidate_rule_code_hash = finding_rule_code_sha256()
    baseline_rulesets: set[str] = set()
    candidate_rulesets: set[str] = set()
    seen_assets: set[str] = set()

    for row in asset_rows:
        asset_id = _required_cell(row, "asset_id", source=asset_map_path.name)
        if asset_id in seen_assets:
            raise CalibrationReplayError(f"duplicate asset_id in asset map: {asset_id}")
        seen_assets.add(asset_id)
        relative = _required_cell(
            row,
            "report_directory_relative",
            source=asset_map_path.name,
        )
        report_dir = _safe_report_directory(root, relative)
        summary_path = report_dir / "summary.json"
        findings_path = report_dir / "findings.json"
        marker_path = report_dir / OUTPUT_MARKER_FILENAME
        for required in (summary_path, findings_path, marker_path):
            if not required.is_file():
                raise CalibrationReplayError(
                    f"asset {asset_id} lacks required report file: {required.name}"
                )

        observed_report_hash = _report_digest(summary_path, findings_path, marker_path)
        expected_report_hash = expected_hashes.get(asset_id)
        if expected_report_hash is None:
            raise CalibrationReplayError(
                f"asset {asset_id} is absent from the frozen review ledger"
            )
        if observed_report_hash != expected_report_hash:
            raise CalibrationReplayError(
                f"frozen evidence mismatch for {asset_id}; regenerate or restore the reviewed reports"
            )

        summary = _read_object(summary_path)
        baseline = _read_object(findings_path)
        try:
            candidate = generate_findings(summary).to_dict()
        except (KeyError, TypeError, ValueError) as exc:
            raise CalibrationReplayError(
                f"candidate finding rules could not replay {asset_id}: {exc}"
            ) from exc
        baseline_ruleset = _string(baseline.get("ruleset_version"))
        candidate_ruleset = _string(candidate.get("ruleset_version"))
        baseline_rulesets.add(baseline_ruleset)
        candidate_rulesets.add(candidate_ruleset)

        summary_hash = _file_sha256(summary_path)
        compatible_signature = _compatible_signature(summary)
        baseline_rule_code_hash = _provenance_hash(
            summary, "finding_rule_code_sha256"
        )
        changes.extend(
            _compare_findings(
                asset_id=asset_id,
                baseline=baseline,
                candidate=candidate,
                summary_sha256=summary_hash,
                compatible_analysis_sha256=compatible_signature,
                baseline_finding_rule_code_sha256=baseline_rule_code_hash,
                candidate_finding_rule_code_sha256=candidate_rule_code_hash,
                baseline_ruleset_version=baseline_ruleset,
                candidate_ruleset_version=candidate_ruleset,
            )
        )

    missing_from_map = sorted(set(expected_hashes) - seen_assets)
    if missing_from_map:
        raise CalibrationReplayError(
            "review ledger contains assets missing from the asset map: "
            + ", ".join(missing_from_map)
        )

    status_counts = Counter(str(row["status"]) for row in changes)
    by_rule: dict[str, Counter[str]] = defaultdict(Counter)
    for row in changes:
        by_rule[str(row["rule_id"])][str(row["status"])] += 1

    return {
        "schema_version": CALIBRATION_REPLAY_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "audioatlas_version": __version__,
        "mode": "saved-summary-rule-replay",
        "asset_count": len(seen_assets),
        "baseline_ruleset_versions": sorted(baseline_rulesets),
        "candidate_ruleset_versions": sorted(candidate_rulesets),
        "candidate_finding_rule_code_sha256": candidate_rule_code_hash,
        "frozen_evidence_verified": True,
        "privacy_boundary": (
            "Output uses anonymous asset IDs and does not include filenames, report paths, "
            "audio paths, or audio content."
        ),
        "interpretation_boundary": (
            "Prompt churn shows how the current rule implementation differs on saved analysis "
            "summaries. It does not replace human listening labels or re-run audio measurements."
        ),
        "summary": {
            "status_counts": dict(sorted(status_counts.items())),
            "by_rule": {
                rule_id: dict(sorted(counts.items()))
                for rule_id, counts in sorted(by_rule.items())
            },
        },
        "changes": changes,
    }


def _compare_findings(
    *,
    asset_id: str,
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    summary_sha256: str,
    compatible_analysis_sha256: str | None,
    baseline_finding_rule_code_sha256: str | None,
    candidate_finding_rule_code_sha256: str,
    baseline_ruleset_version: str,
    candidate_ruleset_version: str,
) -> list[dict[str, Any]]:
    baseline_items = {_rule_id(item): item for item in _all_findings(baseline)}
    candidate_items = {_rule_id(item): item for item in _all_findings(candidate)}
    baseline_items.pop(None, None)
    candidate_items.pop(None, None)
    baseline_shown = {_rule_id(item) for item in _shown_findings(baseline)}
    candidate_shown = {_rule_id(item) for item in _shown_findings(candidate)}

    rows: list[dict[str, Any]] = []
    all_rule_ids = sorted(set(baseline_items) | set(candidate_items))
    if not all_rule_ids:
        rows.append(
            _change_row(
                asset_id=asset_id,
                status="unchanged",
                rule_id="(no-findings)",
                baseline_item=None,
                candidate_item=None,
                baseline_shown=False,
                candidate_shown=False,
                changed_fields=[],
                summary_sha256=summary_sha256,
                compatible_analysis_sha256=compatible_analysis_sha256,
                baseline_finding_rule_code_sha256=baseline_finding_rule_code_sha256,
                candidate_finding_rule_code_sha256=candidate_finding_rule_code_sha256,
                baseline_ruleset_version=baseline_ruleset_version,
                candidate_ruleset_version=candidate_ruleset_version,
            )
        )
        return rows

    for rule_id in all_rule_ids:
        baseline_item = baseline_items.get(rule_id)
        candidate_item = candidate_items.get(rule_id)
        if baseline_item is None:
            status = "appeared"
            changed_fields: list[str] = []
        elif candidate_item is None:
            status = "disappeared"
            changed_fields = []
        else:
            baseline_snapshot = _snapshot(baseline_item)
            candidate_snapshot = _snapshot(candidate_item)
            changed_fields = [
                key
                for key in SNAPSHOT_FIELDS
                if baseline_snapshot.get(key) != candidate_snapshot.get(key)
            ]
            status = "changed" if changed_fields else "unchanged"
        rows.append(
            _change_row(
                asset_id=asset_id,
                status=status,
                rule_id=rule_id,
                baseline_item=baseline_item,
                candidate_item=candidate_item,
                baseline_shown=rule_id in baseline_shown,
                candidate_shown=rule_id in candidate_shown,
                changed_fields=changed_fields,
                summary_sha256=summary_sha256,
                compatible_analysis_sha256=compatible_analysis_sha256,
                baseline_finding_rule_code_sha256=baseline_finding_rule_code_sha256,
                candidate_finding_rule_code_sha256=candidate_finding_rule_code_sha256,
                baseline_ruleset_version=baseline_ruleset_version,
                candidate_ruleset_version=candidate_ruleset_version,
            )
        )
    return rows


def _change_row(
    *,
    asset_id: str,
    status: str,
    rule_id: str,
    baseline_item: dict[str, Any] | None,
    candidate_item: dict[str, Any] | None,
    baseline_shown: bool,
    candidate_shown: bool,
    changed_fields: list[str],
    summary_sha256: str,
    compatible_analysis_sha256: str | None,
    baseline_finding_rule_code_sha256: str | None,
    candidate_finding_rule_code_sha256: str,
    baseline_ruleset_version: str,
    candidate_ruleset_version: str,
) -> dict[str, Any]:
    return {
        "asset_id": asset_id,
        "status": status,
        "rule_id": rule_id,
        "baseline_rule_version": _item_value(baseline_item, "rule_version"),
        "candidate_rule_version": _item_value(candidate_item, "rule_version"),
        "baseline_title": _item_value(baseline_item, "title"),
        "candidate_title": _item_value(candidate_item, "title"),
        "baseline_shown": baseline_shown,
        "candidate_shown": candidate_shown,
        "changed_fields": changed_fields,
        "baseline_finding_sha256": _finding_digest(baseline_item),
        "candidate_finding_sha256": _finding_digest(candidate_item),
        "summary_sha256": summary_sha256,
        "compatible_analysis_sha256": compatible_analysis_sha256,
        "baseline_finding_rule_code_sha256": baseline_finding_rule_code_sha256,
        "candidate_finding_rule_code_sha256": candidate_finding_rule_code_sha256,
        "baseline_ruleset_version": baseline_ruleset_version,
        "candidate_ruleset_version": candidate_ruleset_version,
    }


def _all_findings(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("all_findings", "findings_shown", "findings"):
        value = payload.get(key)
        if isinstance(value, list):
            items = [item for item in value if isinstance(item, dict)]
            if items or key == "findings":
                return items
    return []


def _shown_findings(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("findings_shown", "findings"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _snapshot(item: dict[str, Any]) -> dict[str, Any]:
    return {key: item.get(key) for key in SNAPSHOT_FIELDS}


def _rule_id(item: dict[str, Any]) -> str | None:
    value = item.get("rule_id")
    return value if isinstance(value, str) and value else None


def _item_value(item: dict[str, Any] | None, key: str) -> Any:
    return item.get(key) if isinstance(item, dict) else None


def _finding_digest(item: dict[str, Any] | None) -> str | None:
    return _canonical_sha256(_snapshot(item)) if isinstance(item, dict) else None


def _compatible_signature(summary: dict[str, Any]) -> str | None:
    return _provenance_hash(summary, "compatible_analysis_sha256")


def _provenance_hash(summary: dict[str, Any], key: str) -> str | None:
    block = summary.get("analysis_provenance")
    if not isinstance(block, dict):
        return None
    value = block.get(key)
    return value if isinstance(value, str) and len(value) == 64 else None


def _safe_report_directory(root: Path, relative: str) -> Path:
    candidate = root if relative == "." else root / relative
    try:
        resolved_root = root.resolve()
        resolved_candidate = candidate.resolve()
        resolved_candidate.relative_to(resolved_root)
    except (OSError, ValueError) as exc:
        raise CalibrationReplayError(
            f"asset map report directory escapes the report root: {relative!r}"
        ) from exc
    return resolved_candidate


def _review_hashes(path: Path) -> dict[str, str]:
    rows = _read_csv(path)
    hashes: dict[str, str] = {}
    for row in rows:
        asset_id = _required_cell(row, "asset_id", source=path.name)
        digest = _required_cell(row, "report_evidence_sha256", source=path.name)
        if len(digest) != 64:
            raise CalibrationReplayError(
                f"invalid report_evidence_sha256 for {asset_id} in {path.name}"
            )
        previous = hashes.get(asset_id)
        if previous is not None and previous != digest:
            raise CalibrationReplayError(
                f"inconsistent report hashes for {asset_id} in {path.name}"
            )
        hashes[asset_id] = digest
    return hashes


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise CalibrationReplayError(f"CSV file does not exist: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise CalibrationReplayError(f"CSV has no header: {path.name}")
        return [dict(row) for row in reader]


def _required_cell(row: dict[str, str], key: str, *, source: str) -> str:
    value = row.get(key, "").strip()
    if not value:
        raise CalibrationReplayError(f"missing {key} in {source}")
    return value


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CalibrationReplayError(f"expected a JSON object in {path.name}")
    return value


def _report_digest(*paths: Path) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _string(value: object) -> str:
    return "" if value is None or isinstance(value, bool) else str(value)


def _preflight_outputs(
    paths: list[Path],
    *,
    force: bool,
    protected_paths: list[Path] | None = None,
) -> None:
    resolved = [path.expanduser().resolve() for path in paths]
    if len(set(resolved)) != len(resolved):
        raise CalibrationReplayError("JSON and CSV outputs must use different paths")
    protected = {
        path.expanduser().resolve()
        for path in (protected_paths or [])
    }
    collisions = [path for path in resolved if path in protected]
    if collisions:
        raise CalibrationReplayError(
            "replay outputs must not replace the frozen asset map or review ledger"
        )
    if not force:
        existing = [path for path in paths if path.exists()]
        if existing:
            raise CalibrationReplayError(
                f"output already exists: {existing[0]} (use --force to replace it)"
            )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, changes: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for change in changes:
            row = dict(change)
            row["changed_fields"] = ";".join(change.get("changed_fields", []))
            row["baseline_shown"] = str(bool(change.get("baseline_shown"))).lower()
            row["candidate_shown"] = str(bool(change.get("candidate_shown"))).lower()
            writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})


if __name__ == "__main__":
    raise SystemExit(main())
