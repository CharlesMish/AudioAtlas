"""Static HTML/Markdown navigation for original evidence ranges."""

from __future__ import annotations

from collections import defaultdict
from html import escape

from audioatlas.graphs.registry import graph_by_filename
from audioatlas.markdown import markdown_text
from audioatlas.range_index import RangeIndex, reference_text
from audioatlas.range_navigation import FAMILIES, active_buckets, family_key, family_rows

INTRO = (
    "Existing evidence, ordered by its original time labels. These are not ranked listening "
    "recommendations. Overlapping labels do not establish simultaneous events or a shared cause; "
    "frames and smoothing windows can extend beyond the labels."
)

CSS = """
:is(#evidence-index, #evidence-ledger) { margin: 28px 0; }
:is(#evidence-index, #evidence-ledger) summary { cursor: pointer; overflow-wrap: anywhere; }
:is(#evidence-index, #evidence-ledger) a { color: var(--accent); }
:is(#evidence-index, #evidence-ledger) .range-bucket { margin: 8px 0; padding: 10px 14px; }
:is(#evidence-index, #evidence-ledger) .range-row { display: grid; grid-template-columns: 11rem minmax(0,1fr);
  gap: 10px; padding: 12px 0; border-top: 1px solid var(--border); }
:is(#evidence-index, #evidence-ledger) .range-time { font-variant-numeric: tabular-nums; color: var(--text); }
:is(#evidence-index, #evidence-ledger) .range-row ul { margin: 0; padding-left: 18px; }
:is(#evidence-index, #evidence-ledger) .range-context { color: var(--text-muted); font-size: .88rem; }
:is(#evidence-index, #evidence-ledger) .range-context p { margin: 6px 0; }
:is(#evidence-index, #evidence-ledger) .range-context details { padding: 8px; margin-top: 6px; }
:is(#evidence-index, #evidence-ledger) .range-row:target { outline: 2px solid var(--accent); outline-offset: 2px; }
:is(#evidence-index, #evidence-ledger) .range-row, :is(#evidence-index, #evidence-ledger) li { overflow-wrap: anywhere; min-width: 0; }
#evidence-ledger .range-heading { position: sticky; top: 0; z-index: 1;
  background: var(--surface); padding: 8px; border-bottom: 1px solid var(--border); }
#evidence-ledger .range-row, #evidence-ledger .window-family { scroll-margin-top: 6rem; }
#evidence-ledger .window-family:target { outline: 2px solid var(--accent); outline-offset: 2px; }
#evidence-ledger .window-family details { padding: 6px; }
#evidence-ledger .range-reference { overflow-wrap: anywhere; }
@media print { #evidence-ledger .range-heading { position: static; } }
@media (max-width: 600px) {
  :is(#evidence-index, #evidence-ledger) .range-row { grid-template-columns: minmax(0,1fr); gap: 6px; }
  :is(#evidence-index, #evidence-ledger) .range-bucket { padding: 9px; }
}
"""


def clock(seconds: float) -> str:
    # Display only; original floats remain unchanged in the index/source records.
    minutes, centiseconds = divmod(round(seconds * 100), 6000)
    return f"{minutes}:{centiseconds / 100:05.2f}"


def buckets(index: RangeIndex):
    groups = defaultdict(list)
    for i, row in enumerate(index.rows):
        groups[int(row.start // 10)].append((i, row))
    return groups.items()


def family_name(source) -> str:
    return {
        "peaks": "Level / peak",
        "spectral_shape": "Spectral shape",
        "band_power": "Spectral bands",
        "stereo": "Stereo",
        "mid_side": "Stereo",
        "onset": "Activity / onset",
        "finding": "Findings",
    }[source.family]


def navigation_step(duration: float) -> int:
    """A deterministic navigation scale, never a detected section boundary."""
    step = 10
    while duration > step * 12:
        step *= 2
    return step


def time_groups(index: RangeIndex, step: int):
    groups = defaultdict(list)
    for i, row in enumerate(index.rows):
        groups[int(row.start // step) * step].append((i, row))
    return groups.items()


def _graphs(plot_files):
    available = {}
    for filename in plot_files:
        try:
            spec = graph_by_filename(filename)
            available[spec.key] = (filename, spec.display_name)
        except KeyError:
            continue
    return available


def range_index_html(
    index: RangeIndex,
    plot_files: list[str],
    *,
    report_prefix: str = "",
    expanded: bool = False,
    step: int = 10,
    duration: float | None = None,
) -> str:
    graphs = _graphs(plot_files)
    lines = [
        '<section id="evidence-ledger"><h2>Evidence range index</h2>',
        f'<p class="section-intro">{escape(INTRO)}</p>',
        f"<p>{index.original_count} original ranges · {len(index.rows)} chronological rows. "
        "Only exactly equal label intervals share a record. Window context below links to original records; "
        "it does not duplicate or clip them.</p>",
    ]
    if index.exclusions:
        lines.append(
            f"<p>{len(index.exclusions)} records could not establish a valid interval; "
            "their source JSON is unchanged.</p>"
        )
    if not index.rows:
        lines.append("<p>No existing time ranges are available in this report.</p>")
    domain = duration if duration is not None else max((r.end for r in index.rows), default=0)
    for bucket in active_buckets(index, domain, step):
        start = bucket.start
        rows = [(i, index.rows[i]) for i in bucket.starting]
        heading = f"{clock(start)}–{clock(bucket.end)} · existing label context"
        lines.append(
            f'<section class="range-bucket" id="evidence-start-{start}">'
            f'<h3 class="range-heading">{heading} · '
            f'<a href="{report_prefix}#evidence-index">Navigator</a></h3>'
        )
        lines.append(
            "<p>Presence means an original label interval overlaps this window, "
            "not simultaneous source events. References below may point to records that began earlier.</p>"
        )
        for family, label in FAMILIES:
            ids = family_rows(index, bucket.active, family)
            if not ids:
                continue
            carried = family_rows(index, bucket.continuing, family)
            begun = family_rows(index, bucket.starting, family)
            state = (
                "Starts here and continues from earlier"
                if carried and begun
                else "Continues from earlier"
                if carried
                else "Starts here"
            )
            lines.append(
                f'<div class="window-family" id="evidence-window-{start}-{family}" tabindex="-1">'
                f"<h4>{escape(label)} · {state}</h4><details><summary>Show original range links</summary><ul>"
            )
            for i in ids:
                row = index.rows[i]
                labels = list(
                    dict.fromkeys(
                        o.source.label for o in row.origins if family_key(o.source) == family
                    )
                )
                state = "continues from earlier" if i in carried else "starts here"
                lines.append(
                    f'<li><a class="range-reference" href="#evidence-range-{i}">'
                    f"{escape('; '.join(labels))}: {row.start!r}–{row.end!r} s</a> "
                    f"({state}; original labels)</li>"
                )
            lines.append("</ul></details></div>")
        if not bucket.active:
            lines.append(
                "<p>No indexed label intervals overlap this window. This does not establish silence.</p>"
            )
        lines.append("<h4>Canonical records beginning in this window</h4>")
        if not rows:
            lines.append("<p>No original records begin here; use continuing references above.</p>")
        for i, row in rows:
            lines.append(
                f'<article class="range-row" id="evidence-range-{i}">'
                f'<div class="range-time">{clock(row.start)}–{clock(row.end)}</div><div><ul>'
            )
            for origin in row.origins:
                source = origin.source
                target = (
                    f"{report_prefix}#plot-{source.graph}"
                    if source.graph in graphs
                    else (
                        f"{report_prefix}#findings"
                        if source.family == "finding"
                        else f"{report_prefix}#technical"
                    )
                )
                lines.append(f'<li><a href="{escape(target)}">{escape(source.label)}</a></li>')
            lines.append('</ul><div class="range-context">')
            lines.append("<details><summary>Support, reference &amp; source records</summary>")
            if row.overlaps:
                lines.append(f"<p>Label interval overlaps {row.overlaps} other indexed rows.</p>")
            lines.append(
                f"<p>Original labels: {row.start!r}–{row.end!r} seconds from analyzed start.</p>"
            )
            for origin in row.origins:
                s = origin.source
                graph_name = (
                    graphs[s.graph][1]
                    if s.graph in graphs
                    else "Associated plot not in this report"
                )
                lines.append(
                    f"<p><strong>{escape(s.label)}</strong> · {escape(graph_name)}<br>"
                    f"{escape(s.support)} {escape(origin.context)}<br>"
                    f"{escape(reference_text(s))}</p>"
                )
                if origin.footprint_seconds:
                    a, b = origin.footprint_seconds
                    lines.append(
                        f"<p>Contributing frame-footprint envelope: {a:.6f}–{b:.6f} s. "
                        "This explains support; it is not another detected range.</p>"
                    )
                file = "findings.json" if s.family == "finding" else "summary.json"
                lines.append(
                    f'<p>Source: <a href="{file}">{file}</a> · '
                    f"<code>{escape(origin.path)}</code></p>"
                )
            lines.append("</details></div></div></article>")
        lines.append("</section>")
    return "\n".join(lines + ["</section>"])


def range_index_markdown(
    index: RangeIndex, plot_files: list[str], *, step: int = 10, duration: float | None = None
) -> str:
    graphs = _graphs(plot_files)
    lines = [
        "## Evidence range index",
        "",
        INTRO,
        "",
        f"{index.original_count} original ranges in {len(index.rows)} chronological rows. "
        "Exactly equal label intervals share a row; source evidence is retained.",
        "",
    ]
    if not index.rows:
        lines.extend(["No existing time ranges are available.", ""])
    if index.exclusions:
        lines.extend(
            [
                f"{len(index.exclusions)} records did not establish a valid interval; "
                "source JSON is unchanged.",
                "",
            ]
        )
    domain = duration if duration is not None else max((r.end for r in index.rows), default=0)
    for bucket in active_buckets(index, domain, step):
        start = bucket.start
        rows = [(i, index.rows[i]) for i in bucket.starting]
        lines.extend([f"### {clock(start)}–{clock(bucket.end)}", "", "Existing label context:", ""])
        for family, label in FAMILIES:
            if family_rows(index, bucket.active, family):
                begun = bool(family_rows(index, bucket.starting, family))
                carried = bool(family_rows(index, bucket.continuing, family))
                state = (
                    "starts here and continues from earlier"
                    if begun and carried
                    else "continues from earlier"
                    if carried
                    else "starts here"
                )
                lines.append(
                    f"- [{label} — {state}](evidence_ranges.html#evidence-window-{start}-{family})"
                )
        if not bucket.active:
            lines.append(
                "No indexed label intervals overlap this window; this does not establish silence."
            )
        lines.extend(
            [
                "",
                "Canonical records beginning here (original labels):",
                "",
                "| Original labels | Existing evidence / inspect | Overlapping rows |",
                "|---|---|---:|",
            ]
        )
        for _, row in rows:
            labels = []
            for origin in row.origins:
                label = markdown_text(origin.source.label).replace("|", "\\|")
                graph = graphs.get(origin.source.graph)
                labels.append(f"[{label}]({graph[0]})" if graph else label)
            lines.append(
                f"| {clock(row.start)}–{clock(row.end)} | {'; '.join(labels)} | {row.overlaps} |"
            )
        lines.append("")
    lines.extend(
        [
            "### Reading range support and references",
            "",
            "Times above are original label intervals, not complete source footprints. "
            "Exact boundaries remain in summary.json and findings.json.",
            "",
        ]
    )
    sources = {o.source.key: o for r in index.rows for o in r.origins}
    for key in sorted(sources):
        origin = sources[key]
        lines.append(
            f"- **{markdown_text(origin.source.label)}:** "
            f"{markdown_text(origin.source.support)} {markdown_text(origin.context)} "
            f"{markdown_text(reference_text(origin.source))}"
        )
    return "\n".join(lines) + "\n"
