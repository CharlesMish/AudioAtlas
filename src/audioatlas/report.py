"""Report helpers for AudioAtlas.

Only Markdown + JSON for v0.1. HTML is deferred to a later task; see
``docs/AGENT_TASKS.md``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
PER_CHANNEL_METRIC_DISPLAY: list[tuple[str, str, str]] = [
    ("peak_dbfs_per_channel",      "Sample peak",          "dBFS"),
    ("true_peak_dbtp_per_channel", "True-peak (approx.)",  "dBTP"),
    ("rms_dbfs_per_channel",       "RMS",                  "dBFS"),
    ("dc_offset_per_channel",      "DC offset",            ""),
]


def write_summary_json(summary: dict[str, Any], out_dir: str | Path) -> Path:
    """Write summary.json."""

    out = Path(out_dir) / "summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return out


def _fmt_value(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def write_report_md(
    summary: dict[str, Any], plot_files: list[str], out_dir: str | Path
) -> Path:
    """Write a deliberately simple Markdown report.

    The report's job is to lay out measured facts and the generated plots.
    It must not produce verdicts ("your mix is muddy", "this is well mastered").
    See AGENT_BRIEF.md for the rationale.
    """

    metadata = summary.get("metadata", {})
    levels = summary.get("levels", {})
    rms = summary.get("rms_envelope", {})
    spectrum = summary.get("average_spectrum", {})
    stereo = summary.get("stereo_correlation", {})
    mid_side = summary.get("mid_side_energy", {})

    lines: list[str] = []
    lines.append(f"# AudioAtlas Report: {metadata.get('filename', 'unknown')}\n")

    duration = levels.get("duration_seconds")
    if isinstance(duration, (int, float)):
        duration_label = f"{duration:.2f}s ({mmss(float(duration))})"
    else:
        duration_label = "unknown"

    lines.append("## File\n")
    lines.append(f"- Duration: {duration_label}")
    lines.append(f"- Sample rate: {metadata.get('samplerate', 'unknown')} Hz")
    lines.append(f"- Channels: {metadata.get('channels', 'unknown')}")
    lines.append(
        f"- Format: {metadata.get('format', 'unknown')} / {metadata.get('subtype', 'unknown')}\n"
    )

    lines.append("## Level metrics\n")
    lines.append("| Metric | Value | Unit |")
    lines.append("|---|---|---|")
    for key, label, unit in LEVEL_METRIC_DISPLAY:
        lines.append(f"| {label} | {_fmt_value(levels.get(key))} | {unit} |")
    lines.append("")

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

    lines.append("## Average spectrum summary\n")
    for key, value in spectrum.items():
        lines.append(f"- {key}: {_fmt_value(value)}")
    lines.append("")

    if stereo:
        lines.append("## Stereo correlation summary\n")
        for key, value in stereo.items():
            if key == "warnings":
                continue
            lines.append(f"- {key}: {_fmt_value(value)}")
        stereo_warnings = stereo.get("warnings") or []
        for warning in stereo_warnings:
            lines.append(f"- warning: {warning}")
        lines.append("")

    if mid_side:
        lines.append("## Mid/side energy summary\n")
        for key, value in mid_side.items():
            if key == "warnings":
                continue
            lines.append(f"- {key}: {_fmt_value(value)}")
        mid_side_warnings = mid_side.get("warnings") or []
        for warning in mid_side_warnings:
            lines.append(f"- warning: {warning}")
        lines.append("")

    lines.append("## Plots\n")
    for filename in plot_files:
        title = Path(filename).stem.replace("_", " ").title()
        lines.append(f"### {title}\n")
        lines.append(f"![{title}]({filename})\n")

    lines.append("## Human notes\n")
    lines.append("- Observations:")
    lines.append("- EQ ideas:")
    lines.append("- Dynamics notes:")
    lines.append("- Stereo/image notes:")

    out = Path(out_dir) / "report.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out
