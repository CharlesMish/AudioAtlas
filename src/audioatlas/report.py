"""Report helpers for AudioAtlas.

Markdown and JSON report helpers. Static HTML lives in ``html_report.py``.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from audioatlas import __version__
from audioatlas.alt_text import plot_alt_text
from audioatlas.graphs.registry import RELATIVE_DB_NOTE, graph_by_filename
from audioatlas.markdown import markdown_text
from audioatlas.release import RELEASE_LABEL
from audioatlas.utils import mmss

# Human-friendly labels and units for the level-metrics block of report.md.
# Keep this list in sync with ``ScalarLevelsResult`` whenever a global scalar
# field is added. Per-channel arrays live in ``PER_CHANNEL_METRIC_DISPLAY``
# below and are rendered in their own section.
LEVEL_METRIC_DISPLAY: list[tuple[str, str, str]] = [
    ("sample_peak_dbfs",        "Sample peak",         "dBFS"),
    ("true_peak_dbtp",          "True-peak (approx.)", "dBTP"),
    ("rms_dbfs",                "RMS",                 "dBFS"),
    ("crest_factor_db",         "Crest factor",        "dB"),
    ("integrated_lufs",         "Integrated loudness", "LUFS"),
    ("plr_db",                  "PLR (peak - LUFS)",   "dB"),
    ("clipped_samples",         "Clipped samples",     ""),
    ("near_clipping_samples",   "Near-clipping",       ""),
]

# Per-channel arrays. Order here is the row order in the report's
# per-channel section.
CREST_TIMELINE_DISPLAY: list[tuple[str, str, str]] = [
    ("frame_length", "Frame length", "samples"),
    ("hop_length", "Hop length", "samples"),
    ("frames", "Frames", ""),
    ("crest_factor_db_min", "Crest factor min", "dB"),
    ("crest_factor_db_median", "Crest factor median", "dB"),
    ("crest_factor_db_max", "Crest factor max", "dB"),
]

SHORT_TERM_LUFS_DISPLAY: list[tuple[str, str, str]] = [
    ("window_seconds", "Window", "s"),
    ("hop_seconds", "Hop", "s"),
    ("frames", "Frames", ""),
    ("lufs_min", "Short-term LUFS min", "LUFS"),
    ("lufs_median", "Short-term LUFS median", "LUFS"),
    ("lufs_max", "Short-term LUFS max", "LUFS"),
]

PER_CHANNEL_METRIC_DISPLAY: list[tuple[str, str, str]] = [
    ("peak_dbfs_per_channel",      "Sample peak",          "dBFS"),
    ("true_peak_dbtp_per_channel", "True-peak (approx.)",  "dBTP"),
    ("rms_dbfs_per_channel",       "RMS",                  "dBFS"),
    ("dc_offset_per_channel",      "DC offset",            ""),
]

SEVERITY_DISPLAY: dict[str, str] = {
    "issue": "check before delivery",
    "warning": "worth a listen",
    "info": "for reference",
}

TIME_RANGE_KEYS: set[str] = {
    "correlation_below_0_time_ranges",
    "correlation_below_0_3_time_ranges",
    "side_to_mid_ratio_above_minus_6_time_ranges",
    "centroid_elevated_time_ranges",
    "centroid_reduced_time_ranges",
    "centroid_large_shift_time_ranges",
    "high_onset_density_time_ranges",
}


def write_summary_json(summary: dict[str, Any], out_dir: str | Path) -> Path:
    """Write summary.json."""

    out = Path(out_dir) / "summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return out


def write_findings_json(findings: dict[str, Any], out_dir: str | Path) -> Path:
    """Write findings.json."""

    out = Path(out_dir) / "findings.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(findings, indent=2, sort_keys=True), encoding="utf-8")
    return out


def _fmt_value(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _evidence_item_text(value: Any) -> str:
    """Return a human-facing line from legacy or structured evidence."""

    if isinstance(value, dict):
        label = value.get("label")
        if isinstance(label, str) and label:
            return label
    return str(value)


def _positive_int(block: dict[str, Any], key: str, *, default: int) -> int:
    value = block.get(key)
    if isinstance(value, bool):
        return default
    if isinstance(value, int) and value > 0:
        return value
    return default


def _append_summary_value(lines: list[str], key: str, value: Any) -> None:
    if key in TIME_RANGE_KEYS and isinstance(value, list):
        count_name = key.removesuffix("_time_ranges") + "_ranges"
        lines.append(f"- {count_name}: {len(value)}")
        return
    lines.append(f"- {key}: {_fmt_value(value)}")


def _normalized_time_ranges(time_ranges: list[Any]) -> list[dict[str, float]]:
    out: list[dict[str, float]] = []
    for item in time_ranges:
        if not isinstance(item, dict):
            continue
        start = item.get("start")
        end = item.get("end")
        duration = item.get("duration")
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            continue
        if not isinstance(duration, (int, float)):
            duration = float(end) - float(start)
        out.append(
            {
                "start": float(start),
                "end": float(end),
                "duration": float(duration),
            }
        )
    return out


def _format_range_short(item: dict[str, float]) -> str:
    return f"{item['start']:.3f}s-{item['end']:.3f}s"


def _format_time_ranges_for_report(
    time_ranges: list[Any],
    *,
    max_display: int,
) -> list[str]:
    ranges = _normalized_time_ranges(time_ranges)
    if not ranges:
        return []

    total_duration = sum(item["duration"] for item in ranges)
    longest = max(ranges, key=lambda item: item["duration"])
    examples = _select_time_range_examples(ranges, max_display=max_display)
    lines = [
        (
            f"- Time ranges: {len(ranges)} regions, total {total_duration:.3f}s, "
            f"longest {longest['duration']:.3f}s."
        ),
        f"- Showing {len(examples)} example range(s):",
    ]
    for item in examples:
        lines.append(f"  - {_format_range_short(item)}")
    if len(examples) < len(ranges):
        lines.append("  - see findings.json for full ranges")
    return lines


def _select_time_range_examples(
    ranges: list[dict[str, float]],
    *,
    max_display: int,
) -> list[dict[str, float]]:
    """Pick compact examples: longest ranges first, plus earliest context."""

    capped = max(0, min(max_display, 5))
    if capped == 0:
        return []
    if len(ranges) <= capped:
        return ranges

    longest_count = min(3, capped)
    longest = sorted(ranges, key=lambda item: (-item["duration"], item["start"]))[
        :longest_count
    ]
    remaining_slots = capped - len(longest)
    selected = list(longest)
    for item in sorted(ranges, key=lambda item: item["start"]):
        if len(selected) >= capped:
            break
        if item in selected:
            continue
        selected.append(item)
        remaining_slots -= 1
        if remaining_slots <= 0:
            break
    return sorted(selected, key=lambda item: item["start"])


def _delivery_context_lines(levels: dict[str, Any]) -> list[str]:
    integrated_lufs = levels.get("integrated_lufs")
    if not isinstance(integrated_lufs, (int, float)) or isinstance(integrated_lufs, bool):
        return []
    if integrated_lufs <= -10.0:
        return []
    return [
        "## Delivery / headroom context\n",
        (
            f"- Integrated loudness: {_fmt_value(integrated_lufs)} LUFS. "
            "A playback system using a lower loudness reference may apply negative gain; "
            "the exact adjustment depends on its measurement, mode, and policy."
        ),
        "",
    ]


def _source_range_label(metadata: dict[str, Any]) -> str | None:
    start = metadata.get("source_start_seconds")
    end = metadata.get("source_end_seconds")
    source_duration = metadata.get("source_duration_seconds")
    if not all(isinstance(value, (int, float)) for value in (start, end, source_duration)):
        return None
    start_f = float(start)
    end_f = float(end)
    duration_f = float(source_duration)
    if duration_f <= 0:
        return None
    if abs(start_f) < 1e-9 and abs(end_f - duration_f) < 1e-6:
        return None
    return f"{start_f:.3f}s-{end_f:.3f}s of {duration_f:.3f}s"


def report_timestamp() -> str:
    """Return a UTC timestamp for generated reports."""

    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def git_revision_label(repo_root: str | Path | None = None) -> str | None:
    """Return the AudioAtlas source revision, including a dirty-worktree marker.

    The repository is resolved from the installed module rather than the caller's
    current working directory. This prevents a report generated from an installed
    wheel inside an unrelated Git project from claiming that project's revision.
    """

    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[2]
    if not (root / ".git").exists():
        return None
    try:
        revision = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=normal"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    if not revision:
        return None
    return f"{revision}+dirty" if status else revision


def git_short_hash() -> str | None:
    """Deprecated compatibility wrapper for :func:`git_revision_label`."""

    return git_revision_label()


def report_build_metadata() -> dict[str, str]:
    """Build human-facing report metadata."""

    metadata = {
        "generated_at": report_timestamp(),
        "audioatlas_version": __version__,
    }
    git_hash = git_revision_label()
    if git_hash:
        metadata["git_hash"] = git_hash
    return metadata


def write_report_md(
    summary: dict[str, Any],
    plot_files: list[str],
    out_dir: str | Path,
    findings: dict[str, Any] | None = None,
) -> Path:
    """Write a deliberately simple Markdown report.

    The report's job is to lay out measured facts and the generated plots.
    It must not produce verdicts ("your mix is muddy", "this is well mastered").
    See docs/ALPHA_LIMITATIONS.md for the rationale.
    """

    metadata = summary.get("metadata", {})
    analysis_config = (
        summary.get("analysis_config") if isinstance(summary.get("analysis_config"), dict) else {}
    )
    report_max_time_ranges = _positive_int(
        analysis_config, "report_max_time_ranges", default=8
    )
    levels = summary.get("levels", {})
    rms = summary.get("rms_envelope", {})
    crest_timeline = summary.get("crest_factor_timeline", {})
    spectrum = summary.get("average_spectrum", {})
    spectral_shape = summary.get("spectral_shape", {})
    band_power_timeline = summary.get("band_power_timeline")
    if not isinstance(band_power_timeline, dict):
        band_power_timeline = summary.get("band_energy_timeline", {})
    onset_density = summary.get("onset_density", {})
    chroma_cqt = summary.get("chroma_cqt", {})
    short_term_lufs = summary.get("short_term_lufs", {})
    stereo = summary.get("stereo_correlation", {})
    mid_side = summary.get("mid_side_energy", {})

    lines: list[str] = []
    lines.append(f"# AudioAtlas Report: {markdown_text(metadata.get('filename', 'unknown'))}\n")
    build_metadata = report_build_metadata()

    duration = levels.get("duration_seconds")
    if isinstance(duration, (int, float)):
        duration_label = f"{duration:.2f}s ({mmss(float(duration))})"
    else:
        duration_label = "unknown"

    lines.append("## File\n")
    lines.append(f"- Duration: {duration_label}")
    source_range = _source_range_label(metadata)
    if source_range is not None:
        lines.append(f"- Source range: {source_range}")
    lines.append(f"- Sample rate: {metadata.get('samplerate', 'unknown')} Hz")
    lines.append(f"- Channels: {metadata.get('channels', 'unknown')}")
    lines.append(
        f"- Format: {metadata.get('format', 'unknown')} / {metadata.get('subtype', 'unknown')}\n"
    )
    lines.append("## Report metadata\n")
    lines.append(f"- Generated: {build_metadata['generated_at']}")
    lines.append(f"- AudioAtlas: {build_metadata['audioatlas_version']}")
    if "git_hash" in build_metadata:
        lines.append(f"- Git: {build_metadata['git_hash']}")
    lines.append(f"- Release label: {RELEASE_LABEL}")
    provenance = (
        summary.get("analysis_provenance")
        if isinstance(summary.get("analysis_provenance"), dict)
        else {}
    )
    config_hash = provenance.get("analysis_config_sha256")
    compatible_hash = provenance.get("compatible_analysis_sha256")
    if isinstance(config_hash, str):
        lines.append(f"- Analysis config SHA-256: `{config_hash}`")
    if isinstance(compatible_hash, str):
        lines.append(f"- Comparable-analysis SHA-256: `{compatible_hash}`")
    lines.append("")

    lines.append("## Level metrics\n")
    lines.append("| Metric | Value | Unit |")
    lines.append("|---|---|---|")
    for key, label, unit in LEVEL_METRIC_DISPLAY:
        lines.append(f"| {label} | {_fmt_value(levels.get(key))} | {unit} |")
    lines.append("")
    lines.extend(_delivery_context_lines(levels))

    # Per-channel breakdown. Only render if at least one of the registered
    # per-channel fields is a non-null list (so mono files with all-null
    # per-channel arrays still look clean).
    per_channel_arrays = {
        key: levels.get(key) for key, _label, _unit in PER_CHANNEL_METRIC_DISPLAY
    }
    n_channels: int = 0
    for value in per_channel_arrays.values():
        if isinstance(value, list):
            n_channels = max(n_channels, len(value))
    if n_channels > 0:
        lines.append("## Per-channel breakdown\n")
        header = "| Metric | " + " | ".join(f"ch {i}" for i in range(n_channels)) + " | Unit |"
        sep = "|---|" + "|".join(["---"] * n_channels) + "|---|"
        lines.append(header)
        lines.append(sep)
        for key, label, unit in PER_CHANNEL_METRIC_DISPLAY:
            arr = per_channel_arrays.get(key)
            if isinstance(arr, list):
                cells = [_fmt_value(v) for v in arr]
                # Pad short rows so columns line up visually.
                cells += ["—"] * (n_channels - len(cells))
            else:
                cells = ["—"] * n_channels
            lines.append(f"| {label} | " + " | ".join(cells) + f" | {unit} |")
        lines.append("")

    warnings = levels.get("warnings") or []
    if warnings:
        lines.append("## Warnings / caveats\n")
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.append("")

    lines.append("## Frame RMS envelope summary\n")
    for key, value in rms.items():
        lines.append(f"- {key}: {_fmt_value(value)}")
    lines.append("")

    if crest_timeline:
        lines.append("## Crest factor timeline summary\n")
        for key, label, unit in CREST_TIMELINE_DISPLAY:
            if key in crest_timeline:
                unit_suffix = f" {unit}" if unit else ""
                lines.append(f"- {label}: {_fmt_value(crest_timeline.get(key))}{unit_suffix}")
        crest_warnings = crest_timeline.get("warnings") or []
        for warning in crest_warnings:
            lines.append(f"- Warning: {warning}")
        lines.append("")

    lines.append("## Average spectrum summary\n")
    lines.append(f"{RELATIVE_DB_NOTE}\n")
    for key, value in spectrum.items():
        if key in {"band_energies", "band_mean_power"}:
            continue
        lines.append(f"- {key}: {_fmt_value(value)}")
    lines.append("")

    band_mean_power = spectrum.get("band_mean_power")
    if not isinstance(band_mean_power, dict):
        band_mean_power = spectrum.get("band_energies")
    if isinstance(band_mean_power, dict) and band_mean_power:
        lines.append("## Relative mean band power summary\n")
        lines.append(
            "Each value is mean spectral power per included FFT bin, normalized within "
            "this file. It is not integrated total energy for the differently sized bands.\n"
        )
        lines.append(f"{RELATIVE_DB_NOTE}\n")
        lines.append("| Band | Range | Mean relative power |")
        lines.append("|---|---|---|")
        for band, values in band_mean_power.items():
            if not isinstance(values, dict):
                continue
            low = _fmt_value(values.get("low_hz"))
            high = _fmt_value(values.get("high_hz"))
            mean_power = values.get("mean_power_db", values.get("energy_db"))
            lines.append(
                f"| {band} | {low}-{high} Hz | {_fmt_value(mean_power)} dB relative |"
            )
        lines.append("")

    if spectral_shape:
        lines.append("## Spectral shape summary\n")
        for key, value in spectral_shape.items():
            if key == "warnings":
                continue
            _append_summary_value(lines, key, value)
        spectral_shape_warnings = spectral_shape.get("warnings") or []
        for warning in spectral_shape_warnings:
            lines.append(f"- warning: {warning}")
        lines.append("")

    if band_power_timeline:
        lines.append("## Relative mean band power timeline summary\n")
        lines.append(
            "Each frame averages spectral power per included FFT bin. This is not "
            "integrated total energy for the differently sized bands.\n"
        )
        lines.append(f"{RELATIVE_DB_NOTE}\n")
        lines.append(f"- frames: {_fmt_value(band_power_timeline.get('frames'))}")
        lines.append(f"- valid_frames: {_fmt_value(band_power_timeline.get('valid_frames'))}")
        highest_band = band_power_timeline.get(
            "highest_mean_power_band_by_median",
            band_power_timeline.get("strongest_band_by_median"),
        )
        lines.append(f"- highest_mean_power_band_by_median: {_fmt_value(highest_band)}")
        bands = band_power_timeline.get("bands")
        if isinstance(bands, dict) and bands:
            lines.append("")
            lines.append("| Band | Median | Mean | Min | Max |")
            lines.append("|---|---|---|---|---|")
            for band, values in bands.items():
                if not isinstance(values, dict):
                    continue
                lines.append(
                    f"| {band} | {_fmt_value(values.get('median_db'))} | "
                    f"{_fmt_value(values.get('mean_db'))} | {_fmt_value(values.get('min_db'))} | "
                    f"{_fmt_value(values.get('max_db'))} |"
                )
        warnings = band_power_timeline.get("warnings") or []
        for warning in warnings:
            lines.append(f"- warning: {warning}")
        lines.append("")

    if onset_density:
        lines.append("## Onset / transient density summary\n")
        for key, value in onset_density.items():
            if key == "warnings":
                continue
            _append_summary_value(lines, key, value)
        onset_warnings = onset_density.get("warnings") or []
        for warning in onset_warnings:
            lines.append(f"- warning: {warning}")
        lines.append("")

    if chroma_cqt:
        lines.append("## Chroma CQT summary\n")
        lines.append(
            "Pitch-class energy within this track. This is not key detection "
            "and values are not calibrated across unrelated songs.\n"
        )
        for key, value in chroma_cqt.items():
            if key in {"warnings", "mean_chroma", "pitch_classes"}:
                continue
            _append_summary_value(lines, key, value)
        mean_chroma = chroma_cqt.get("mean_chroma")
        pitch_classes = chroma_cqt.get("pitch_classes")
        if isinstance(mean_chroma, list) and isinstance(pitch_classes, list) and mean_chroma:
            lines.append("")
            lines.append("| Pitch class | Mean energy |")
            lines.append("|---|---|")
            for pitch_class, energy in zip(pitch_classes, mean_chroma, strict=True):
                lines.append(f"| {pitch_class} | {_fmt_value(energy)} |")
        chroma_warnings = chroma_cqt.get("warnings") or []
        for warning in chroma_warnings:
            lines.append(f"- warning: {warning}")
        lines.append("")

    if short_term_lufs:
        lines.append("## Short-term LUFS summary\n")
        lines.append(
            "K-weighted loudness over 3 s windows. This is distinct from the RMS timeline "
            "and from integrated LUFS, which summarizes the whole track.\n"
        )
        for key, label, unit in SHORT_TERM_LUFS_DISPLAY:
            if key in short_term_lufs:
                unit_suffix = f" {unit}" if unit else ""
                lines.append(f"- {label}: {_fmt_value(short_term_lufs.get(key))}{unit_suffix}")
        lufs_warnings = short_term_lufs.get("warnings") or []
        for warning in lufs_warnings:
            lines.append(f"- Warning: {warning}")
        lines.append("")

    if stereo:
        lines.append("## Stereo correlation summary\n")
        for key, value in stereo.items():
            if key == "warnings":
                continue
            _append_summary_value(lines, key, value)
        stereo_warnings = stereo.get("warnings") or []
        for warning in stereo_warnings:
            lines.append(f"- warning: {warning}")
        lines.append("")

    if mid_side:
        lines.append("## Mid/side energy summary\n")
        for key, value in mid_side.items():
            if key == "warnings":
                continue
            _append_summary_value(lines, key, value)
        mid_side_warnings = mid_side.get("warnings") or []
        for warning in mid_side_warnings:
            lines.append(f"- warning: {warning}")
        lines.append("")

    if findings is not None:
        lines.append("## Findings\n")
        lines.append(
            "Findings are measurement-based observations derived from the analysis. "
            "They highlight values or regions worth checking by ear; they are not "
            "quality judgments."
        )
        lines.append(
            "Long lists of time ranges are summarized here; see findings.json for "
            "full machine-readable details."
        )
        lines.append(
            "Brief low-correlation events can be normal for panned effects; "
            "sustained or frequent low correlation is more relevant."
        )
        suppressed = findings.get("findings_suppressed_count") if isinstance(findings, dict) else 0
        if isinstance(suppressed, int) and suppressed > 0:
            lines.append(
                f"{suppressed} lower-priority finding(s) suppressed; see findings.json for details."
            )
        lines.append("")
        finding_items = findings.get("findings_shown") if isinstance(findings, dict) else None
        if not isinstance(finding_items, list) and isinstance(findings, dict):
            finding_items = findings.get("findings")
        if isinstance(finding_items, list) and finding_items:
            for item in finding_items:
                if not isinstance(item, dict):
                    continue
                lines.append(f"### {item.get('title', 'Finding')}\n")
                severity = str(item.get("severity", "unknown"))
                lines.append(f"- Prompt level: {SEVERITY_DISPLAY.get(severity, severity)}")
                lines.append(f"- Category: {item.get('category', 'unknown')}")
                rule_id = item.get("rule_id")
                rule_version = item.get("rule_version")
                if isinstance(rule_id, str) and rule_id:
                    version_suffix = f" v{rule_version}" if isinstance(rule_version, int) else ""
                    lines.append(f"- Rule: `{rule_id}`{version_suffix}")
                if item.get("measured_value") is not None:
                    lines.append(
                        f"- Measured value: {_fmt_value(item.get('measured_value'))} "
                        f"{item.get('unit', '')}".rstrip()
                    )
                if item.get("threshold") is not None:
                    lines.append(f"- Threshold: {_fmt_value(item.get('threshold'))}")
                evidence_items = item.get("evidence_items")
                if isinstance(evidence_items, list) and evidence_items:
                    lines.append("- Evidence:")
                    for evidence_item in evidence_items:
                        lines.append(f"  - {_evidence_item_text(evidence_item)}")
                else:
                    lines.append(f"- Evidence: {item.get('evidence', '')}")
                lines.append(f"- Why it matters: {item.get('why_it_matters', '')}")
                does_not_mean = item.get("does_not_mean")
                if isinstance(does_not_mean, str) and does_not_mean:
                    lines.append(f"- Does not mean: {does_not_mean}")
                suggested_checks = item.get("suggested_checks")
                if isinstance(suggested_checks, list) and suggested_checks:
                    lines.append("- Suggested listening checks:")
                    for check in suggested_checks:
                        lines.append(f"  - {check}")
                time_ranges = item.get("time_ranges")
                if isinstance(time_ranges, list) and time_ranges:
                    lines.extend(
                        _format_time_ranges_for_report(
                            time_ranges,
                            max_display=report_max_time_ranges,
                        )
                    )
                lines.append(f"- Confidence: {item.get('confidence', 'unknown')}")
                lines.append("")
        else:
            lines.append(
                "- No prioritized findings surfaced. The plots and technical details "
                "still describe the track's measured shape.\n"
            )

    lines.append("## Plots\n")
    for filename in plot_files:
        try:
            graph = graph_by_filename(filename)
            title = graph.display_name
            note = graph.report_note
        except KeyError:
            title = Path(filename).stem.replace("_", " ").title()
            note = None
        lines.append(f"### {title}\n")
        if note is not None:
            lines.append(f"{note}\n")
        alt_text = plot_alt_text(filename, summary)
        lines.append(f"![{alt_text}]({filename})\n")

    lines.append("## Human notes\n")
    lines.append("- Observations:")
    lines.append("- EQ ideas:")
    lines.append("- Dynamics notes:")
    lines.append("- Stereo/image notes:")

    out = Path(out_dir) / "report.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out
