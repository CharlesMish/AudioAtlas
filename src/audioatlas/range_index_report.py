"""Static HTML/Markdown navigation for original evidence ranges."""

from __future__ import annotations

from collections import defaultdict
from html import escape

from audioatlas.graphs.registry import graph_by_filename
from audioatlas.markdown import markdown_text
from audioatlas.range_index import RangeIndex, reference_text

INTRO = (
    "Existing evidence, ordered by its original time labels. These are not ranked listening "
    "recommendations. Overlapping labels do not establish simultaneous events or a shared cause; "
    "frames and smoothing windows can extend beyond the labels."
)

CSS = """
#evidence-index { margin: 28px 0; }
#evidence-index summary { cursor: pointer; overflow-wrap: anywhere; }
#evidence-index a { color: var(--accent); }
#evidence-index .range-bucket { margin: 8px 0; padding: 10px 14px; }
#evidence-index .range-row { display: grid; grid-template-columns: 11rem minmax(0,1fr);
  gap: 10px; padding: 12px 0; border-top: 1px solid var(--border); }
#evidence-index .range-time { font-variant-numeric: tabular-nums; color: var(--text); }
#evidence-index .range-row ul { margin: 0; padding-left: 18px; }
#evidence-index .range-context { color: var(--text-muted); font-size: .88rem; }
#evidence-index .range-context p { margin: 6px 0; }
#evidence-index .range-context details { padding: 8px; margin-top: 6px; }
#evidence-index .range-row:target { outline: 2px solid var(--accent); outline-offset: 2px; }
#evidence-index .range-row, #evidence-index li { overflow-wrap: anywhere; min-width: 0; }
@media (max-width: 600px) {
  #evidence-index .range-row { grid-template-columns: minmax(0,1fr); gap: 6px; }
  #evidence-index .range-bucket { padding: 9px; }
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


def _graphs(plot_files):
    available = {}
    for filename in plot_files:
        try:
            spec = graph_by_filename(filename)
            available[spec.key] = (filename, spec.display_name)
        except KeyError:
            continue
    return available


def range_index_html(index: RangeIndex, plot_files: list[str]) -> str:
    graphs = _graphs(plot_files)
    lines = [
        '<section id="evidence-index"><h2>Evidence range index</h2>',
        f'<p class="section-intro">{escape(INTRO)}</p>',
        f"<p>{index.original_count} original ranges · {len(index.rows)} chronological rows. "
        "Only exactly equal label intervals share a row. Open a start-time group to browse.</p>",
    ]
    if index.exclusions:
        lines.append(
            f"<p>{len(index.exclusions)} records could not establish a valid interval; "
            "their source JSON is unchanged.</p>"
        )
    if not index.rows:
        lines.append("<p>No existing time ranges are available in this report.</p>")
    for bucket, rows in buckets(index):
        lines.append(
            f'<details class="range-bucket"><summary>Starts {clock(bucket * 10)}–'
            f"{clock((bucket + 1) * 10)} · {len(rows)} rows</summary>"
        )
        for i, row in rows:
            lines.append(
                f'<article class="range-row" id="evidence-range-{i}">'
                f'<div class="range-time">{clock(row.start)}–{clock(row.end)}</div><div><ul>'
            )
            for origin in row.origins:
                source = origin.source
                target = (
                    f"#plot-{source.graph}"
                    if source.graph in graphs
                    else ("#findings" if source.family == "finding" else "#technical")
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
        lines.append("</details>")
    return "\n".join(lines + ["</section>"])


def range_index_markdown(index: RangeIndex, plot_files: list[str]) -> str:
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
    # Native details are optional: a plain Markdown reader can still read every row.
    for bucket, rows in buckets(index):
        lines.extend(
            [
                "<details>",
                f"<summary>Starts {clock(bucket * 10)}–{clock((bucket + 1) * 10)} "
                f"· {len(rows)} rows</summary>",
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
        lines.extend(["", "</details>", ""])
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
