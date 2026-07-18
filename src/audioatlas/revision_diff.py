"""Guarded descriptive comparison of two revisions of the same track.

This module compares completed AudioAtlas reports. It does not compare audio
files directly, rank revisions, or interpret a numerical direction as merit.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any

from audioatlas import __version__
from audioatlas.errors import RevisionDiffError
from audioatlas.output import (
    ALL_GENERATED_FILENAMES,
    OUTPUT_MARKER_FILENAME,
    REVISION_DIFF_FILENAMES,
    output_transaction,
    publish_staged_output,
    staged_output_directory,
    write_output_manifest,
)
from audioatlas.presentation import (
    presentation_controls_html,
    presentation_css,
    presentation_script,
    skip_link_html,
    validate_presentation_mode,
)
from audioatlas.provenance import canonical_json_sha256, provenance_signature
from audioatlas.release import REVISION_DIFF_SCHEMA_VERSION
from audioatlas.theme import default_theme_name, theme_css_variables, validate_theme_name


@dataclass(frozen=True)
class ReportInputs:
    """Normalized completed-report inputs used by the revision comparator."""

    directory: Path
    summary: dict[str, Any]
    findings: dict[str, Any]


@dataclass(frozen=True)
class MetricSpec:
    path: tuple[str, ...]
    label: str
    unit: str
    decimals: int = 3


METRICS: tuple[MetricSpec, ...] = (
    MetricSpec(("levels", "integrated_lufs"), "Integrated loudness", "LUFS", 2),
    MetricSpec(("levels", "true_peak_dbtp"), "Approximate true peak", "dBTP", 2),
    MetricSpec(("levels", "sample_peak_dbfs"), "Sample peak", "dBFS", 2),
    MetricSpec(("levels", "rms_dbfs"), "RMS", "dBFS", 2),
    MetricSpec(("levels", "plr_db"), "Peak-to-loudness ratio", "dB", 2),
    MetricSpec(("levels", "crest_factor_db"), "Whole-file crest factor", "dB", 2),
    MetricSpec(("levels", "clipped_samples"), "Clipped sample count", "samples", 0),
    MetricSpec(("levels", "near_clipping_samples"), "Near-clipping sample count", "samples", 0),
    MetricSpec(
        ("stereo_correlation", "correlation_median"),
        "Median stereo correlation",
        "Pearson r",
        3,
    ),
    MetricSpec(
        ("mid_side_energy", "side_to_mid_ratio_db_median"),
        "Median side/mid ratio",
        "dB",
        2,
    ),
    MetricSpec(
        ("spectral_shape", "centroid_median_hz"),
        "Median spectral centroid",
        "Hz",
        1,
    ),
    MetricSpec(
        ("spectral_shape", "rolloff_95_median_hz"),
        "Median 95% spectral rolloff",
        "Hz",
        1,
    ),
    MetricSpec(
        ("spectral_shape", "bandwidth_median_hz"),
        "Median spectral bandwidth",
        "Hz",
        1,
    ),
    MetricSpec(
        ("onset_density", "onset_density_median"),
        "Median onset density",
        "relative activity",
        3,
    ),
)


def generate_revision_diff(
    report_a: str | Path,
    report_b: str | Path,
    *,
    confirm_same_track: bool = False,
    allow_incomparable: bool = False,
    label_a: str | None = None,
    label_b: str | None = None,
) -> dict[str, Any]:
    """Return descriptive deltas for two completed same-track reports.

    A matching non-plaintext track token digest is sufficient identity evidence.
    Otherwise the caller must explicitly confirm that both reports are exports
    of the same track. Reports with conflicting tokens are always refused.
    """

    first = load_report_inputs(report_a)
    second = load_report_inputs(report_b)
    same_track = _same_track_assessment(
        first.summary,
        second.summary,
        confirm_same_track=confirm_same_track,
    )
    comparability = _comparability_assessment(first.summary, second.summary)
    if comparability["status"] in {"incomparable", "unknown"} and not allow_incomparable:
        raise RevisionDiffError(
            "The reports do not carry matching analysis provenance. Regenerate them with "
            "the same AudioAtlas/configuration, or pass --allow-incomparable to create a "
            "prominently caveated descriptive report."
        )
    comparability["override_used"] = bool(
        allow_incomparable and comparability["status"] in {"incomparable", "unknown"}
    )

    first_label = _clean_label(label_a) or _source_filename(first.summary) or "Report A"
    second_label = _clean_label(label_b) or _source_filename(second.summary) or "Report B"
    metric_deltas = _metric_deltas(first.summary, second.summary)
    band_deltas = _band_power_deltas(first.summary, second.summary)
    finding_changes = _finding_changes(first.findings, second.findings)
    finding_rule_assessment = comparability["finding_rules"]
    finding_changes["attribution"] = finding_rule_assessment["attribution"]

    return {
        "schema_version": REVISION_DIFF_SCHEMA_VERSION,
        "generated_at": _utc_timestamp(),
        "audioatlas_version": __version__,
        "comparison_kind": "same-track-revision",
        "labels": {"a": first_label, "b": second_label},
        "same_track": same_track,
        "comparability": comparability,
        "source_context": _source_context(first, second),
        "metric_deltas": metric_deltas,
        "band_power_median_deltas": band_deltas,
        "finding_changes": finding_changes,
        "interpretation_boundary": (
            "Deltas are descriptive measurements. A positive or negative value does not "
            "assign merit, preference, readiness, or delivery suitability."
        ),
    }


def _utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def write_revision_diff(
    payload: dict[str, Any],
    out_dir: str | Path,
    *,
    theme_name: str | None = None,
    presentation_mode: str | None = None,
) -> dict[str, Path]:
    """Publish JSON, Markdown, and HTML revision-diff artifacts safely."""

    out = Path(out_dir)
    selected_theme = validate_theme_name(theme_name or default_theme_name())
    selected_presentation = validate_presentation_mode(presentation_mode)
    with output_transaction(out) as transaction, staged_output_directory(out) as staging:
        json_path = staging / "revision_diff.json"
        json_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _write_diff_markdown(payload, staging / "revision_diff.md")
        _write_diff_html(
            payload,
            staging / "revision_diff.html",
            selected_theme,
            selected_presentation,
        )
        write_output_manifest(
            staging,
            kind="same-track-revision-diff",
            generated_files=[*REVISION_DIFF_FILENAMES, OUTPUT_MARKER_FILENAME],
        )
        publish_staged_output(
            staging,
            out,
            owned_filenames=set(ALL_GENERATED_FILENAMES),
            transaction=transaction,
        )
    return {
        "json": out / "revision_diff.json",
        "markdown": out / "revision_diff.md",
        "html": out / "revision_diff.html",
    }


def load_report_inputs(path: str | Path) -> ReportInputs:
    """Load a completed report directory or its summary.json path."""

    supplied = Path(path).expanduser()
    if supplied.is_dir():
        directory = supplied
    elif supplied.is_file() and supplied.name == "summary.json":
        directory = supplied.parent
    else:
        raise RevisionDiffError(
            f"Expected a report directory or summary.json, received '{supplied.name}'."
        )
    summary_path = directory / "summary.json"
    findings_path = directory / "findings.json"
    if not summary_path.is_file() or not findings_path.is_file():
        raise RevisionDiffError(
            f"Report '{directory.name}' must contain summary.json and findings.json."
        )
    return ReportInputs(
        directory=directory,
        summary=_read_json_object(summary_path),
        findings=_read_json_object(findings_path),
    )


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RevisionDiffError(f"Could not read '{path.name}' from report '{path.parent.name}'.") from exc
    if not isinstance(value, dict):
        raise RevisionDiffError(f"Expected a JSON object in '{path.name}'.")
    return value


def _same_track_assessment(
    first: dict[str, Any],
    second: dict[str, Any],
    *,
    confirm_same_track: bool,
) -> dict[str, Any]:
    first_hash = _track_hash(first)
    second_hash = _track_hash(second)
    if first_hash is not None and second_hash is not None:
        if first_hash != second_hash:
            raise RevisionDiffError(
                "The reports carry different track-identity digests. AudioAtlas refuses "
                "to treat them as revisions of the same track."
            )
        return {
            "status": "matched",
            "basis": "matching-user-supplied-track-id-digest",
            "explicit_confirmation_used": False,
        }
    if not confirm_same_track:
        raise RevisionDiffError(
            "Same-track identity is not established. Regenerate both reports with the same "
            "--track-id token, or pass --confirm-same-track only after checking that both "
            "reports are revisions of the same track."
        )
    return {
        "status": "asserted",
        "basis": "explicit-user-confirmation",
        "explicit_confirmation_used": True,
    }


def _track_hash(summary: dict[str, Any]) -> str | None:
    identity = summary.get("source_identity")
    if not isinstance(identity, dict):
        return None
    value = identity.get("track_id_sha256")
    if isinstance(value, str) and len(value) == 64:
        return value
    return None


def _comparability_assessment(
    first: dict[str, Any], second: dict[str, Any]
) -> dict[str, Any]:
    exact_a = provenance_signature(first, "exact_environment_sha256")
    exact_b = provenance_signature(second, "exact_environment_sha256")
    compatible_a = provenance_signature(first, "compatible_analysis_sha256")
    compatible_b = provenance_signature(second, "compatible_analysis_sha256")
    reasons: list[str] = []

    if exact_a is not None and exact_a == exact_b:
        status = "exact"
        reasons.append("Analysis code, configuration, dependencies, and recorded environment match.")
    elif compatible_a is not None and compatible_a == compatible_b:
        status = "compatible"
        reasons.append(
            "Analysis code, configuration, decoder, and dependency versions match; the "
            "recorded execution environment differs."
        )
    elif compatible_a is None or compatible_b is None:
        status = "unknown"
        reasons.append("One or both reports predate the provenance block or lack valid signatures.")
    else:
        status = "incomparable"
        reasons.extend(_provenance_difference_reasons(first, second))
        if not reasons:
            reasons.append("The analysis signatures differ.")

    scope_caveats = _scope_caveats(first, second)
    return {
        "status": status,
        "override_used": False,
        "reasons": reasons,
        "scope_caveats": scope_caveats,
        "finding_rules": _finding_rule_assessment(first, second),
    }


def _finding_rule_assessment(
    first: dict[str, Any], second: dict[str, Any]
) -> dict[str, Any]:
    provenance_a = (
        first.get("analysis_provenance")
        if isinstance(first.get("analysis_provenance"), dict)
        else {}
    )
    provenance_b = (
        second.get("analysis_provenance")
        if isinstance(second.get("analysis_provenance"), dict)
        else {}
    )
    code_a = provenance_a.get("finding_rule_code_sha256")
    code_b = provenance_b.get("finding_rule_code_sha256")
    version_a = provenance_a.get("finding_ruleset_version")
    version_b = provenance_b.get("finding_ruleset_version")
    if not all(isinstance(value, str) and value for value in (code_a, code_b)):
        return {
            "status": "unknown",
            "reasons": [
                "One or both reports lack a finding-rule implementation fingerprint."
            ],
            "attribution": "source-and-or-rule-implementation",
        }
    if code_a == code_b and version_a == version_b:
        return {
            "status": "matching",
            "reasons": [
                "Finding-rule implementation and ruleset version match between reports."
            ],
            "attribution": "source-revision-under-matching-rules",
        }
    reasons: list[str] = []
    if code_a != code_b:
        reasons.append("Finding-rule implementation differs between reports.")
    if version_a != version_b:
        reasons.append("Finding ruleset version differs between reports.")
    return {
        "status": "differing",
        "reasons": reasons,
        "attribution": "source-and-or-rule-implementation",
    }


def _provenance_difference_reasons(
    first: dict[str, Any], second: dict[str, Any]
) -> list[str]:
    a = first.get("analysis_provenance")
    b = second.get("analysis_provenance")
    if not isinstance(a, dict) or not isinstance(b, dict):
        return ["One or both provenance blocks are missing."]
    labels = (
        ("analysis_config_sha256", "Analysis configuration differs."),
        ("measurement_code_sha256", "Measurement implementation differs."),
        ("dependencies", "Scientific dependency versions differ."),
        ("decoder", "Decoder backend versions differ."),
        ("measurement_methods", "Recorded measurement method details differ."),
    )
    return [message for key, message in labels if a.get(key) != b.get(key)]


def _scope_caveats(first: dict[str, Any], second: dict[str, Any]) -> list[str]:
    caveats: list[str] = []
    meta_a = first.get("metadata") if isinstance(first.get("metadata"), dict) else {}
    meta_b = second.get("metadata") if isinstance(second.get("metadata"), dict) else {}
    for key, label in (("samplerate", "sample rate"), ("channels", "channel count")):
        if meta_a.get(key) != meta_b.get(key):
            caveats.append(f"The {label} differs between reports.")
    start_a = _number(meta_a.get("source_start_seconds"))
    start_b = _number(meta_b.get("source_start_seconds"))
    if start_a is not None and start_b is not None and abs(start_a - start_b) > 1e-6:
        caveats.append("The analyzed source start time differs.")
    duration_a = _metric_value(first, ("levels", "duration_seconds"))
    duration_b = _metric_value(second, ("levels", "duration_seconds"))
    if duration_a is not None and duration_b is not None:
        tolerance = max(0.05, 0.001 * max(abs(duration_a), abs(duration_b), 1.0))
        if abs(duration_a - duration_b) > tolerance:
            caveats.append("The analyzed duration differs enough to affect whole-file metrics.")
    return caveats


def _source_context(first: ReportInputs, second: ReportInputs) -> dict[str, Any]:
    return {
        "a": _report_context(first.summary, first.findings),
        "b": _report_context(second.summary, second.findings),
    }


def _report_context(
    summary: dict[str, Any], findings: dict[str, Any]
) -> dict[str, Any]:
    metadata = summary.get("metadata") if isinstance(summary.get("metadata"), dict) else {}
    provenance = (
        summary.get("analysis_provenance")
        if isinstance(summary.get("analysis_provenance"), dict)
        else {}
    )
    ruleset_version = provenance.get("finding_ruleset_version")
    if not isinstance(ruleset_version, str) or not ruleset_version:
        candidate = findings.get("ruleset_version")
        ruleset_version = candidate if isinstance(candidate, str) and candidate else None
    return {
        "filename": _source_filename(summary),
        "duration_seconds": _metric_value(summary, ("levels", "duration_seconds")),
        "samplerate": metadata.get("samplerate"),
        "channels": metadata.get("channels"),
        "summary_schema_version": summary.get("schema_version"),
        "audioatlas_version": provenance.get("audioatlas_version"),
        "finding_ruleset_version": ruleset_version,
        "summary_sha256": canonical_json_sha256(summary),
        "findings_sha256": canonical_json_sha256(findings),
        "report_snapshot_sha256": canonical_json_sha256(
            {"summary": summary, "findings": findings}
        ),
    }


def _source_filename(summary: dict[str, Any]) -> str | None:
    metadata = summary.get("metadata")
    if not isinstance(metadata, dict):
        return None
    value = metadata.get("filename")
    return value if isinstance(value, str) and value else None


def _metric_deltas(first: dict[str, Any], second: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in METRICS:
        value_a = _metric_value(first, spec.path)
        value_b = _metric_value(second, spec.path)
        if value_a is None and value_b is None:
            continue
        delta = value_b - value_a if value_a is not None and value_b is not None else None
        if spec.decimals == 0:
            value_a = int(value_a) if value_a is not None else None
            value_b = int(value_b) if value_b is not None else None
            delta = int(delta) if delta is not None else None
        rows.append(
            {
                "metric": ".".join(spec.path),
                "label": spec.label,
                "unit": spec.unit,
                "a": value_a,
                "b": value_b,
                "delta_b_minus_a": delta,
                "display_decimals": spec.decimals,
            }
        )
    return rows


def _band_power_deltas(first: dict[str, Any], second: dict[str, Any]) -> list[dict[str, Any]]:
    bands_a = _band_blocks(first)
    bands_b = _band_blocks(second)
    names = sorted(set(bands_a) | set(bands_b))
    rows: list[dict[str, Any]] = []
    for name in names:
        value_a = _band_median(bands_a.get(name))
        value_b = _band_median(bands_b.get(name))
        if value_a is None and value_b is None:
            continue
        rows.append(
            {
                "band": name,
                "unit": "dB relative",
                "a_median_db": value_a,
                "b_median_db": value_b,
                "delta_b_minus_a_db": (
                    value_b - value_a
                    if value_a is not None and value_b is not None
                    else None
                ),
                "measurement": "relative_mean_power_per_fft_bin",
            }
        )
    return rows


def _band_blocks(summary: dict[str, Any]) -> dict[str, Any]:
    block = summary.get("band_power_timeline")
    if not isinstance(block, dict):
        block = summary.get("band_energy_timeline")
    if not isinstance(block, dict):
        return {}
    bands = block.get("bands")
    return bands if isinstance(bands, dict) else {}


def _band_median(value: Any) -> float | None:
    if not isinstance(value, dict):
        return None
    return _number(value.get("median_db"))


def _finding_changes(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    findings_a = {_finding_rule_id(item): item for item in _all_findings(first)}
    findings_b = {_finding_rule_id(item): item for item in _all_findings(second)}
    findings_a.pop(None, None)
    findings_b.pop(None, None)
    appeared: list[dict[str, Any]] = []
    disappeared: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []
    unchanged_count = 0
    for rule_id in sorted(set(findings_a) | set(findings_b)):
        item_a = findings_a.get(rule_id)
        item_b = findings_b.get(rule_id)
        if item_a is None and item_b is not None:
            appeared.append(_finding_snapshot(item_b))
        elif item_b is None and item_a is not None:
            disappeared.append(_finding_snapshot(item_a))
        elif item_a is not None and item_b is not None:
            snap_a = _finding_snapshot(item_a)
            snap_b = _finding_snapshot(item_b)
            changed_fields = [
                key for key in snap_a if snap_a.get(key) != snap_b.get(key)
            ]
            if not changed_fields:
                unchanged_count += 1
            else:
                changed.append(
                    {
                        "rule_id": rule_id,
                        "changed_fields": changed_fields,
                        "a": snap_a,
                        "b": snap_b,
                    }
                )
    return {
        "appeared": appeared,
        "disappeared": disappeared,
        "changed": changed,
        "unchanged_count": unchanged_count,
    }


def _all_findings(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("all_findings", "findings_shown", "findings"):
        value = payload.get(key)
        if isinstance(value, list):
            items = [item for item in value if isinstance(item, dict)]
            if items or key == "findings":
                return items
    return []


def _finding_rule_id(item: dict[str, Any]) -> str | None:
    value = item.get("rule_id")
    return value if isinstance(value, str) and value else None


def _finding_snapshot(item: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "rule_id",
        "rule_version",
        "severity",
        "category",
        "title",
        "confidence",
        "measured_value",
        "threshold",
        "unit",
        "evidence",
        "evidence_items",
        "why_it_matters",
        "does_not_mean",
        "suggested_checks",
        "associated_graphs",
        "time_ranges",
    )
    return {key: item.get(key) for key in keys}


def _metric_value(summary: dict[str, Any], path: tuple[str, ...]) -> float | None:
    value: Any = summary
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return _number(value)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _clean_label(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split()).strip()
    if not cleaned:
        raise RevisionDiffError("Revision labels cannot be blank.")
    if len(cleaned) > 160:
        raise RevisionDiffError("Revision labels must be 160 characters or fewer.")
    return cleaned


def _write_diff_markdown(payload: dict[str, Any], path: Path) -> None:
    labels = payload["labels"]
    comparison = payload["comparability"]
    lines = [
        "# AudioAtlas same-track revision delta",
        "",
        f"- A: **{_markdown_escape(labels['a'])}**",
        f"- B: **{_markdown_escape(labels['b'])}**",
        f"- Comparability: **{comparison['status']}**",
        f"- Same-track basis: {payload['same_track']['basis']}",
        "",
        "> Deltas are B minus A. They are descriptive measurements and do not assign merit, preference, readiness, or delivery suitability.",
        "",
    ]
    if comparison.get("override_used"):
        lines.extend(
            [
                "> **Comparability override used.** The measurements may reflect implementation, configuration, or dependency differences in addition to source changes.",
                "",
            ]
        )
    for reason in comparison.get("reasons", []):
        lines.append(f"- Comparability note: {reason}")
    for caveat in comparison.get("scope_caveats", []):
        lines.append(f"- Scope caveat: {caveat}")
    rule_assessment = comparison.get("finding_rules", {})
    for reason in rule_assessment.get("reasons", []):
        lines.append(f"- Finding-rule note: {reason}")
    lines.extend(["", "## Scalar measurement deltas", "", _markdown_metric_table(payload), ""])
    lines.extend(["## Relative mean band-power median deltas", "", _markdown_band_table(payload), ""])
    lines.extend(_markdown_findings(payload["finding_changes"]))
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _markdown_metric_table(payload: dict[str, Any]) -> str:
    labels = payload["labels"]
    lines = [
        f"| Metric | {_markdown_escape(labels['a'])} | {_markdown_escape(labels['b'])} | Δ B−A | Unit |",
        "|---|---:|---:|---:|---|",
    ]
    for row in payload["metric_deltas"]:
        decimals = int(row.get("display_decimals", 3))
        lines.append(
            f"| {_markdown_escape(row['label'])} | {_fmt(row['a'], decimals)} | {_fmt(row['b'], decimals)} | "
            f"{_fmt_signed(row['delta_b_minus_a'], decimals)} | {_markdown_escape(row['unit'])} |"
        )
    if len(lines) == 2:
        lines.append("| No shared scalar measurements | — | — | — | — |")
    return "\n".join(lines)


def _markdown_band_table(payload: dict[str, Any]) -> str:
    labels = payload["labels"]
    lines = [
        f"| Band | {_markdown_escape(labels['a'])} | {_markdown_escape(labels['b'])} | Δ B−A |",
        "|---|---:|---:|---:|",
    ]
    for row in payload["band_power_median_deltas"]:
        lines.append(
            f"| {_markdown_escape(row['band'])} | {_fmt(row['a_median_db'], 2)} | "
            f"{_fmt(row['b_median_db'], 2)} | {_fmt_signed(row['delta_b_minus_a_db'], 2)} |"
        )
    if len(lines) == 2:
        lines.append("| No shared band-power medians | — | — | — |")
    return "\n".join(lines)


def _markdown_findings(changes: dict[str, Any]) -> list[str]:
    lines = ["## Review-prompt changes", ""]
    lines.append(f"- Unchanged rules: {changes.get('unchanged_count', 0)}")
    for label, key in (("Appeared in B", "appeared"), ("Disappeared in B", "disappeared")):
        items = changes.get(key, [])
        lines.extend(["", f"### {label}", ""])
        if not items:
            lines.append("- None")
        else:
            for item in items:
                lines.append(
                    f"- `{_markdown_code(item.get('rule_id'))}` — "
                    f"{_markdown_escape(item.get('title'))}"
                )
    items = changes.get("changed", [])
    lines.extend(["", "### Changed rule payloads", ""])
    if not items:
        lines.append("- None")
    else:
        for item in items:
            fields = item.get("changed_fields", [])
            suffix = (
                " — changed: " + ", ".join(_markdown_escape(field) for field in fields)
                if isinstance(fields, list) and fields
                else ""
            )
            lines.append(f"- `{_markdown_code(item.get('rule_id'))}`{suffix}")
    lines.append("")
    return lines


def _write_diff_html(
    payload: dict[str, Any],
    path: Path,
    theme_name: str,
    presentation_mode: str,
) -> None:
    labels = payload["labels"]
    comparison = payload["comparability"]
    rows = []
    for row in payload["metric_deltas"]:
        decimals = int(row.get("display_decimals", 3))
        rows.append(
            "<tr>"
            f"<th scope=\"row\">{escape(str(row['label']))}</th>"
            f"<td>{escape(_fmt(row['a'], decimals))}</td>"
            f"<td>{escape(_fmt(row['b'], decimals))}</td>"
            f"<td>{escape(_fmt_signed(row['delta_b_minus_a'], decimals))}</td>"
            f"<td>{escape(str(row['unit']))}</td>"
            "</tr>"
        )
    band_rows = []
    for row in payload["band_power_median_deltas"]:
        band_rows.append(
            "<tr>"
            f"<th scope=\"row\">{escape(str(row['band']))}</th>"
            f"<td>{escape(_fmt(row['a_median_db'], 2))}</td>"
            f"<td>{escape(_fmt(row['b_median_db'], 2))}</td>"
            f"<td>{escape(_fmt_signed(row['delta_b_minus_a_db'], 2))}</td>"
            "</tr>"
        )
    finding_rule_assessment = comparison.get("finding_rules", {})
    notes = "".join(
        f"<li>{escape(str(item))}</li>"
        for item in [
            *comparison.get("reasons", []),
            *comparison.get("scope_caveats", []),
            *finding_rule_assessment.get("reasons", []),
        ]
    )
    override = (
        '<div class="callout warning"><strong>Comparability override used.</strong> '
        "The observed deltas may include implementation, configuration, or dependency effects.</div>"
        if comparison.get("override_used")
        else ""
    )
    changes = payload["finding_changes"]
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AudioAtlas revision delta</title>
<style>
{theme_css_variables(theme_name)}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--text); font-family: Inter, ui-sans-serif, system-ui, -apple-system, sans-serif; line-height: 1.5; }}
main {{ max-width: 1100px; margin: 0 auto; padding: 36px 22px 72px; }}
header, section {{ background: var(--surface); border: 1px solid var(--border); border-radius: 18px; padding: 24px; margin-bottom: 18px; box-shadow: var(--shadow-card); }}
h1, h2 {{ margin-top: 0; }}
.pair {{ display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 12px; }}
.card {{ background: var(--surface-muted); border: 1px solid var(--border-soft); border-radius: 12px; padding: 14px; }}
.badge {{ display: inline-block; background: var(--chip-bg); border: 1px solid var(--border); border-radius: 999px; padding: 5px 10px; margin-right: 6px; }}
.callout {{ background: var(--callout-bg); border-left: 4px solid var(--callout-border); padding: 14px 16px; border-radius: 10px; margin: 16px 0; }}
.warning {{ background: var(--warning-bg); color: var(--warning-text); border-color: var(--warning-border); }}
table {{ width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }}
th, td {{ padding: 10px 9px; border-bottom: 1px solid var(--border-soft); text-align: right; vertical-align: top; }}
th:first-child, td:first-child {{ text-align: left; }}
.small {{ color: var(--text-muted); }}
.columns {{ display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 12px; }}
ul {{ padding-left: 20px; }}
.top-nav {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 0 0 18px; padding: 12px 4px; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); background: var(--bg); }}
.top-nav a {{ color: var(--accent); font-weight: 650; text-decoration: none; }}
.top-nav a:hover {{ text-decoration: underline; }}
.top-nav span {{ color: var(--text-soft); }}
@media (max-width: 760px) {{ .pair, .columns {{ grid-template-columns: 1fr; }} table {{ font-size: .88rem; }} }}
{presentation_css()}
</style>
</head>
<body data-presentation="{escape(presentation_mode)}">
{skip_link_html()}
<main id="main-content" tabindex="-1">
<header>
<h1>Same-track revision delta</h1>
{presentation_controls_html(presentation_mode)}
<div class="pair"><div class="card"><strong>A</strong><br>{escape(str(labels['a']))}</div><div class="card"><strong>B</strong><br>{escape(str(labels['b']))}</div></div>
<p><span class="badge">Comparability: {escape(str(comparison['status']))}</span><span class="badge">Finding rules: {escape(str(finding_rule_assessment.get('status', 'unknown')))}</span><span class="badge">Identity: {escape(str(payload['same_track']['basis']))}</span></p>
<div class="callout"><strong>Interpretation boundary.</strong> Deltas are B minus A. They are descriptive measurements and do not assign merit, preference, readiness, or delivery suitability.</div>
{override}
<ul>{notes or '<li>No additional comparability caveats.</li>'}</ul>
</header>
<nav class="top-nav" aria-label="Revision delta sections"><a href="#scalar-deltas">Scalar deltas</a><span aria-hidden="true">·</span><a href="#band-deltas">Band deltas</a><span aria-hidden="true">·</span><a href="#prompt-changes">Prompt changes</a></nav>
<section id="scalar-deltas"><h2>Scalar measurement deltas</h2>
<div class="table-scroll" role="region" aria-label="Scalar measurement deltas" tabindex="0"><table><thead><tr><th scope="col">Metric</th><th scope="col">{escape(str(labels['a']))}</th><th scope="col">{escape(str(labels['b']))}</th><th scope="col">Δ B−A</th><th scope="col">Unit</th></tr></thead><tbody>{''.join(rows) or '<tr><td colspan="5">No shared scalar measurements.</td></tr>'}</tbody></table></div></section>
<section id="band-deltas"><h2>Relative mean band-power median deltas</h2><p class="small">Mean spectral power per included FFT bin, normalized within each file. These are not integrated band-energy values.</p>
<div class="table-scroll" role="region" aria-label="Relative band-power median deltas" tabindex="0"><table><thead><tr><th scope="col">Band</th><th scope="col">{escape(str(labels['a']))}</th><th scope="col">{escape(str(labels['b']))}</th><th scope="col">Δ B−A</th></tr></thead><tbody>{''.join(band_rows) or '<tr><td colspan="4">No shared band-power medians.</td></tr>'}</tbody></table></div></section>
<section id="prompt-changes"><h2>Review-prompt changes</h2><p class="small">Attribution: {escape(str(changes.get('attribution', 'unknown')))}.</p><div class="columns">
{_finding_html_column('Appeared in B', changes.get('appeared', []))}
{_finding_html_column('Disappeared in B', changes.get('disappeared', []))}
{_finding_html_column('Changed payload', changes.get('changed', []))}
</div><p class="small">Unchanged rules: {int(changes.get('unchanged_count', 0))}</p></section>
</main>
{presentation_script(presentation_mode)}
</body></html>
"""
    path.write_text(html, encoding="utf-8")


def _finding_html_column(title: str, items: list[Any]) -> str:
    rendered: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if "a" in item and "b" in item:
            rule_id = item.get("rule_id", "unknown")
            label = (
                item.get("b", {}).get("title", "Changed rule")
                if isinstance(item.get("b"), dict)
                else "Changed rule"
            )
            fields = item.get("changed_fields", [])
            if isinstance(fields, list) and fields:
                label = f"{label} (changed: {', '.join(str(field) for field in fields)})"
        else:
            rule_id = item.get("rule_id", "unknown")
            label = item.get("title", "Review prompt")
        rendered.append(f"<li><code>{escape(str(rule_id))}</code><br>{escape(str(label))}</li>")
    body = "".join(rendered) or "<li>None</li>"
    return f'<div class="card"><h3>{escape(title)}</h3><ul>{body}</ul></div>'


def _markdown_escape(value: Any) -> str:
    """Escape user/report labels used in Markdown prose and table cells."""

    return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("*", "\\*")


def _markdown_code(value: Any) -> str:
    return str(value).replace("`", "'")


def _fmt(value: Any, decimals: int) -> str:
    if value is None:
        return "—"
    if decimals == 0:
        return str(int(round(float(value))))
    return f"{float(value):.{decimals}f}"


def _fmt_signed(value: Any, decimals: int) -> str:
    if value is None:
        return "—"
    if decimals == 0:
        return f"{int(round(float(value))):+d}"
    return f"{float(value):+.{decimals}f}"
