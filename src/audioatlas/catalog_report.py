"""Catalog-level summary and report writers for batch mode."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from statistics import mean, median
from typing import Any

from audioatlas.utils import mmss

CATALOG_METRICS: tuple[str, ...] = (
    "integrated_lufs",
    "true_peak_dbtp",
    "sample_peak_dbfs",
    "rms_dbfs",
    "plr_db",
    "median_stereo_correlation",
    "median_side_to_mid_ratio_db",
    "centroid_median_hz",
    "rolloff_95_median_hz",
    "onset_density_median",
)

METRIC_LABELS: dict[str, str] = {
    "integrated_lufs": "Integrated LUFS",
    "true_peak_dbtp": "True peak",
    "sample_peak_dbfs": "Sample peak",
    "rms_dbfs": "RMS",
    "plr_db": "PLR",
    "median_stereo_correlation": "Median stereo correlation",
    "median_side_to_mid_ratio_db": "Median side/mid ratio",
    "centroid_median_hz": "Centroid median",
    "rolloff_95_median_hz": "95% rolloff median",
    "onset_density_median": "Onset density median",
}

METRIC_UNITS: dict[str, str] = {
    "integrated_lufs": "LUFS",
    "true_peak_dbtp": "dBTP",
    "sample_peak_dbfs": "dBFS",
    "rms_dbfs": "dBFS",
    "plr_db": "dB",
    "median_side_to_mid_ratio_db": "dB",
    "centroid_median_hz": "Hz",
    "rolloff_95_median_hz": "Hz",
}


def build_catalog_summary(
    *,
    input_folder: Path,
    output_folder: Path,
    tracks: list[dict[str, Any]],
    skipped_files: list[dict[str, str]],
) -> dict[str, Any]:
    """Build the JSON-safe catalog summary dictionary."""

    return {
        "schema_version": "0.1.0",
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "input_folder": str(input_folder),
        "output_folder": str(output_folder),
        "track_count": len(tracks),
        "skipped_files": skipped_files,
        "tracks": tracks,
        "statistics": calculate_catalog_statistics(tracks),
    }


def calculate_catalog_statistics(tracks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Calculate neutral folder-level scalar statistics."""

    stats: dict[str, dict[str, Any]] = {}
    for key in CATALOG_METRICS:
        values = [
            float(track[key])
            for track in tracks
            if isinstance(track.get(key), (int, float)) and not isinstance(track.get(key), bool)
        ]
        missing_count = len(tracks) - len(values)
        if values:
            stats[key] = {
                "count": len(values),
                "min": min(values),
                "median": median(values),
                "max": max(values),
                "mean": mean(values),
                "missing_count": missing_count,
            }
        else:
            stats[key] = {
                "count": 0,
                "min": None,
                "median": None,
                "max": None,
                "mean": None,
                "missing_count": missing_count,
            }
    return stats


def track_record_from_run(
    *,
    filename: str,
    report_path: str,
    summary: dict[str, Any],
    findings: dict[str, Any],
) -> dict[str, Any]:
    """Extract catalog fields from one single-track analysis run."""

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
    average_spectrum = (
        summary.get("average_spectrum")
        if isinstance(summary.get("average_spectrum"), dict)
        else {}
    )
    spectral_shape = (
        summary.get("spectral_shape") if isinstance(summary.get("spectral_shape"), dict) else {}
    )
    onset_density = (
        summary.get("onset_density") if isinstance(summary.get("onset_density"), dict) else {}
    )
    shown = findings.get("findings_shown")
    if not isinstance(shown, list):
        shown = findings.get("findings")
    if not isinstance(shown, list):
        shown = []

    return {
        "filename": filename,
        "report_path": report_path,
        "duration_seconds": levels.get("duration_seconds"),
        "sample_rate": metadata.get("samplerate"),
        "channels": metadata.get("channels"),
        "format": metadata.get("format"),
        "subtype": metadata.get("subtype"),
        "integrated_lufs": levels.get("integrated_lufs"),
        "true_peak_dbtp": levels.get("true_peak_dbtp"),
        "sample_peak_dbfs": levels.get("sample_peak_dbfs"),
        "rms_dbfs": levels.get("rms_dbfs"),
        "plr_db": levels.get("plr_db"),
        "clipped_samples": levels.get("clipped_samples"),
        "near_clipping_samples": levels.get("near_clipping_samples"),
        "median_stereo_correlation": stereo.get("correlation_median"),
        "median_side_to_mid_ratio_db": mid_side.get("side_to_mid_ratio_db_median"),
        "strongest_band": _strongest_band(average_spectrum),
        "centroid_median_hz": spectral_shape.get("centroid_hz_median"),
        "rolloff_95_median_hz": spectral_shape.get("rolloff_95_hz_median"),
        "onset_density_median": onset_density.get("onset_density_median"),
        "findings_shown_count": len(shown),
        "findings_suppressed_count": findings.get("findings_suppressed_count", 0),
        "top_findings": _top_findings(shown),
    }


def write_catalog_summary_json(catalog: dict[str, Any], out_dir: str | Path) -> Path:
    out = Path(out_dir) / "catalog_summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(catalog, indent=2, sort_keys=True), encoding="utf-8")
    return out


def write_catalog_md(catalog: dict[str, Any], out_dir: str | Path) -> Path:
    out = Path(out_dir) / "catalog.md"
    tracks = _track_list(catalog)
    stats = catalog.get("statistics") if isinstance(catalog.get("statistics"), dict) else {}
    lines = [
        f"# AudioAtlas Catalog: {Path(str(catalog.get('input_folder', 'folder'))).name}",
        "",
        "Folder-level technical fingerprints, not rankings.",
        "",
        (
            "This catalog summarizes measurements across a folder of tracks. It shows "
            "ranges, medians, and technical fingerprints. It does not rank tracks or "
            "judge quality."
        ),
        "",
        "## Folder summary",
        "",
        f"- Track count: {catalog.get('track_count', 0)}",
        f"- Input folder: {catalog.get('input_folder', '')}",
        f"- Output folder: {catalog.get('output_folder', '')}",
        "",
        "## Tracks",
        "",
        (
            "| Filename | Duration | LUFS | True peak | PLR | Median correlation | "
            "Side/mid | Strongest band | Findings | Report |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---|---:|---|",
    ]
    for track in tracks:
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(track.get("filename")),
                    _duration(track.get("duration_seconds")),
                    _fmt(track.get("integrated_lufs")),
                    _fmt(track.get("true_peak_dbtp")),
                    _fmt(track.get("plr_db")),
                    _fmt(track.get("median_stereo_correlation")),
                    _fmt(track.get("median_side_to_mid_ratio_db")),
                    _md_cell(track.get("strongest_band")),
                    _fmt(track.get("findings_shown_count"), digits=0),
                    f"[report.html]({_md_cell(track.get('report_path'))})",
                ]
            )
            + " |"
        )

    lines.extend(["", "## Metric distribution summary", ""])
    for key in CATALOG_METRICS:
        metric_stats = stats.get(key) if isinstance(stats, dict) else None
        if isinstance(metric_stats, dict):
            lines.append(
                f"- {METRIC_LABELS[key]}: folder range {_fmt(metric_stats.get('min'))} to "
                f"{_fmt(metric_stats.get('max'))}, folder median "
                f"{_fmt(metric_stats.get('median'))}; missing "
                f"{_fmt(metric_stats.get('missing_count'), digits=0)}."
            )

    skipped = catalog.get("skipped_files")
    if isinstance(skipped, list) and skipped:
        lines.extend(["", "## Skipped files", ""])
        for item in skipped:
            if isinstance(item, dict):
                lines.append(f"- {_md_cell(item.get('filename'))}: {_md_cell(item.get('reason'))}")

    lines.extend(
        [
            "",
            "## Context",
            "",
            (
                "Folder medians and ranges are descriptive. Values near folder edges are "
                "technical fingerprints, not problems. Relative dB plots inside individual "
                "track reports are normalized within each track and are not calibrated dBFS."
            ),
            "",
        ]
    )
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def write_catalog_html(catalog: dict[str, Any], out_dir: str | Path) -> Path:
    out = Path(out_dir) / "catalog.html"
    folder_name = Path(str(catalog.get("input_folder", "folder"))).name
    stats = catalog.get("statistics") if isinstance(catalog.get("statistics"), dict) else {}
    lines = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f"<title>AudioAtlas Catalog - {_h(folder_name)}</title>",
        "<style>",
        _css(),
        "</style>",
        "</head>",
        "<body>",
        '<div class="container">',
        "<header>",
        f"<h1>{_h(folder_name)}</h1>",
        '<div class="subtitle">Folder-level technical fingerprints, not rankings.</div>',
        '<div class="meta-chips">',
        _chip("Tracks", catalog.get("track_count", 0)),
        _chip("Input", catalog.get("input_folder", "")),
        "</div>",
        "</header>",
        '<section class="how-to-read">',
        "<strong>How to read this catalog</strong>",
        (
            "<p>This catalog summarizes measurements across a folder of tracks. It shows "
            "ranges, medians, and technical fingerprints. It does not rank tracks or "
            "judge quality.</p>"
        ),
        "</section>",
        "<section>",
        "<h2>Summary</h2>",
        '<div class="metrics-grid">',
        _metric_card("Track count", catalog.get("track_count"), ""),
        _stat_card(stats, "integrated_lufs", "Folder median LUFS"),
        _stat_card(stats, "plr_db", "Folder median PLR"),
        _stat_card(stats, "true_peak_dbtp", "Folder median true peak"),
        _stat_card(stats, "median_stereo_correlation", "Folder median stereo correlation"),
        _stat_card(stats, "median_side_to_mid_ratio_db", "Folder median side/mid ratio"),
        _metric_card("Most common strongest band", _most_common_strongest_band(catalog), ""),
        "</div>",
        "</section>",
        _track_table(catalog),
        _metric_distributions(catalog),
        _fingerprint_cards(catalog),
        _context_section(),
        "</div>",
        "</body>",
        "</html>",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def _strongest_band(average_spectrum: dict[str, Any]) -> Any:
    value = average_spectrum.get("strongest_band")
    if isinstance(value, dict):
        return value.get("name") or value.get("band")
    if isinstance(value, str):
        return value
    bands = average_spectrum.get("band_energies")
    if isinstance(bands, dict):
        best_name = None
        best_value = None
        for name, item in bands.items():
            candidate = item.get("relative_db") if isinstance(item, dict) else item
            if (
                isinstance(candidate, (int, float))
                and not isinstance(candidate, bool)
                and (best_value is None or candidate > best_value)
            ):
                best_name = name
                best_value = candidate
        return best_name
    return None


def _top_findings(findings: list[Any]) -> list[dict[str, Any]]:
    out = []
    for item in findings[:3]:
        if isinstance(item, dict):
            out.append({"title": item.get("title"), "category": item.get("category")})
    return out


def _track_list(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    tracks = catalog.get("tracks")
    return [track for track in tracks if isinstance(track, dict)] if isinstance(tracks, list) else []


def _fmt(value: Any, *, digits: int = 3) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _duration(value: Any) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return mmss(float(value))
    return "—"


def _md_cell(value: Any) -> str:
    return str(value).replace("|", "\\|") if value is not None else "—"


def _h(value: Any) -> str:
    return escape(str(value), quote=True)


def _chip(label: str, value: Any) -> str:
    return f'<div class="chip"><strong>{_h(label)}</strong> {_h(value)}</div>'


def _metric_card(label: str, value: Any, unit: str) -> str:
    unit_html = f'<div class="metric-note">{_h(unit)}</div>' if unit else ""
    return (
        '<div class="metric-card">'
        f'<div class="metric-value">{_h(_fmt(value))}</div>'
        f'<div class="metric-label">{_h(label)}</div>'
        f"{unit_html}</div>"
    )


def _stat_card(stats: dict[str, Any], key: str, label: str) -> str:
    metric_stats = stats.get(key) if isinstance(stats, dict) else None
    value = metric_stats.get("median") if isinstance(metric_stats, dict) else None
    return _metric_card(label, value, METRIC_UNITS.get(key, ""))


def _most_common_strongest_band(catalog: dict[str, Any]) -> str:
    counts: dict[str, int] = {}
    for track in _track_list(catalog):
        value = track.get("strongest_band")
        if isinstance(value, str) and value:
            counts[value] = counts.get(value, 0) + 1
    if not counts:
        return "—"
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _track_table(catalog: dict[str, Any]) -> str:
    lines = [
        '<section id="tracks">',
        "<h2>Tracks</h2>",
        '<div class="table-wrap">',
        '<table class="track-table">',
        "<thead><tr>",
    ]
    headers = [
        "Filename",
        "Duration",
        "LUFS",
        "True peak",
        "PLR",
        "Median correlation",
        "Side/mid",
        "Strongest band",
        "Findings",
        "Report",
    ]
    for header in headers:
        lines.append(f"<th>{_h(header)}</th>")
    lines.append("</tr></thead><tbody>")
    for track in _track_list(catalog):
        lines.append("<tr>")
        cells = [
            _h(track.get("filename", "")),
            _duration(track.get("duration_seconds")),
            _fmt(track.get("integrated_lufs")),
            _fmt(track.get("true_peak_dbtp")),
            _fmt(track.get("plr_db")),
            _fmt(track.get("median_stereo_correlation")),
            _fmt(track.get("median_side_to_mid_ratio_db")),
            _h(track.get("strongest_band", "—")),
            _fmt(track.get("findings_shown_count"), digits=0),
        ]
        for cell in cells:
            lines.append(f"<td>{cell}</td>")
        report_path = track.get("report_path", "")
        lines.append(f'<td><a href="{_h(report_path)}">report.html</a></td>')
        lines.append("</tr>")
    lines.extend(["</tbody></table>", "</div>", "</section>"])
    return "\n".join(lines)


def _metric_distributions(catalog: dict[str, Any]) -> str:
    stats = catalog.get("statistics") if isinstance(catalog.get("statistics"), dict) else {}
    lines = [
        '<section id="distributions">',
        "<h2>Metric Distributions</h2>",
        '<div class="distribution-grid">',
    ]
    for key in CATALOG_METRICS:
        metric_stats = stats.get(key) if isinstance(stats, dict) else None
        if not isinstance(metric_stats, dict):
            continue
        lines.append('<article class="distribution-card">')
        lines.append(f"<h3>{_h(METRIC_LABELS[key])}</h3>")
        lines.append(
            '<div class="range-row">'
            f"<span>Min {_h(_fmt(metric_stats.get('min')))}</span>"
            f"<span>Median {_h(_fmt(metric_stats.get('median')))}</span>"
            f"<span>Max {_h(_fmt(metric_stats.get('max')))}</span>"
            "</div>"
        )
        lines.append('<div class="range-bar"><span></span></div>')
        lines.append(
            f'<p class="metric-note">{_h(_fmt(metric_stats.get("count"), digits=0))} measured; '
            f'{_h(_fmt(metric_stats.get("missing_count"), digits=0))} missing.</p>'
        )
        lines.append("</article>")
    lines.extend(["</div>", "</section>"])
    return "\n".join(lines)


def _fingerprint_cards(catalog: dict[str, Any]) -> str:
    lines = [
        '<section id="fingerprints">',
        "<h2>Per-track fingerprints</h2>",
        '<div class="fingerprint-grid">',
    ]
    for track in _track_list(catalog):
        lines.append('<article class="fingerprint-card">')
        lines.append(f"<h3>{_h(track.get('filename', 'track'))}</h3>")
        lines.append(
            "<p>"
            f"LUFS {_h(_fmt(track.get('integrated_lufs')))} · "
            f"PLR {_h(_fmt(track.get('plr_db')))} · "
            f"True peak {_h(_fmt(track.get('true_peak_dbtp')))}"
            "</p>"
        )
        lines.append(
            "<p>"
            f"Correlation {_h(_fmt(track.get('median_stereo_correlation')))} · "
            f"Strongest band {_h(track.get('strongest_band', '—'))}"
            "</p>"
        )
        lines.append(f'<a href="{_h(track.get("report_path", ""))}">Open track report</a>')
        lines.append("</article>")
    lines.extend(["</div>", "</section>"])
    return "\n".join(lines)


def _context_section() -> str:
    return """
<section id="context">
<h2>Context</h2>
<div class="context-card">
<p>Folder medians and ranges are descriptive. Values near folder edges are
technical fingerprints, not problems. Relative dB plots inside individual
track reports are normalized within each track and are not calibrated dBFS.</p>
</div>
</section>
"""


def _css() -> str:
    return """
:root {
  --bg: #f5f7f8;
  --surface: #ffffff;
  --surface-muted: #f8fafc;
  --text: #1f2937;
  --text-muted: #4b5563;
  --border: #dfe5eb;
  --accent: #0f766e;
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
.container { max-width: 1180px; margin: 0 auto; padding: 32px 18px 84px; }
header { margin-bottom: 24px; padding: 22px 0 6px; }
h1 { font-size: 32px; font-weight: 680; margin: 0 0 6px; line-height: 1.15; }
h2 { font-size: 20px; font-weight: 680; margin: 42px 0 12px; padding-bottom: 8px; border-bottom: 1px solid var(--border); }
h3 { margin: 0; }
.subtitle { font-size: 14.5px; color: var(--text-muted); margin-bottom: 16px; }
.meta-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
.chip { display: inline-flex; gap: 6px; background: #eef2f5; border: 1px solid var(--border); border-radius: 999px; padding: 5px 12px; font-size: 12.5px; color: var(--text-muted); }
.chip strong { color: var(--text); font-weight: 550; }
.how-to-read { background: #f1f5f9; border: 1px solid #d7e0ea; border-left: 4px solid #94a3b8; padding: 16px 18px; border-radius: 8px; font-size: 14px; color: #334155; }
.how-to-read strong { display: block; margin-bottom: 4px; color: var(--text); }
.how-to-read p { margin: 4px 0; }
.metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(168px, 1fr)); gap: 12px; }
.metric-card, .distribution-card, .fingerprint-card, .context-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; box-shadow: var(--shadow-card); }
.metric-card { min-height: 116px; padding: 18px 16px 16px; display: flex; flex-direction: column; justify-content: space-between; }
.metric-value { font-size: 24px; font-weight: 700; line-height: 1.05; margin-bottom: 8px; color: #111827; }
.metric-label { font-size: 12.5px; color: var(--text-muted); font-weight: 560; }
.metric-note { font-size: 12px; color: #64748b; margin: 8px 0 0; }
.table-wrap { overflow-x: auto; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; box-shadow: var(--shadow-card); }
.track-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.track-table th, .track-table td { padding: 9px 10px; border-bottom: 1px solid #edf1f5; text-align: left; white-space: nowrap; }
.track-table th { color: #334155; background: var(--surface-muted); font-weight: 650; }
.track-table a, .fingerprint-card a { color: var(--accent); font-weight: 600; text-decoration: none; }
.track-table a:hover, .fingerprint-card a:hover { text-decoration: underline; }
.distribution-grid, .fingerprint-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }
.distribution-card, .fingerprint-card, .context-card { padding: 16px; }
.distribution-card h3, .fingerprint-card h3 { font-size: 15px; margin-bottom: 8px; color: #1e293b; }
.range-row { display: flex; justify-content: space-between; gap: 10px; color: var(--text-muted); font-size: 12.5px; }
.range-bar { height: 8px; background: #e2e8f0; border-radius: 999px; overflow: hidden; margin-top: 12px; }
.range-bar span { display: block; width: 100%; height: 100%; background: linear-gradient(90deg, #99f6e4, #94a3b8); }
.fingerprint-card p, .context-card p { margin: 6px 0; color: var(--text-muted); }
@media (max-width: 520px) {
  .container { padding: 20px 12px 56px; }
  h1 { font-size: 26px; }
  h2 { font-size: 18px; margin-top: 34px; }
}
"""
