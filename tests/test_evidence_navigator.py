from __future__ import annotations

import json
from collections import Counter
from html.parser import HTMLParser

import numpy as np
import pytest
import soundfile as sf

from audioatlas.config import AnalysisConfig
from audioatlas.errors import OutputOwnershipError
from audioatlas.evidence_navigator import CSS, extent, navigator_html
from audioatlas.graphs import GraphSelection
from audioatlas.output import EVIDENCE_REPORT_FILENAMES, OUTPUT_MARKER_FILENAME
from audioatlas.pipeline import analyze_file
from audioatlas.range_index import build_range_index
from audioatlas.range_index_report import navigation_step, range_index_html, time_groups


class DOM(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.tags = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def summary():
    return {
        "levels": {"duration_seconds": 30},
        "peak_timeline": {"near_clipping_time_ranges": [{"start": 1.0, "end": 2.0}]},
        "spectral_shape": {"centroid_elevated_time_ranges": [{"start": 1.0, "end": 2.0}]},
        "band_power_timeline": {
            "bands": {
                "bass": {"elevated_time_ranges": [{"start": 1.001, "end": 2.0}]},
                "air": {"reduced_time_ranges": [{"start": 29.0, "end": 30.02}]},
            }
        },
    }


def test_every_mark_is_one_original_range_no_union_retime_or_intensity():
    s = summary()
    index = build_range_index(s)
    dom = DOM(navigator_html(index, s, ["peak_timeline.png", "spectral_shape.png"]))
    marks = [a for tag, a in dom.tags if tag == "rect"]
    expected = Counter((repr(r.start), repr(r.end)) for r in index.rows for _ in r.origins)
    assert Counter((a["data-start"], a["data-end"]) for a in marks) == expected
    for a in marks:
        assert float(a["x"]) == float(a["data-start"])
        assert float(a["width"]) == float(a["data-end"]) - float(a["data-start"])
        assert a["height"] == "10" and a["class"] == "nav-mark"
        assert "opacity" not in a and "fill" not in a and "style" not in a
    assert "opacity" not in CSS
    assert extent(index, s) == 30.02  # preserve legacy end beyond the decoded duration
    assert len([a for tag, a in dom.tags if tag == "svg"]) == 4  # each band retained


def test_reference_descriptions_pointer_shortcuts_and_keyboard_alternative():
    s = summary()
    index = build_range_index(s)
    text = navigator_html(index, s, [])
    dom = DOM(text)
    ids = {a["id"] for _, a in dom.tags if "id" in a}
    segments = [a for tag, a in dom.tags if tag == "a" and "aria-describedby" in a]
    assert len(segments) == index.original_count
    for a in segments:
        assert a["aria-describedby"] in ids
        assert "0:" in a["aria-label"]
        assert a["href"].startswith("evidence_ranges.html#evidence-range-")
        assert a["tabindex"] == "-1"  # no thousands-of-links keyboard trap
    assert 'href="evidence_ranges.html#evidence-ledger"' in text
    assert "within" in text and "full scale" in text
    assert "not" in text and "keyboard navigation" in text
    assert "<script" not in text
    assert "min-width: 720px" in CSS and "overflow-x: auto" in CSS
    assert "<span>Level / peak" in text  # neutral group family names
    assert "rows</" not in text  # no multiplicity-as-importance headers


@pytest.mark.parametrize("duration,expected_step", [(30, 10), (71, 10), (300, 40)])
def test_navigation_scale_is_deterministic_not_detection(duration, expected_step):
    s = summary()
    s["levels"]["duration_seconds"] = duration
    index = build_range_index(s)
    assert navigation_step(duration) == expected_step
    original = [(i, row) for i, row in enumerate(index.rows)]
    regrouped = [pair for _, rows in time_groups(index, expected_step) for pair in rows]
    assert regrouped == original


def test_expanded_ledger_targets_and_backlinks_work_without_javascript():
    index = build_range_index(summary())
    text = range_index_html(
        index, ["peak_timeline.png"], report_prefix="report.html", expanded=True
    )
    dom = DOM(text)
    ids = {a["id"] for _, a in dom.tags if "id" in a}
    assert "evidence-ledger" in ids
    assert {f"evidence-range-{i}" for i in range(len(index.rows))} <= ids
    assert 'href="report.html#plot-peak_timeline"' in text
    assert 'id="evidence-start-0"' in text
    assert '<details class="range-bucket"' not in text  # row is never hidden by closed ancestors


def test_companion_ownership_cleanup_collision_and_slice_scope(tmp_path):
    sr = 16000
    t = np.arange(sr * 4) / sr
    y = 0.2 * np.sin(2 * np.pi * 440 * t)
    path = tmp_path / "private-source.wav"
    sf.write(path, np.column_stack([y, 0.5 * y]), sr)
    out = tmp_path / "report"
    config = AnalysisConfig(
        n_fft=512, hop_length=128, rms_frame_length=512, welch_nperseg=512, true_peak_oversample=1
    )
    kwargs = dict(config=config, start_seconds=1, end_seconds=3)
    analyze_file(path, out, selection=GraphSelection(profile="full"), **kwargs)
    manifest = json.loads((out / OUTPUT_MARKER_FILENAME).read_text())
    assert set(manifest["generated_files"]) >= EVIDENCE_REPORT_FILENAMES
    for name in EVIDENCE_REPORT_FILENAMES:
        text = (out / name).read_text()
        assert str(tmp_path) not in text
        assert "relative to the analyzed audio" in text
    html = (out / "report.html").read_text()
    assert "Evidence navigator" in html
    assert 'class="range-row"' not in html
    assert "evidence_ranges.html" in html
    assert len(list(out.glob("*.png"))) == 18
    # Historical/non-Detailed outputs need no companions. Owned stale companions are removed.
    analyze_file(path, out, selection=GraphSelection(profile="standard"), **kwargs)
    assert all(not (out / name).exists() for name in EVIDENCE_REPORT_FILENAMES)
    assert "Evidence navigator" not in (out / "report.html").read_text()
    assert len(list(out.glob("*.png"))) == 14
    # An unrelated same-named file must never be claimed by the new optional allowlist.
    (out / "evidence_ranges.html").write_text("user content")
    old = (out / "report.html").read_bytes()
    with pytest.raises(OutputOwnershipError, match="unowned output file"):
        analyze_file(path, out, selection=GraphSelection(profile="full"), **kwargs)
    assert (out / "evidence_ranges.html").read_text() == "user content"
    assert (out / "report.html").read_bytes() == old


def test_detailed_project_and_section_companions_remain_owned_and_readable(tmp_path):
    from pathlib import Path

    from audioatlas.project import add_project_revision, build_project, init_project

    fixture = Path(__file__).parents[1] / "tests/fixtures/sine_1k_-6dbfs_2s.wav"
    project = tmp_path / "project"
    init_project(project, name="Evidence", graphs_profile="full", sections=[("slice", 0.5, 1.5)])
    revision = add_project_revision(project, fixture, label="First")
    paths = [project / revision["report"], project / revision["sections"][0]["report"]]
    for report in paths:
        manifest = json.loads((report / OUTPUT_MARKER_FILENAME).read_text())
        assert set(manifest["generated_files"]) >= EVIDENCE_REPORT_FILENAMES
        assert all((report / name).is_file() for name in EVIDENCE_REPORT_FILENAMES)
    build_project(project)
    assert str(tmp_path) not in (project / "project.json").read_text()
