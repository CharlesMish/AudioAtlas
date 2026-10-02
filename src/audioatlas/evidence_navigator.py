"""Static navigation of existing range labels, not a measurement or detector."""

from __future__ import annotations

import math
from collections import defaultdict
from html import escape

from audioatlas.range_index import RangeIndex, reference_text
from audioatlas.range_index_report import (
    _graphs,
    clock,
    family_name,
    navigation_step,
)
from audioatlas.range_navigation import FAMILIES, active_buckets, family_key, family_rows
from audioatlas.references import REFERENCES

LEDGER_HTML = "evidence_ranges.html"
LEDGER_MD = "evidence_ranges.md"
CSS = """
#evidence-index .nav-lane { margin: 10px 0; padding: 8px 12px;
  background: var(--surface); border: 1px solid var(--border); border-radius: 6px; }
#evidence-index .nav-label { display: flex; flex-wrap: wrap; gap: 6px 18px;
  align-items: baseline; justify-content: space-between; }
#evidence-index .nav-label a { font-size: .9rem; }
#evidence-index .nav-scroll { overflow-x: auto; }
#evidence-index .nav-scale { min-width: 720px; }
#evidence-index svg { width: 100%; height: 12px; display: block; margin: 7px 0; }
#evidence-index .nav-mark { fill: var(--accent); }
#evidence-index .nav-axis { display: flex; justify-content: space-between;
  color: var(--text-muted); font-variant-numeric: tabular-nums; font-size: .8rem; }
#evidence-index .nav-meaning { margin: 6px 0 0; box-shadow: none; }
#evidence-index .nav-meaning summary { padding: 4px 6px; }
#evidence-index .nav-meaning p { padding: 0 8px; }
#evidence-index a:focus-visible { outline: 2px solid var(--text); outline-offset: 2px; }
@media (max-width: 600px) {
  #evidence-index .nav-lane { padding: 8px; }
}
"""


def extent(index: RangeIndex, summary: dict) -> float:
    """Include legacy end labels even if one hop extends beyond decoded duration."""
    levels = summary.get("levels") or {}
    duration = levels.get("duration_seconds", 0) if isinstance(levels, dict) else 0
    if not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration < 0:
        duration = 0
    return max(float(duration), max((r.end for r in index.rows), default=0), 1e-9)


def lanes(index: RangeIndex):
    """Navigation taxonomy only; never claim statistical independence."""
    groups = defaultdict(list)
    for i, row in enumerate(index.rows):
        for origin in row.origins:
            source = origin.source
            if source.family == "band_power":
                band = source.key.split(".bands.")[1].split(".")[0]
                key = (2, band)
                label = "Spectral bands / " + band.replace("_", " ")
            elif source.family in {"stereo", "mid_side"}:
                key = (3, source.family)
                label = "Stereo / " + ("correlation" if source.family == "stereo" else "mid/side")
            else:
                order = {"peaks": 0, "spectral_shape": 1, "onset": 4, "finding": 5}
                key = (order[source.family], "")
                label = family_name(source)
            groups[key].append((label, i, row, origin))
    band_order = {
        name: i
        for i, name in enumerate(("sub", "bass", "low_mid", "mid", "presence", "high", "air"))
    }
    return [groups[k] for k in sorted(groups, key=lambda k: (k[0], band_order.get(k[1], 99), k[1]))]


def _geometry_html(index: RangeIndex, summary: dict, plot_files: list[str]) -> str:
    graph_map = _graphs(plot_files)
    end = extent(index, summary)
    ledger = LEDGER_HTML
    source_ids = {
        key: f"nav-reference-{i}"
        for i, key in enumerate(sorted({o.source.key for r in index.rows for o in r.origins}))
    }
    lines = [
        '<section id="evidence-geometry"><h3>Exact original intervals</h3>',
        "<p>Each mark uses its original start and end, not bucket boundaries. "
        "Short intervals may be subpixel. Marks are pointer shortcuts, not additional tab stops; "
        "use the presence table and ledger for keyboard navigation and exact text.</p>",
    ]
    seen_families = set()
    if not index.rows:
        lines.append("<p>No existing time ranges are available in this report.</p>")
    for entries in lanes(index):
        label = entries[0][0]
        family = family_key(entries[0][3].source)
        family_anchor = f' id="nav-family-{family}"' if family not in seen_families else ""
        seen_families.add(family)
        sources = {o.source.key: o for _, _, _, o in entries}
        available = sorted({o.source.graph for o in sources.values()} & graph_map.keys())
        graph_links = (
            " · ".join(
                f'<a href="#plot-{escape(k)}">{escape(graph_map[k][1])}</a>' for k in available
            )
            or '<a href="#findings">Finding context</a>'
        )
        lines.extend(
            [
                f'<div class="nav-lane"{family_anchor}>',
                f'<div class="nav-label"><strong>{escape(label)}</strong><span>{graph_links}</span></div>',
                '<div class="nav-scroll" tabindex="0" role="group" aria-label="Scrollable time lane">',
                '<div class="nav-scale">',
                f'<div class="nav-axis"><span>{clock(0)}</span><span>{clock(end / 2)}</span>'
                f"<span>{clock(end)}</span></div>",
                f'<svg viewBox="0 0 {end!r} 10" preserveAspectRatio="none" role="group" '
                f'aria-label="{escape(label)}: original range labels">',
            ]
        )
        for _, row_id, row, origin in entries:
            source = origin.source
            text = f"{label}; {source.label}; {clock(row.start)}–{clock(row.end)}"
            lines.append(
                f'<a href="{ledger}#evidence-range-{row_id}" tabindex="-1" '
                f'aria-label="{escape(text)}" aria-describedby="{source_ids[source.key]}">'
                f'<title>{escape(text)}</title><rect class="nav-mark" '
                f'x="{row.start!r}" y="0" width="{row.end - row.start!r}" height="10" '
                f'data-start="{row.start!r}" data-end="{row.end!r}" '
                f'data-source="{escape(source.key)}" /></a>'
            )
        lines.extend(
            [
                "</svg></div></div>",
                '<details class="nav-meaning"><summary>Meaning &amp; limits</summary>',
            ]
        )
        for key, origin in sorted(sources.items()):
            source = origin.source
            reference = REFERENCES.get(source.reference)
            identity = (
                reference.identity.replace("_", " ") if reference else "existing finding context"
            )
            lines.append(
                f'<p id="{source_ids[key]}"><strong>{escape(source.label)}</strong>: '
                f"Reference: {escape(identity)}. {escape(reference_text(source))} {escape(source.support)} "
                "The line uses original labels, not the integration footprint.</p>"
            )
        lines.append("</details></div>")
    lines.append("</section>")
    return "\n".join(lines)


def _matrix_html(index: RangeIndex, summary: dict) -> str:
    windows = active_buckets(index, extent(index, summary), navigation_step(extent(index, summary)))
    lines = [
        '<section id="evidence-presence"><h3>Evidence by time window</h3>',
        '<p id="presence-boundary">Present means at least one original range label from that family '
        "overlaps the window, including ranges that began earlier. It does not encode count, "
        "strength, importance, corroboration or simultaneous events. Windows are navigation, not "
        "detected sections. An empty cell does not establish silence or that a measurement was computed.</p>",
        "<p>Times are relative to the analyzed audio or selected range. Source integration support "
        "may extend beyond labels; it is not used to mark cells.</p>",
        '<div class="matrix-scroll" tabindex="0" role="region" aria-label="Scrollable evidence presence table">',
        '<table class="presence-table" aria-describedby="presence-boundary"><caption>Existing evidence by time window and family — columns are navigation windows, not a proportional time axis</caption>',
        '<thead><tr><th scope="col">Measurement family</th>',
    ]
    for bucket in windows:
        lines.append(f'<th scope="col">{clock(bucket.start)}–{clock(bucket.end)}</th>')
    lines.append("</tr></thead><tbody>")
    for key, name in FAMILIES:
        present = any(family_rows(index, bucket.active, key) for bucket in windows)
        label = f'<a href="#nav-family-{key}">{escape(name)}</a>' if present else escape(name)
        lines.append(f'<tr><th scope="row">{label}</th>')
        for bucket in windows:
            ids = family_rows(index, bucket.active, key)
            label = f"{name}; {clock(bucket.start)}–{clock(bucket.end)}"
            if ids:
                lines.append(
                    f'<td><a class="presence-link" href="{LEDGER_HTML}#evidence-window-{bucket.start}-{key}" '
                    f'aria-label="{escape(label)}: original range labels overlap" '
                    'aria-describedby="presence-boundary">Present</a></td>'
                )
            else:
                lines.append(
                    f'<td><span aria-label="{escape(label)}: no indexed label overlap">—</span></td>'
                )
        lines.append("</tr>")
    return "\n".join(lines + ["</tbody></table></div></section>"])


def navigator_html(
    index: RangeIndex, summary: dict, plot_files: list[str], *, companion: bool = True
) -> str:
    if not companion:
        raise ValueError("The companion-ledger architecture is required")
    return "\n".join(
        [
            '<section id="evidence-index"><h2>Evidence navigator</h2>',
            f'<p><a href="{LEDGER_HTML}#evidence-ledger">Complete evidence ledger</a> · '
            '<a href="#evidence-geometry">Exact original intervals</a> · '
            '<a href="#plots">Measurement plots</a></p>',
            _matrix_html(index, summary),
            _geometry_html(index, summary, plot_files),
            "</section>",
        ]
    )


def navigator_markdown(
    index: RangeIndex, summary: dict, plot_files: list[str], *, companion: bool = True
) -> str:
    if not companion:
        raise ValueError("The companion-ledger architecture is required")
    graph_map = _graphs(plot_files)
    step = navigation_step(extent(index, summary))
    ledger_html = LEDGER_HTML if companion else "report.html"
    ledger_md = LEDGER_MD if companion else "#evidence-range-index"
    lines = [
        "## Evidence navigator",
        "",
        "Active means an original range label overlaps this navigation window, including ranges "
        "that began earlier. Presence does not encode strength, importance, corroboration or "
        "simultaneity. Empty cells do not establish silence. Times remain slice-relative; "
        "integration footprints are not new evidence intervals.",
        "",
        f"[All original ranges]({ledger_md}) · [Time × family table](report.html#evidence-presence) · "
        "[Exact original interval geometry](report.html#evidence-geometry)",
        "",
        "| Navigation window | Families with existing range labels |",
        "|---|---|",
    ]
    for bucket in active_buckets(index, extent(index, summary), step):
        cells = []
        for ids in [bucket.active]:
            names = [
                f"[{name}]({ledger_html}#evidence-window-{bucket.start}-{key})"
                for key, name in FAMILIES
                if family_rows(index, ids, key)
            ]
            cells.append("; ".join(names) or "None indexed")
        lines.append(f"| {clock(bucket.start)}–{clock(bucket.end)} | " + " | ".join(cells) + " |")
    lines.extend(["", "| Measurement | Inspect |", "|---|---|"])
    for entries in lanes(index):
        sources = {o.source.graph for _, _, _, o in entries}
        links = [
            f"[{graph_map[k][1]}]({graph_map[k][0]})" for k in sorted(sources & graph_map.keys())
        ]
        lines.append(
            f"| {entries[0][0]} | {'; '.join(links) or 'Finding context in this report'} |"
        )
    lines.extend(
        [
            "",
            "Reference and support notes accompany each family in the static navigator "
            "and the exhaustive ledger. No counts are used to rank groups.",
            "",
        ]
    )
    return "\n".join(lines)


CSS += """
#evidence-index .matrix-scroll { overflow-x: auto; }
#evidence-index .presence-table { border-collapse: collapse; width: 100%; background: var(--surface); }
#evidence-index .presence-table caption { text-align: left; margin: 8px 0; }
#evidence-index .presence-table th, #evidence-index .presence-table td {
  border: 1px solid var(--border); padding: 9px; text-align: center; }
#evidence-index .presence-table th[scope=row] { text-align: left; min-width: 8rem; }
#evidence-index .presence-table th[scope=col] { min-width: 7.5rem; }
#evidence-index .presence-link { display: block; padding: 5px; color: var(--accent); }
#evidence-index details p { padding: 0 12px; }
"""
