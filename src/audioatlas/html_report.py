"""Static HTML report writer for AudioAtlas."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from audioatlas.report import (
    PLOT_DISPLAY_NAMES,
    RELATIVE_DB_NOTE,
    SEVERITY_DISPLAY,
    _fmt_value,
    _format_range_short,
    _normalized_time_ranges,
    _positive_int,
    _select_time_range_examples,
)
from audioatlas.utils import mmss

WIDE_PLOTS = {
    "03_log_spectrogram.png",
    "04_average_spectrum.png",
    "09_band_energy_timeline.png",
    "10_onset_density.png",
}

PLOT_CAPTIONS: dict[str, str] = {
    "01_waveform_rms.png": "What this shows: raw samples with the RMS envelope overlaid.",
    "02_rms_timeline.png": "What this shows: frame-by-frame RMS energy over time.",
    "03_log_spectrogram.png": (
        "What this shows: frequency content over time on a log-frequency axis. "
        + RELATIVE_DB_NOTE
    ),
    "04_average_spectrum.png": (
        "What this shows: the track's long-term Welch average spectrum. "
        + RELATIVE_DB_NOTE
    ),
    "05_sample_histogram.png": (
        "What this shows: sample-value distribution with clipping and near-clipping thresholds."
    ),
    "06_stereo_correlation.png": (
        "What this shows: the measured left/right channel relationship over time."
    ),
    "07_mid_side_energy.png": (
        "What this shows: mid and side RMS energy over time with the side-to-mid ratio."
    ),
    "08_spectral_shape.png": (
        "What this shows: spectral centroid, rolloff, and bandwidth movement over time."
    ),
    "09_band_energy_timeline.png": (
        "What this shows: broad frequency-band energy movement within the track. "
        + RELATIVE_DB_NOTE
    ),
    "10_onset_density.png": (
        "What this shows: attack/activity movement within this track, not punch or quality."
    ),
}

GLOSSARY: list[tuple[str, str]] = [
    (
        "LUFS",
        "Integrated LUFS is a whole-track loudness measurement weighted toward human hearing. "
        "It gives delivery context, not a quality judgment.",
    ),
    (
        "True peak",
        "True peak estimates reconstructed peaks between samples. Values above 0 dBTP can matter "
        "for playback, conversion, or encoding headroom.",
    ),
    (
        "Sample peak",
        "Sample peak is the largest stored sample value in the file. It is not loudness or density.",
    ),
    (
        "RMS",
        "RMS is average signal energy. The RMS timeline is useful for seeing where energy rises "
        "or falls across the track.",
    ),
    (
        "PLR",
        "PLR is the relationship between true peak and integrated loudness. Higher PLR means "
        "more peak headroom relative to loudness; lower PLR means the track is more consistently loud.",
    ),
    (
        "Clipping / near-clipping",
        "Clipping counts samples at the configured ceiling; near-clipping counts samples close to it. "
        "Use the waveform and histogram to inspect where these samples occur.",
    ),
    (
        "Stereo correlation",
        "Stereo correlation describes the L/R relationship. +1 means nearly identical channels; "
        "0 means loosely related; negative values indicate opposite-polarity/decorrelated content.",
    ),
    (
        "Side/mid ratio",
        "Side/mid ratio compares stereo-difference energy with center energy. 0 dB means side "
        "and mid energy are similar; more negative means mid-dominant; closer to 0 means more side energy.",
    ),
    (
        "Spectral centroid",
        "Spectral centroid is the spectrum's center-of-mass frequency. It moves higher when "
        "energy shifts upward in frequency, and lower when energy is weighted toward lows/mids.",
    ),
    (
        "Rolloff",
        "Spectral rolloff marks the frequency below which most measured spectral energy sits.",
    ),
    (
        "Spectral bandwidth",
        "Spectral bandwidth describes how spread out the spectrum is around the centroid.",
    ),
    (
        "Average spectrum",
        "Average spectrum is the long-term frequency profile of the track. Relative values show "
        "shape within the file.",
    ),
    (
        "Band energy",
        "Band energy summarizes broad frequency ranges. Relative band values do not indicate "
        "absolute dBFS level.",
    ),
    (
        "Onset density",
        "Onset density is an attack/activity map for this track. It is not punch, groove quality, "
        "drum hits per second, or mix quality. Absolute onset-density values are not reliable "
        "quality comparisons across songs.",
    ),
    (
        "Relative dB",
        "Relative dB plots show shape within this track. They are useful for shape within this "
        "track; not comparable to dBFS values from meters or other songs.",
    ),
]

TECHNICAL_BLOCKS: list[tuple[str, str]] = [
    ("Level metrics", "levels"),
    ("Stereo metrics", "stereo_correlation"),
    ("Spectrum metrics", "average_spectrum"),
    ("Spectral shape", "spectral_shape"),
    ("Band energy timeline", "band_energy_timeline"),
    ("Onset density", "onset_density"),
    ("Analysis config", "analysis_config"),
]


def write_report_html(
    summary: dict[str, Any],
    plot_files: list[str],
    out_dir: str | Path,
    findings: dict[str, Any] | None = None,
) -> Path:
    """Write a static, local report.html."""

    metadata = summary.get("metadata") if isinstance(summary.get("metadata"), dict) else {}
    levels = summary.get("levels") if isinstance(summary.get("levels"), dict) else {}
    stereo = (
        summary.get("stereo_correlation")
        if isinstance(summary.get("stereo_correlation"), dict)
        else {}
    )
    mid_side = (
        summary.get("mid_side_energy") if isinstance(summary.get("mid_side_energy"), dict) else {}
    )
    analysis_config = (
        summary.get("analysis_config") if isinstance(summary.get("analysis_config"), dict) else {}
    )
    report_max_time_ranges = _positive_int(
        analysis_config, "report_max_time_ranges", default=8
    )

    filename = str(metadata.get("filename", "unknown"))
    duration = levels.get("duration_seconds")
    if isinstance(duration, (int, float)):
        duration_label = f"{duration:.2f}s ({mmss(float(duration))})"
    else:
        duration_label = "unknown"

    lines = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f"<title>AudioAtlas Report - {_h(filename)}</title>",
        "<style>",
        _css(),
        "</style>",
        "</head>",
        "<body>",
        '<div class="container">',
        "<header>",
        f"<h1>{_h(filename)}</h1>",
        '<div class="subtitle">Measurement-based findings, not quality judgments.</div>',
        '<div class="meta-chips">',
        _chip("Duration", duration_label),
        _chip("Sample rate", f"{_fmt_value(metadata.get('samplerate'))} Hz"),
        _chip("Channels", _fmt_value(metadata.get("channels"))),
        _chip("Format", f"{_fmt_value(metadata.get('format'))} / {_fmt_value(metadata.get('subtype'))}"),
        "</div>",
        '<nav class="top-nav" aria-label="Report sections">',
        '<a href="#findings">Findings</a><span>.</span>',
        '<a href="#plots">Plots</a><span>.</span>',
        '<a href="#glossary">Understanding these numbers</a><span>.</span>',
        '<a href="#technical">Technical details</a><span>.</span>',
        '<a href="#notes">Human notes</a>',
        "</nav>",
        "</header>",
        '<section class="how-to-read" id="how-to-read">',
        "<strong>How to read this report</strong>",
        "<p>Start with Findings, then inspect the referenced plots. AudioAtlas measurements "
        "are observations for listening and inspection, not quality judgments.</p>",
        f"<p>{_h(RELATIVE_DB_NOTE)}</p>",
        "<p>Check before delivery / worth a listen / for reference indicate priority, not quality.</p>",
        "<p>A report can have no prioritized findings; the plots still describe the track's measured shape.</p>",
        "</section>",
        '<section id="metrics">',
        "<h2>Key metrics</h2>",
        '<div class="metrics-grid">',
        _metric_card("Integrated LUFS", levels.get("integrated_lufs"), "LUFS"),
        _metric_card("True peak", levels.get("true_peak_dbtp"), "dBTP"),
        _metric_card("Sample peak", levels.get("sample_peak_dbfs"), "dBFS"),
        _metric_card("RMS", levels.get("rms_dbfs"), "dBFS"),
        _metric_card("PLR", levels.get("plr_db"), "dB"),
        _metric_card("Clipped samples", levels.get("clipped_samples"), ""),
        _metric_card("Near-clipping samples", levels.get("near_clipping_samples"), ""),
        _metric_card("Median stereo correlation", stereo.get("correlation_median"), "Pearson r"),
        _metric_card("Median side/mid ratio", mid_side.get("side_to_mid_ratio_db_median"), "dB"),
        "</div>",
        _delivery_context_html(levels),
        "</section>",
        _findings_section(findings, report_max_time_ranges),
        _plots_section(plot_files),
        _glossary_section(),
        _technical_section(summary),
        _notes_section(),
        '<p class="footer-note">AudioAtlas reports measured facts and visual maps. The listener decides what matters for the track.</p>',
        "</div>",
        "</body>",
        "</html>",
        "",
    ]

    out = Path(out_dir) / "report.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def _h(value: Any) -> str:
    return escape(str(value), quote=True)


def _chip(label: str, value: Any) -> str:
    return f'<div class="chip"><strong>{_h(label)}</strong> {_h(value)}</div>'


def _metric_card(label: str, value: Any, unit: str) -> str:
    value_text = _fmt_value(value)
    unit_html = f'<div class="metric-note">{_h(unit)}</div>' if unit else ""
    return (
        '<div class="metric-card">'
        f'<div class="metric-value">{_h(value_text)}</div>'
        f'<div class="metric-label">{_h(label)}</div>'
        f"{unit_html}</div>"
    )


def _delivery_context_html(levels: dict[str, Any]) -> str:
    integrated_lufs = levels.get("integrated_lufs")
    if (
        not isinstance(integrated_lufs, (int, float))
        or isinstance(integrated_lufs, bool)
        or integrated_lufs <= -10.0
    ):
        return ""
    return (
        '<div class="context-card">'
        "<h3>Delivery / headroom context</h3>"
        f"<p>Integrated loudness: {_h(_fmt_value(integrated_lufs))} LUFS. "
        "This is above many streaming normalization reference levels; platforms that "
        "normalize playback may reduce level.</p>"
        "</div>"
    )


def _findings_section(findings: dict[str, Any] | None, max_display: int) -> str:
    lines = [
        '<section id="findings">',
        "<h2>Findings</h2>",
        '<p class="section-intro">Findings are measurement-based observations derived '
        "from the analysis. They highlight values or regions worth checking by ear; "
        "they are not quality judgments.</p>",
    ]
    if not isinstance(findings, dict):
        lines.append('<p class="empty">No findings data was provided.</p>')
        lines.append("</section>")
        return "\n".join(lines)

    suppressed = findings.get("findings_suppressed_count")
    if isinstance(suppressed, int) and suppressed > 0:
        lines.append(
            f'<p class="suppressed-note">{suppressed} lower-priority finding(s) suppressed; '
            "see findings.json for details.</p>"
        )

    items = findings.get("findings_shown")
    if not isinstance(items, list):
        items = findings.get("findings")
    if not isinstance(items, list) or not items:
        lines.append(
            "<p class=\"empty\">No prioritized findings surfaced. The plots and technical "
            "details still describe the track's measured shape.</p>"
        )
        lines.append("</section>")
        return "\n".join(lines)

    lines.append('<div class="findings-list">')
    for item in items:
        if isinstance(item, dict):
            lines.append(_finding_card(item, max_display))
    lines.append("</div>")
    lines.append("</section>")
    return "\n".join(lines)


def _finding_card(item: dict[str, Any], max_display: int) -> str:
    severity = str(item.get("severity", "info"))
    priority = SEVERITY_DISPLAY.get(severity, severity)
    lines = [
        '<article class="finding-card">',
        '<div class="finding-header">',
        f'<span class="priority priority-{_h(severity)}">{_h(priority)}</span>',
        f'<span class="category">{_h(item.get("category", "unknown"))}</span>',
        "</div>",
        f'<h3 class="finding-title">{_h(item.get("title", "Finding"))}</h3>',
    ]
    evidence_items = item.get("evidence_items")
    if isinstance(evidence_items, list) and evidence_items:
        lines.append('<div class="evidence"><strong>Evidence:</strong></div>')
        lines.append('<ul class="evidence-list">')
        for evidence_item in evidence_items:
            lines.append(f"<li>{_h(evidence_item)}</li>")
        lines.append("</ul>")
    else:
        lines.append(
            f'<p class="evidence"><strong>Evidence:</strong> {_h(item.get("evidence", ""))}</p>'
        )
    lines.append(
        f'<p class="why"><strong>Why it matters:</strong> {_h(item.get("why_it_matters", ""))}</p>'
    )
    does_not_mean = item.get("does_not_mean")
    if isinstance(does_not_mean, str) and does_not_mean:
        lines.append(f'<p class="why"><strong>Does not mean:</strong> {_h(does_not_mean)}</p>')

    checks = item.get("suggested_checks")
    if isinstance(checks, list) and checks:
        lines.append("<h4>Suggested listening checks</h4>")
        lines.append('<ul class="checks">')
        for check in checks:
            lines.append(f"<li>{_h(check)}</li>")
        lines.append("</ul>")

    time_ranges = item.get("time_ranges")
    if isinstance(time_ranges, list):
        lines.extend(_html_time_ranges(time_ranges, max_display))
    lines.append("</article>")
    return "\n".join(lines)


def _html_time_ranges(time_ranges: list[Any], max_display: int) -> list[str]:
    ranges = _normalized_time_ranges(time_ranges)
    if not ranges:
        return []
    total_duration = sum(item["duration"] for item in ranges)
    longest = max(ranges, key=lambda item: item["duration"])
    examples = _select_time_range_examples(ranges, max_display=max_display)
    lines = [
        '<div class="time-ranges">',
        (
            f"{len(ranges)} regions, total {total_duration:.3f}s, "
            f"longest {longest['duration']:.3f}s."
        ),
    ]
    lines.append('<ul class="range-list">')
    for item in examples:
        lines.append(f"<li>{_h(_format_range_short(item))}</li>")
    if len(examples) < len(ranges):
        lines.append("<li>see findings.json for full ranges</li>")
    lines.append("</ul>")
    lines.append("</div>")
    return lines


def _plots_section(plot_files: list[str]) -> str:
    lines = [
        '<section id="plots">',
        "<h2>Plots</h2>",
        '<p class="section-intro">Visual maps generated from the analysis.</p>',
        '<div class="plots-grid">',
    ]
    normal = [name for name in plot_files if name not in WIDE_PLOTS]
    wide = [name for name in plot_files if name in WIDE_PLOTS]
    for filename in [*normal, *wide]:
        title = PLOT_DISPLAY_NAMES.get(filename, Path(filename).stem.replace("_", " ").title())
        class_name = "plot-card plot-card-wide" if filename in WIDE_PLOTS else "plot-card"
        caption = PLOT_CAPTIONS.get(filename, "What this shows: a visual map from the analysis.")
        lines.extend(
            [
                f'<article class="{class_name}">',
                f"<h3>{_h(title)}</h3>",
                '<div class="plot-image-wrapper">',
                f'<img src="{_h(filename)}" alt="{_h(title)}">',
                "</div>",
                f'<div class="plot-filename">{_h(filename)}</div>',
                f'<p class="plot-desc">{_h(caption)}</p>',
                "</article>",
            ]
        )
    lines.append("</div>")
    lines.append("</section>")
    return "\n".join(lines)


def _glossary_section() -> str:
    lines = [
        '<section id="glossary">',
        "<h2>Understanding these numbers</h2>",
        "<details open>",
        "<summary>Metric glossary</summary>",
        '<div class="details-body glossary-grid">',
    ]
    for term, text in GLOSSARY:
        lines.append(
            f'<div class="glossary-item"><h3>{_h(term)}</h3><p>{_h(text)}</p></div>'
        )
    lines.extend(["</div>", "</details>", "</section>"])
    return "\n".join(lines)


def _technical_section(summary: dict[str, Any]) -> str:
    lines = [
        '<section id="technical">',
        "<h2>Technical details</h2>",
    ]
    for label, key in TECHNICAL_BLOCKS:
        block = summary.get(key)
        if isinstance(block, dict):
            lines.append("<details>")
            lines.append(f"<summary>{_h(label)}</summary>")
            lines.append('<div class="details-body">')
            lines.append(_dict_table(block))
            lines.append("</div>")
            lines.append("</details>")
    lines.append("</section>")
    return "\n".join(lines)


def _dict_table(block: dict[str, Any]) -> str:
    rows = ['<table class="metrics-table">']
    for key, value in block.items():
        if key == "warnings" and not value:
            continue
        rows.append("<tr>")
        rows.append(f"<td>{_h(key)}</td>")
        rows.append(f"<td>{_h(_compact_value(value))}</td>")
        rows.append("</tr>")
    rows.append("</table>")
    return "\n".join(rows)


def _compact_value(value: Any) -> str:
    if isinstance(value, dict):
        return ", ".join(f"{key}: {_compact_value(val)}" for key, val in value.items())
    if isinstance(value, list):
        if len(value) > 8:
            return f"{len(value)} item(s)"
        return ", ".join(_compact_value(item) for item in value)
    return _fmt_value(value)


def _notes_section() -> str:
    labels = ["Observations", "EQ ideas", "Dynamics notes", "Stereo/image notes"]
    lines = [
        '<section id="notes">',
        "<h2>Human notes</h2>",
        '<p class="section-intro">Notes typed here are temporary in this browser page and are not saved into the report files.</p>',
        '<div class="notes-grid">',
    ]
    for index, label in enumerate(labels):
        lines.append('<div class="note-box">')
        lines.append(f'<label for="note-{index}">{_h(label)}</label>')
        lines.append(f'<textarea id="note-{index}"></textarea>')
        lines.append("</div>")
    lines.extend(["</div>", "</section>"])
    return "\n".join(lines)


def _css() -> str:
    return """
:root {
  --bg: #f5f7f8;
  --surface: #ffffff;
  --surface-muted: #f8fafc;
  --text: #1f2937;
  --text-muted: #4b5563;
  --text-soft: #64748b;
  --border: #dfe5eb;
  --border-soft: #edf1f5;
  --accent: #0f766e;
  --accent-muted: #e6f4f1;
  --chip-bg: #eef2f5;
  --callout-bg: #f1f5f9;
  --callout-border: #94a3b8;
  --shadow-card: 0 1px 2px rgba(15, 23, 42, 0.05), 0 8px 28px rgba(15, 23, 42, 0.04);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.5;
  font-size: 15px;
}
.container { max-width: 1160px; margin: 0 auto; padding: 32px 18px 84px; }
header { margin-bottom: 24px; padding: 22px 0 6px; }
h1 { font-size: 32px; font-weight: 680; margin: 0 0 6px; line-height: 1.15; }
h2 { font-size: 20px; font-weight: 680; margin: 42px 0 12px; padding-bottom: 8px; border-bottom: 1px solid var(--border); line-height: 1.25; }
h3 { margin: 0; }
.subtitle { font-size: 14.5px; color: var(--text-muted); margin-bottom: 16px; }
.meta-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
.chip { display: inline-flex; gap: 6px; background: var(--chip-bg); border: 1px solid var(--border); border-radius: 999px; padding: 5px 12px; font-size: 12.5px; color: var(--text-muted); }
.chip strong { color: var(--text); font-weight: 550; }
.top-nav { display: flex; flex-wrap: wrap; gap: 12px; font-size: 13.5px; margin: 10px 0 26px; padding: 12px 0; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); }
.top-nav a { color: var(--accent); text-decoration: none; font-weight: 550; }
.top-nav a:hover { text-decoration: underline; }
.top-nav span { color: #cbd5e1; }
section { margin-top: 34px; }
.how-to-read { background: var(--callout-bg); border: 1px solid #d7e0ea; border-left: 4px solid var(--callout-border); padding: 16px 18px; margin: 0 0 30px; border-radius: 8px; font-size: 14px; color: #334155; box-shadow: 0 1px 0 rgba(15, 23, 42, 0.02); }
.how-to-read strong { display: block; margin-bottom: 4px; color: var(--text); }
.how-to-read p { margin: 4px 0; }
.section-intro { font-size: 13.5px; color: var(--text-muted); max-width: 76ch; margin: 0 0 16px; }
.metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(158px, 1fr)); gap: 12px; }
.metric-card, .finding-card, .plot-card, details, .note-box, .context-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; box-shadow: var(--shadow-card); }
.metric-card { min-height: 116px; padding: 18px 16px 16px; display: flex; flex-direction: column; justify-content: space-between; }
.context-card { margin-top: 14px; padding: 16px 18px; border-color: #cbd5e1; background: #fbfcfd; }
.context-card h3 { font-size: 14px; margin: 0 0 6px; }
.context-card p { margin: 0; color: var(--text-muted); }
.metric-value { font-size: 24px; font-weight: 700; line-height: 1.05; margin-bottom: 8px; color: #111827; }
.metric-label { font-size: 12.5px; color: var(--text-muted); font-weight: 560; }
.metric-note { font-size: 11.5px; color: var(--text-soft); margin-top: 2px; }
.findings-list { display: flex; flex-direction: column; gap: 14px; }
.finding-card { padding: 18px 20px; font-size: 13.5px; }
.finding-header { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
.priority { font-size: 10.5px; font-weight: 680; padding: 3px 8px; border-radius: 999px; text-transform: uppercase; letter-spacing: 0; }
.priority-issue { background: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }
.priority-warning { background: #ccfbf1; color: #115e59; border: 1px solid #99f6e4; }
.priority-info { background: #e2e8f0; color: #334155; border: 1px solid #cbd5e1; }
.category { font-size: 11px; background: var(--surface-muted); color: #475569; padding: 3px 8px; border-radius: 999px; border: 1px solid var(--border-soft); }
.finding-title { font-size: 17px; font-weight: 680; margin: 0 0 10px; line-height: 1.3; }
.evidence, .why { margin: 8px 0; color: #374151; }
.evidence-list { margin: 6px 0 10px; padding-left: 20px; }
.evidence-list li { margin-bottom: 4px; }
.checks { margin: 6px 0 2px; padding-left: 20px; }
.checks li { margin-bottom: 4px; }
.finding-card h4 { margin: 14px 0 5px; font-size: 13px; color: #334155; }
.time-ranges { font-size: 12.5px; background: var(--surface-muted); padding: 10px 12px; border-radius: 6px; margin-top: 12px; border: 1px solid var(--border-soft); border-left: 3px solid #94a3b8; color: #475569; }
.range-list { margin: 6px 0 0; padding-left: 18px; }
.suppressed-note, .empty { font-size: 13px; color: #6b7280; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 12px 14px; box-shadow: var(--shadow-card); }
.plots-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 18px; }
.plot-card { padding: 16px 16px 15px; }
.plot-card-wide { grid-column: 1 / -1; }
.plot-card h3 { font-size: 14.5px; margin-bottom: 10px; color: #1e293b; }
.plot-image-wrapper { background: var(--surface-muted); border: 1px solid var(--border-soft); border-radius: 6px; padding: 8px; margin-bottom: 10px; overflow: hidden; }
.plot-image-wrapper img { width: 100%; height: auto; display: block; border-radius: 4px; }
.plot-filename { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11px; color: #64748b; text-align: center; }
.plot-desc { font-size: 12.5px; color: #4b5563; margin: 8px 0 0; }
details { margin-bottom: 10px; overflow: hidden; }
details summary { padding: 12px 15px; font-weight: 600; cursor: pointer; user-select: none; font-size: 14px; color: #1e293b; }
details[open] summary { border-bottom: 1px solid var(--border); }
.details-body { padding: 14px 16px 16px; font-size: 13px; }
.glossary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }
.glossary-item { padding: 2px 0; }
.glossary-item h3 { font-size: 14px; margin-bottom: 5px; color: #1e293b; }
.glossary-item p { margin: 0; color: var(--text-muted); }
.metrics-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.metrics-table td { padding: 6px 0; border-bottom: 1px solid #f1f5f9; vertical-align: top; }
.metrics-table td:first-child { width: 36%; color: var(--text-muted); }
.notes-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }
.note-box { padding: 13px 14px; }
.note-box label { display: block; font-size: 12.5px; font-weight: 600; margin-bottom: 7px; color: var(--text-muted); }
.note-box textarea { width: 100%; min-height: 96px; border: 1px solid var(--border); border-radius: 6px; padding: 9px; font-family: inherit; font-size: 13px; resize: vertical; background: #fbfcfd; color: var(--text); }
.note-box textarea:focus { outline: 2px solid var(--accent-muted); border-color: #5eead4; }
.footer-note { margin-top: 48px; font-size: 11.5px; color: #6b7280; border-top: 1px solid var(--border); padding-top: 16px; }
@media (max-width: 520px) {
  .plots-grid { grid-template-columns: 1fr; }
  .container { padding: 20px 12px 56px; }
  h1 { font-size: 26px; }
  h2 { font-size: 18px; margin-top: 34px; }
  .metric-card { min-height: 100px; }
}
"""
