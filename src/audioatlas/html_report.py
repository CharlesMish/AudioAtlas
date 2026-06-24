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
    _source_range_label,
    report_build_metadata,
)
from audioatlas.theme import default_theme_name, theme_css_variables, validate_theme_name
from audioatlas.utils import mmss

WIDE_PLOTS = {
    "04_log_spectrogram.png",
    "05_average_spectrum.png",
    "10_band_energy_timeline.png",
    "11_onset_density.png",
    "12_chroma_cqt.png",
    "13_short_term_lufs.png",
}

PLOT_CAPTIONS: dict[str, str] = {
    "01_waveform_rms.png": "What this shows: raw samples with the RMS envelope overlaid.",
    "02_rms_timeline.png": "What this shows: frame-by-frame RMS energy over time.",
    "03_crest_factor_timeline.png": (
        "What this shows: per-frame peak-to-RMS contrast in dB. Higher values mean "
        "more transient-like frames within this track; this is not punch or quality."
    ),
    "04_log_spectrogram.png": (
        "What this shows: frequency content over time on a log-frequency axis. "
        + RELATIVE_DB_NOTE
    ),
    "05_average_spectrum.png": (
        "What this shows: the track's long-term Welch average spectrum. "
        + RELATIVE_DB_NOTE
    ),
    "06_sample_histogram.png": (
        "What this shows: sample-value distribution with clipping and near-clipping thresholds."
    ),
    "07_stereo_correlation.png": (
        "What this shows: the measured left/right channel relationship over time."
    ),
    "08_mid_side_energy.png": (
        "What this shows: mid and side RMS energy over time with the side-to-mid ratio."
    ),
    "09_spectral_shape.png": (
        "What this shows: spectral centroid, rolloff, and bandwidth movement over time."
    ),
    "10_band_energy_timeline.png": (
        "What this shows: broad frequency-band energy movement within the track. "
        + RELATIVE_DB_NOTE
    ),
    "11_onset_density.png": (
        "What this shows: attack/activity movement within this track, not punch or quality."
    ),
    "12_chroma_cqt.png": (
        "What this shows: pitch-class energy over time within this track. "
        "This is not key detection and values are not calibrated across unrelated songs."
    ),
    "13_short_term_lufs.png": (
        "What this shows: K-weighted short-term loudness in 3 s windows over time. "
        "This is distinct from the RMS timeline and from integrated LUFS."
    ),
}

GLOSSARY: list[tuple[str, str]] = [
    (
        "LUFS",
        "Integrated LUFS is a whole-track loudness measurement weighted toward human hearing. "
        "It gives delivery context, not a quality judgment.",
    ),
    (
        "Short-term LUFS",
        "Short-term LUFS is a time-varying K-weighted loudness measurement using 3 s windows. "
        "It shows where this track is louder or quieter over time and is distinct from RMS.",
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
        "Crest factor",
        "Crest factor is peak-to-RMS contrast in dB. It describes measured peak contrast, "
        "not punch, quality, or dynamic range.",
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
        "Chroma CQT",
        "Chroma CQT shows pitch-class energy within this track. It is not key detection, "
        "chord detection, or harmonic-quality analysis.",
    ),
    (
        "Relative dB",
        "Relative dB plots show shape within this track. They are useful for shape within this "
        "track; not comparable to dBFS values from meters or other songs.",
    ),
]

TECHNICAL_BLOCKS: list[tuple[str, str]] = [
    ("Level metrics", "levels"),
    ("Crest factor timeline", "crest_factor_timeline"),
    ("Stereo metrics", "stereo_correlation"),
    ("Spectrum metrics", "average_spectrum"),
    ("Spectral shape", "spectral_shape"),
    ("Band energy timeline", "band_energy_timeline"),
    ("Onset density", "onset_density"),
    ("Chroma CQT", "chroma_cqt"),
    ("Short-term LUFS", "short_term_lufs"),
    ("Analysis config", "analysis_config"),
]


def write_report_html(
    summary: dict[str, Any],
    plot_files: list[str],
    out_dir: str | Path,
    findings: dict[str, Any] | None = None,
    *,
    theme_name: str | None = None,
) -> Path:
    """Write a static, local report.html."""

    selected_theme = validate_theme_name(theme_name or default_theme_name())
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
    source_range = _source_range_label(metadata)
    build_metadata = report_build_metadata()

    lines = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f"<title>AudioAtlas Report - {_h(filename)}</title>",
        "<style>",
        _css(selected_theme),
        "</style>",
        "</head>",
        "<body>",
        '<div class="container">',
        "<header>",
        f"<h1>{_h(filename)}</h1>",
        '<div class="subtitle">Measurement-based findings, not quality judgments.</div>',
        '<div class="meta-chips">',
        _chip("Duration", duration_label),
        _chip("Source range", source_range) if source_range is not None else "",
        _chip("Sample rate", f"{_fmt_value(metadata.get('samplerate'))} Hz"),
        _chip("Channels", _fmt_value(metadata.get("channels"))),
        _chip("Format", f"{_fmt_value(metadata.get('format'))} / {_fmt_value(metadata.get('subtype'))}"),
        _chip("Generated", build_metadata["generated_at"]),
        _chip("AudioAtlas", build_metadata["audioatlas_version"]),
        _chip("Git", build_metadata.get("git_hash", "unavailable")),
        _chip("Release", "public early alpha"),
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
        "<p>Use this alpha report as a workflow: review Delivery / headroom context, "
        "scan Findings for checks worth prioritizing, then inspect the referenced plots "
        "and verify by listening.</p>",
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
        _lightbox_overlay(),
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
                f'<div class="plot-image-wrapper" data-title="{_h(title)}" data-filename="{_h(filename)}">',
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


def _css(theme_name: str | None = None) -> str:
    return (
        theme_css_variables(theme_name)
        + """
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
.top-nav span { color: var(--text-soft); }
section { margin-top: 34px; }
.how-to-read { background: var(--callout-bg); border: 1px solid var(--border); border-left: 4px solid var(--callout-border); padding: 16px 18px; margin: 0 0 30px; border-radius: 8px; font-size: 14px; color: var(--text-muted); box-shadow: 0 1px 0 rgba(15, 23, 42, 0.02); }
.how-to-read strong { display: block; margin-bottom: 4px; color: var(--text); }
.how-to-read p { margin: 4px 0; }
.section-intro { font-size: 13.5px; color: var(--text-muted); max-width: 76ch; margin: 0 0 16px; }
.metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(158px, 1fr)); gap: 12px; }
.metric-card, .finding-card, .plot-card, details, .note-box, .context-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; box-shadow: var(--shadow-card); }
.metric-card { min-height: 116px; padding: 18px 16px 16px; display: flex; flex-direction: column; justify-content: space-between; }
.context-card { margin-top: 14px; padding: 16px 18px; border-color: var(--border); background: var(--surface); }
.context-card h3 { font-size: 14px; margin: 0 0 6px; }
.context-card p { margin: 0; color: var(--text-muted); }
.metric-value { font-size: 24px; font-weight: 700; line-height: 1.05; margin-bottom: 8px; color: var(--text); }
.metric-label { font-size: 12.5px; color: var(--text-muted); font-weight: 560; }
.metric-note { font-size: 11.5px; color: var(--text-soft); margin-top: 2px; }
.findings-list { display: flex; flex-direction: column; gap: 14px; }
.finding-card { padding: 18px 20px; font-size: 13.5px; }
.finding-header { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
.priority { font-size: 10.5px; font-weight: 680; padding: 3px 8px; border-radius: 999px; text-transform: uppercase; letter-spacing: 0; }
.priority-issue { background: var(--issue-bg); color: var(--issue-text); border: 1px solid var(--issue-border); }
.priority-warning { background: var(--warning-bg); color: var(--warning-text); border: 1px solid var(--warning-border); }
.priority-info { background: var(--info-bg); color: var(--info-text); border: 1px solid var(--info-border); }
.category { font-size: 11px; background: var(--trait-bg); color: var(--trait-text); padding: 3px 8px; border-radius: 999px; border: 1px solid var(--trait-border); }
.finding-title { font-size: 17px; font-weight: 680; margin: 0 0 10px; line-height: 1.3; }
.evidence, .why { margin: 8px 0; color: var(--text-muted); }
.evidence-list { margin: 6px 0 10px; padding-left: 20px; }
.evidence-list li { margin-bottom: 4px; }
.checks { margin: 6px 0 2px; padding-left: 20px; }
.checks li { margin-bottom: 4px; }
.finding-card h4 { margin: 14px 0 5px; font-size: 13px; color: var(--text); }
.time-ranges { font-size: 12.5px; background: var(--surface-muted); padding: 10px 12px; border-radius: 6px; margin-top: 12px; border: 1px solid var(--border-soft); border-left: 3px solid var(--callout-border); color: var(--text-muted); }
.range-list { margin: 6px 0 0; padding-left: 18px; }
.suppressed-note, .empty { font-size: 13px; color: var(--text-muted); background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 12px 14px; box-shadow: var(--shadow-card); }
.plots-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 18px; }
.plot-card { padding: 16px 16px 15px; }
.plot-card-wide { grid-column: 1 / -1; }
.plot-card h3 { font-size: 14.5px; margin-bottom: 10px; color: var(--text); }
.plot-image-wrapper { background: var(--surface-muted); border: 1px solid var(--border-soft); border-radius: 6px; padding: 8px; margin-bottom: 10px; overflow: hidden; }
.plot-image-wrapper img { width: 100%; height: auto; display: block; border-radius: 4px; }
.plot-filename { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11px; color: var(--text-soft); text-align: center; }
.plot-desc { font-size: 12.5px; color: var(--text-muted); margin: 8px 0 0; }
details { margin-bottom: 10px; overflow: hidden; }
details summary { padding: 12px 15px; font-weight: 600; cursor: pointer; user-select: none; font-size: 14px; color: var(--text); }
details[open] summary { border-bottom: 1px solid var(--border); }
.details-body { padding: 14px 16px 16px; font-size: 13px; }
.glossary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }
.glossary-item { padding: 2px 0; }
.glossary-item h3 { font-size: 14px; margin-bottom: 5px; color: var(--text); }
.glossary-item p { margin: 0; color: var(--text-muted); }
.metrics-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.metrics-table td { padding: 6px 0; border-bottom: 1px solid var(--border-soft); vertical-align: top; }
.metrics-table td:first-child { width: 36%; color: var(--text-muted); }
.notes-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }
.note-box { padding: 13px 14px; }
.note-box label { display: block; font-size: 12.5px; font-weight: 600; margin-bottom: 7px; color: var(--text-muted); }
.note-box textarea { width: 100%; min-height: 96px; border: 1px solid var(--border); border-radius: 6px; padding: 9px; font-family: inherit; font-size: 13px; resize: vertical; background: var(--surface-muted); color: var(--text); }
.note-box textarea:focus { outline: 2px solid var(--accent-muted); border-color: #5eead4; }
.footer-note { margin-top: 48px; font-size: 11.5px; color: var(--text-soft); border-top: 1px solid var(--border); padding-top: 16px; }
@media (max-width: 520px) {
  .plots-grid { grid-template-columns: 1fr; }
  .container { padding: 20px 12px 56px; }
  h1 { font-size: 26px; }
  h2 { font-size: 18px; margin-top: 34px; }
  .metric-card { min-height: 100px; }
}

/* Lightbox overlay for plot images (static, offline, no external deps).
   Calm dark scrim + surface modal. Matches AudioAtlas colors/spacing.
   Clickable plot wrappers get affordance. */
.plot-image-wrapper { cursor: zoom-in; }
.plot-image-wrapper:hover {
  border-color: var(--border);
  box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.06);
}

.lightbox {
  position: fixed;
  inset: 0;
  background: var(--lightbox-scrim);
  display: none;
  align-items: center;
  justify-content: center;
  z-index: 99999;
  padding: 24px 16px;
}
.lightbox.open { display: flex; }
.lightbox-content {
  background: var(--lightbox-surface);
  border-radius: 10px;
  width: 100%;
  max-width: 1080px;
  max-height: 94vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 10px 50px rgba(0, 0, 0, 0.35);
  overflow: hidden;
  border: 1px solid var(--border);
}
.lightbox-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: var(--surface-muted);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.lightbox-nav {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
.lightbox-nav button {
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text);
  width: 32px;
  height: 32px;
  border-radius: 6px;
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.1s ease, border-color 0.1s ease;
}
.lightbox-nav button:hover {
  background: var(--accent-muted);
  border-color: var(--accent);
}
.lightbox-nav button:disabled {
  opacity: 0.4;
  cursor: default;
}
.lightbox-counter {
  font-size: 12.5px;
  color: var(--text-soft);
  font-variant-numeric: tabular-nums;
  min-width: 48px;
  text-align: center;
  padding: 0 6px;
}
.lightbox-meta {
  flex: 1;
  min-width: 0;
  padding-left: 8px;
}
.lightbox-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.lightbox-filename {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11.5px;
  color: var(--text-soft);
  margin-top: 1px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.lightbox-close {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-muted);
  width: 34px;
  height: 34px;
  border-radius: 6px;
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-left: 8px;
}
.lightbox-close:hover {
  background: var(--issue-bg);
  border-color: var(--issue-border);
  color: var(--issue-text);
}
.lightbox-image-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface-muted);
  padding: 18px;
  overflow: auto;
  min-height: 240px;
}
.lightbox-image-wrap img {
  max-width: 100%;
  max-height: 72vh;
  width: auto;
  height: auto;
  display: block;
  border-radius: 4px;
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.08);
  background: #fff;
}
.lightbox-footer {
  padding: 10px 14px;
  border-top: 1px solid var(--border);
  font-size: 12.5px;
  color: var(--text-muted);
  background: var(--surface);
  flex-shrink: 0;
}
.lightbox-footer .hint { color: var(--text-soft); font-size: 11.5px; }

@media (max-width: 640px) {
  .lightbox-content { max-height: 96vh; }
  .lightbox-header { padding: 8px 10px; }
  .lightbox-image-wrap { padding: 12px; }
  .lightbox-title { font-size: 14px; }
}
"""
    )


def _lightbox_overlay() -> str:
    """Return the static lightbox overlay HTML + minimal inline JS.

    - Uses real relative PNG srcs from the plot cards.
    - All dynamic text comes from already-escaped data-* attrs.
    - No external resources, no CDN, works on file:// .
    - Matches the design prototype behavior and requirements.
    """
    html = (
        '<div id="lightbox" class="lightbox" aria-hidden="true" role="dialog" aria-modal="true" aria-label="Plot image viewer">'
        '<div class="lightbox-content" role="document">'
        '<div class="lightbox-header">'
        '<div class="lightbox-nav">'
        '<button id="lb-prev" type="button" aria-label="Previous image" title="Previous (left arrow)">←</button>'
        '<button id="lb-next" type="button" aria-label="Next image" title="Next (right arrow)">→</button>'
        '<span class="lightbox-counter" id="lb-counter">1 / 1</span>'
        '</div>'
        '<div class="lightbox-meta">'
        '<div class="lightbox-title" id="lb-title">Plot</div>'
        '<div class="lightbox-filename" id="lb-filename"></div>'
        '</div>'
        '<button class="lightbox-close" id="lb-close" type="button" aria-label="Close viewer" title="Close (Esc)">×</button>'
        '</div>'
        '<div class="lightbox-image-wrap" id="lb-image-wrap">'
        '<img id="lb-img" alt="Enlarged plot image" />'
        '</div>'
        '<div class="lightbox-footer">'
        '<span>Click dark backdrop or press <strong>Esc</strong> to close • Arrow keys or buttons navigate (wraps)</span>'
        '</div>'
        '</div>'
        '</div>'
        '<script>'
        '(function(){'
        '"use strict";'
        'var lb=document.getElementById("lightbox"),'
        'lbImg=document.getElementById("lb-img"),'
        'lbTitle=document.getElementById("lb-title"),'
        'lbFilename=document.getElementById("lb-filename"),'
        'lbCounter=document.getElementById("lb-counter"),'
        'btnPrev=document.getElementById("lb-prev"),'
        'btnNext=document.getElementById("lb-next"),'
        'btnClose=document.getElementById("lb-close"),'
        'imageWrap=document.getElementById("lb-image-wrap");'
        'var items=[],currentIndex=0,isOpen=false;'
        'function collectItems(){'
        'items=[];'
        'var wrappers=document.querySelectorAll(".plots-grid .plot-image-wrapper");'
        'for(var i=0;i<wrappers.length;i++){'
        'var w=wrappers[i],img=w.querySelector("img");if(!img)continue;'
        'items.push({'
        'title:w.getAttribute("data-title")||"Plot",'
        'filename:w.getAttribute("data-filename")||"",'
        'src:img.getAttribute("src")||""'
        '});'
        '}'
        '}'
        'function updateCounter(){if(!items.length)return;lbCounter.textContent=(currentIndex+1)+" / "+items.length;}'
        'function showItem(idx){if(!items.length)return;currentIndex=((idx%items.length)+items.length)%items.length;var it=items[currentIndex];lbImg.src=it.src;lbTitle.textContent=it.title;lbFilename.textContent=it.filename;updateCounter();}'
        'function openLightbox(startIndex){if(!items.length)collectItems();if(!items.length)return;currentIndex=startIndex||0;showItem(currentIndex);lb.classList.add("open");lb.setAttribute("aria-hidden","false");document.body.style.overflow="hidden";isOpen=true;setTimeout(function(){btnClose&&btnClose.focus();},30);}'
        'function closeLightbox(){lb.classList.remove("open");lb.setAttribute("aria-hidden","true");document.body.style.overflow="";isOpen=false;}'
        'function goPrev(){if(!items.length)return;showItem(currentIndex-1);}'
        'function goNext(){if(!items.length)return;showItem(currentIndex+1);}'
        'function attachClickHandlers(){'
        'var wrappers=document.querySelectorAll(".plots-grid .plot-image-wrapper");'
        'for(var i=0;i<wrappers.length;i++){(function(index){wrappers[index].addEventListener("click",function(e){openLightbox(index);});})(i);}'
        '}'
        'if(lb){lb.addEventListener("click",function(e){if(e.target===lb)closeLightbox();});}'
        'if(btnPrev)btnPrev.addEventListener("click",function(e){e.stopPropagation();goPrev();});'
        'if(btnNext)btnNext.addEventListener("click",function(e){e.stopPropagation();goNext();});'
        'if(btnClose)btnClose.addEventListener("click",function(e){e.stopPropagation();closeLightbox();});'
        'document.addEventListener("keydown",function(e){if(!isOpen)return;if(e.key==="Escape"||e.key==="Esc"){e.preventDefault();closeLightbox();}else if(e.key==="ArrowLeft"){e.preventDefault();goPrev();}else if(e.key==="ArrowRight"){e.preventDefault();goNext();}});'
        'if(imageWrap&&lbImg)imageWrap.addEventListener("click",function(e){if(e.target===lbImg)goNext();});'
        'if(lbImg)lbImg.addEventListener("dragstart",function(e){e.preventDefault();});'
        'function init(){collectItems();attachClickHandlers();}'
        'if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);else init();'
        '})();'
        '</script>'
    )
    return html
