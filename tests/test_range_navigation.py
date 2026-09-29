from __future__ import annotations

from copy import deepcopy

import pytest

from audioatlas.evidence_navigator import _matrix_html, navigator_markdown
from audioatlas.range_index import build_range_index
from audioatlas.range_index_report import range_index_html
from audioatlas.range_navigation import active_buckets, family_rows


def fixture():
    return {
        "levels": {"duration_seconds": 40},
        "peak_timeline": {"near_clipping_time_ranges": [{"start": 1.0, "end": 35.0}]},
        "spectral_shape": {
            "centroid_elevated_time_ranges": [
                {"start": 9.98, "end": 10.0},
                {"start": 10.0, "end": 10.025},
                {"start": 30.0, "end": 30.02},
            ]
        },
    }


def test_half_open_overlap_continuing_and_no_start_windows_preserve_coordinates():
    s = fixture()
    before = deepcopy(s)
    index = build_range_index(s)
    windows = active_buckets(index, 40, 10)
    assert [(w.start, w.end) for w in windows] == [(0, 10), (10, 20), (20, 30), (30, 40)]
    assert windows[1].starting == (2,)
    assert windows[1].continuing == (0,)
    assert 1 not in windows[1].active  # end exactly at boundary is excluded
    assert windows[2].starting == () and windows[2].active == (0,)
    assert windows[3].continuing == (0,)
    assert family_rows(index, windows[2].active, "level") == (0,)
    assert s == before
    assert index.rows[0].start == 1 and index.rows[0].end == 35
    assert sum(len(w.starting) for w in windows) == len(index.rows)


def test_support_footprints_never_expand_navigation_presence():
    from dataclasses import replace

    index = build_range_index(fixture())
    row = index.rows[1]
    origin = replace(row.origins[0], footprint_seconds=(0, 40))
    changed = replace(index, rows=(index.rows[0], replace(row, origins=(origin,)), *index.rows[2:]))
    assert active_buckets(index, 40, 10) == active_buckets(changed, 40, 10)


def test_matrix_presence_includes_carry_and_micro_ranges_without_multiplicity():
    s = fixture()
    index = build_range_index(s)
    text = _matrix_html(index, s)
    assert "<svg" not in text
    assert "<caption>" in text and 'scope="row"' in text and 'scope="col"' in text
    assert "evidence-window-20-level" in text
    assert "evidence-window-10-spectral_shape" in text
    assert "evidence-window-20-spectral_shape" not in text
    assert text.count('class="presence-link"') == 7
    # Another same-family range in the same bucket changes no presence cell/style.
    s["spectral_shape"]["centroid_elevated_time_ranges"].append({"start": 10.04, "end": 10.06})
    assert _matrix_html(build_range_index(s), s) == text
    assert "importance" in text and "does not establish silence" in text
    assert "0.025" not in text  # not promoted to first-level prose
    assert "<script" not in text


def test_context_references_keep_canonical_rows_singular_and_exact():
    index = build_range_index(fixture())
    text = range_index_html(
        index, [], expanded=True, step=10, duration=40, report_prefix="report.html"
    )
    assert text.count('id="evidence-range-0"') == 1
    assert text.count('href="#evidence-range-0"') == 4
    assert 'id="evidence-start-20"' in text
    assert 'id="evidence-window-20-level"' in text
    assert "Continues from earlier" in text
    assert "1.0–35.0 s" in text
    assert text.count('class="range-row"') == len(index.rows)
    assert "report.html#evidence-index" in text
    md = navigator_markdown(index, fixture(), [])
    assert "Continues from earlier" not in md
    assert "evidence-window-20-level" in md


def test_empty_bucket_and_extent_are_not_silence_or_new_ranges():
    s = fixture()
    s["levels"]["duration_seconds"] = 60
    index = build_range_index(s)
    windows = active_buckets(index, 60, 10)
    assert windows[-1].active == () and windows[-1].starting == ()
    assert "does not establish silence" in range_index_html(index, [], duration=60)
    assert index.original_count == 4
    for duration, step in [(float("inf"), 10), (40, 0), (40, -1)]:
        with pytest.raises(ValueError):
            active_buckets(index, duration, step)


def test_retired_inline_architecture_cannot_be_enabled(tmp_path):
    from audioatlas.html_report import write_report_html
    from audioatlas.report import write_report_md

    for writer in [write_report_html, write_report_md]:
        with pytest.raises(ValueError, match="companion-ledger"):
            writer({}, [], tmp_path, navigator_layout="inline")
    assert not list(tmp_path.iterdir())


def test_combined_layers_keep_long_and_micro_ranges_traceable_without_repetition():
    from html.parser import HTMLParser

    from audioatlas.evidence_navigator import navigator_html

    class DOM(HTMLParser):
        def __init__(self, text):
            super().__init__()
            self.tags = []
            self.feed(text)

        def handle_starttag(self, tag, attrs):
            self.tags.append((tag, dict(attrs)))

    s = fixture()
    s["peak_timeline"]["near_clipping_time_ranges"] = [{"start": 3.0, "end": 25.0}]
    index = build_range_index(s)
    text = navigator_html(index, s, [])
    dom = DOM(text)
    marks = [a for t, a in dom.tags if t == "rect"]
    assert len(marks) == index.original_count
    long = [a for a in marks if a["data-start"] == "3.0"]
    assert len(long) == 1 and long[0]["data-end"] == "25.0" and long[0]["width"] == "22.0"
    assert all(a["data-source"] for a in marks)
    presence = [a["href"] for t, a in dom.tags if a.get("class") == "presence-link"]
    assert all(
        f"evidence_ranges.html#evidence-window-{start}-level" in presence for start in [0, 10, 20]
    )
    assert "evidence_ranges.html#evidence-window-30-level" not in presence
    micro = next(a for a in marks if a["data-start"] == "10.0")
    assert float(micro["width"]) == 10.025 - 10.0  # never lengthened or snapped
    assert "evidence_ranges.html#evidence-window-10-spectral_shape" in presence
    assert text.index('id="evidence-presence"') < text.index('id="evidence-geometry"')
    assert (
        "Active:" not in text and "Starts here" not in text and "Continues from earlier" not in text
    )
    assert 'class="range-row"' not in text
    ids = [a["id"] for _, a in dom.tags if "id" in a]
    assert len(ids) == len(set(ids))
    ledger = range_index_html(index, [], report_prefix="report.html", duration=40)
    assert ledger.count('id="evidence-range-0"') == 1
    assert ledger.count('href="#evidence-range-0"') == 3
    assert all(
        a.get("tabindex") == "-1"
        for t, a in dom.tags
        if t == "a" and a.get("href", "").startswith("evidence_ranges.html#evidence-range-")
    )
