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

PLOT_DISPLAY_NAMES: dict[str, str] = {
    "01_waveform_rms.png": "Waveform + RMS Envelope",
    "02_rms_timeline.png": "Frame RMS Timeline",
    "03_log_spectrogram.png": "Log-Frequency Spectrogram",
    "04_average_spectrum.png": "Welch Average Spectrum",
    "05_sample_histogram.png": "Sample Histogram",
    "06_stereo_correlation.png": "Stereo Correlation Timeline",
    "07_mid_side_energy.png": "Mid/Side Energy Timeline",
    "08_spectral_shape.png": "Spectral Shape Timeline",
    "09_band_energy_timeline.png": "Frequency Band Energy Timeline",
    "10_onset_density.png": "Onset / Transient Density Timeline",
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


def write_report_md(
    summary: dict[str, Any],
    plot_files: list[str],
    out_dir: str | Path,
    findings: dict[str, Any] | None = None,
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
    spectral_shape = summary.get("spectral_shape", {})
    band_energy_timeline = summary.get("band_energy_timeline", {})
    onset_density = summary.get("onset_density", {})
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
    lines.append("Relative dB plots use track max = 0 dB and are not calibrated dBFS.\n")
    for key, value in spectrum.items():
        if key == "band_energies":
            continue
        lines.append(f"- {key}: {_fmt_value(value)}")
    lines.append("")

    band_energies = spectrum.get("band_energies")
    if isinstance(band_energies, dict) and band_energies:
        lines.append("## Band energy summary\n")
        lines.append("| Band | Range | Energy |")
        lines.append("|---|---|---|")
        for band, values in band_energies.items():
            if not isinstance(values, dict):
                continue
            low = _fmt_value(values.get("low_hz"))
            high = _fmt_value(values.get("high_hz"))
            energy = _fmt_value(values.get("energy_db"))
            lines.append(f"| {band} | {low}-{high} Hz | {energy} dB relative |")
        lines.append("")

    if spectral_shape:
        lines.append("## Spectral shape summary\n")
        for key, value in spectral_shape.items():
            if key in (
                "warnings",
                "centroid_elevated_time_ranges",
                "centroid_reduced_time_ranges",
                "centroid_large_shift_time_ranges",
            ):
                continue
            lines.append(f"- {key}: {_fmt_value(value)}")
        spectral_shape_warnings = spectral_shape.get("warnings") or []
        for warning in spectral_shape_warnings:
            lines.append(f"- warning: {warning}")
        lines.append("")

    if band_energy_timeline:
        lines.append("## Band energy timeline summary\n")
        lines.append("Relative dB values use this analysis view's maximum as 0 dB and are not calibrated dBFS.\n")
        lines.append(f"- frames: {_fmt_value(band_energy_timeline.get('frames'))}")
        lines.append(f"- valid_frames: {_fmt_value(band_energy_timeline.get('valid_frames'))}")
        lines.append(f"- strongest_band_by_median: {_fmt_value(band_energy_timeline.get('strongest_band_by_median'))}")
        bands = band_energy_timeline.get("bands")
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
        warnings = band_energy_timeline.get("warnings") or []
        for warning in warnings:
            lines.append(f"- warning: {warning}")
        lines.append("")

    if onset_density:
        lines.append("## Onset / transient density summary\n")
        for key, value in onset_density.items():
            if key in ("warnings", "high_onset_density_time_ranges"):
                continue
            lines.append(f"- {key}: {_fmt_value(value)}")
        onset_warnings = onset_density.get("warnings") or []
        for warning in onset_warnings:
            lines.append(f"- warning: {warning}")
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

    if findings is not None:
        lines.append("## Findings\n")
        lines.append(
            "Findings are prioritized factual observations. Some lower-priority "
            "observations may be omitted from this report."
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
                lines.append(f"- Severity: {item.get('severity', 'unknown')}")
                lines.append(f"- Category: {item.get('category', 'unknown')}")
                lines.append(
                    f"- Measured value: {_fmt_value(item.get('measured_value'))} "
                    f"{item.get('unit', '')}".rstrip()
                )
                lines.append(f"- Threshold: {_fmt_value(item.get('threshold'))}")
                lines.append(f"- Evidence: {item.get('evidence', '')}")
                lines.append(f"- Why it matters: {item.get('why_it_matters', '')}")
                suggested_checks = item.get("suggested_checks")
                if isinstance(suggested_checks, list) and suggested_checks:
                    lines.append("- Suggested checks:")
                    for check in suggested_checks:
                        lines.append(f"  - {check}")
                time_ranges = item.get("time_ranges")
                if isinstance(time_ranges, list) and time_ranges:
                    lines.append("- Time ranges:")
                    for item_range in time_ranges:
                        if not isinstance(item_range, dict):
                            continue
                        start = _fmt_value(item_range.get("start"))
                        end = _fmt_value(item_range.get("end"))
                        duration = _fmt_value(item_range.get("duration"))
                        lines.append(f"  - {start}s-{end}s ({duration}s)")
                lines.append(f"- Confidence: {item.get('confidence', 'unknown')}")
                lines.append("")
        else:
            lines.append("- No findings triggered by the current rule set.\n")

    lines.append("## Plots\n")
    for filename in plot_files:
        title = PLOT_DISPLAY_NAMES.get(filename, Path(filename).stem.replace("_", " ").title())
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
