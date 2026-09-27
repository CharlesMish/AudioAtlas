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
    time_groups,
)
from audioatlas.references import REFERENCES

LEDGER_HTML = "evidence_ranges.html"
LEDGER_MD = "evidence_ranges.md"
INTRO = (
    "Locate existing range labels by measurement, then inspect the associated graph. "
    "Each mark is an original interval, not a new detection. Overlap does not mean "
    "importance, independence, simultaneity or a shared cause. Frame support can extend "
    "beyond the drawn labels."
)
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
#evidence-index .nav-groups { display: grid; grid-template-columns: repeat(auto-fit,minmax(220px,1fr));
  gap: 6px; padding: 0; list-style: none; }
#evidence-index .nav-groups a { display: block; padding: 7px; border: 1px solid var(--border); }
#evidence-index .nav-groups span { display: block; color: var(--text-muted); font-size: .88rem; }
#evidence-index a:focus-visible { outline: 2px solid var(--text); outline-offset: 2px; }
@media (max-width: 600px) {
  #evidence-index .nav-lane { padding: 8px; }
  #evidence-index .nav-groups { grid-template-columns: minmax(0,1fr); }
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


def navigator_html(
    index: RangeIndex, summary: dict, plot_files: list[str], *, companion=True
) -> str:
    graph_map = _graphs(plot_files)
    end = extent(index, summary)
    step = navigation_step(end)
    ledger = LEDGER_HTML if companion else ""
    source_ids = {
        key: f"nav-reference-{i}"
        for i, key in enumerate(sorted({o.source.key for r in index.rows for o in r.origins}))
    }
    lines = [
        '<section id="evidence-index"><h2>Evidence navigator</h2>',
        f"<p>{escape(INTRO)}</p>",
        "<p>Times are relative to the analyzed audio, including a selected range. "
        "Short intervals may be subpixel at this scale. Use the chronological ledger for exact "
        "times and keyboard navigation; marks are pointer shortcuts and do not add tab stops.</p>",
        f'<p><a href="{ledger}#evidence-ledger">Browse all original ranges</a> · '
        '<a href="#plots">Go to measurement plots</a></p>',
    ]
    if not index.rows:
        lines.append("<p>No existing time ranges are available in this report.</p>")
    for entries in lanes(index):
        label = entries[0][0]
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
                '<div class="nav-lane">',
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
                f'data-start="{row.start!r}" data-end="{row.end!r}" /></a>'
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
    lines.extend(
        [
            "<h3>Browse by start time</h3><p>Fixed navigation intervals, not detected song sections. "
            "Names identify families with ranges starting here; longer ranges may begin earlier.</p>",
            '<ul class="nav-groups">',
        ]
    )
    for start, rows in time_groups(index, step):
        names = sorted({family_name(o.source) for _, r in rows for o in r.origins})
        lines.append(
            f'<li><a href="{ledger}#evidence-start-{start}">Starts {clock(start)}–{clock(start + step)}'
            f"<span>{escape(' · '.join(names))}</span></a></li>"
        )
    lines.extend(["</ul></section>"])
    return "\n".join(lines)


def navigator_markdown(
    index: RangeIndex, summary: dict, plot_files: list[str], *, companion: bool = True
) -> str:
    graph_map = _graphs(plot_files)
    step = navigation_step(extent(index, summary))
    ledger_html = LEDGER_HTML if companion else "report.html"
    ledger_md = LEDGER_MD if companion else "#evidence-range-index"
    lines = [
        "## Evidence navigator",
        "",
        INTRO,
        "",
        "Times remain relative to the analyzed audio. These start-time groups are navigation, "
        "not detected sections. Longer ranges may begin earlier.",
        "",
        f"[All original ranges]({ledger_md}) · [Static lane navigator](report.html#evidence-index)",
        "",
        "| Ranges starting in | Families |",
        "|---|---|",
    ]
    for start, rows in time_groups(index, step):
        names = sorted({family_name(o.source) for _, r in rows for o in r.origins})
        lines.append(
            f"| [{clock(start)}–{clock(start + step)}]({ledger_html}#evidence-start-{start}) "
            f"| {' · '.join(names)} |"
        )
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
