from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import numpy as np

from audioatlas.analysis.bundle import AnalysisBundle
from audioatlas.config import AnalysisConfig
from audioatlas.range_index import build_range_index, index_enabled
from audioatlas.range_index_report import range_index_html, range_index_markdown


def fixture():
    return {
        "graphs": {"profile": "full"},
        "analysis_execution": {"mode": "full"},
        "peak_timeline": {
            "near_clipping_time_ranges": [{"start": 1.0, "end": 2.0, "duration": 1.0}]
        },
        "spectral_shape": {
            "centroid_elevated_time_ranges": [
                {"start": 1.0, "end": 2.0, "duration": 1.0},
                {"start": 1.001, "end": 2.0, "duration": 0.999},
                {"start": 2.0, "end": 3.0, "duration": 1.0},
            ]
        },
    }


def test_original_ranges_chronological_exact_duplicate_only_no_mutation():
    summary = fixture()
    original = deepcopy(summary)
    index = build_range_index(summary)
    assert summary == original
    assert index.original_count == 4
    assert len(index.rows) == 3
    assert [(r.start, r.end) for r in index.rows] == [(1, 2), (1.001, 2), (2, 3)]
    assert [r.overlaps for r in index.rows] == [1, 1, 0]  # touching endpoints do not overlap
    assert len(index.rows[0].origins) == 2
    assert (
        index.rows[0].origins[0].original
        == original["peak_timeline"]["near_clipping_time_ranges"][0]
    )
    assert (
        index.rows[0].origins[0].original
        is not summary["peak_timeline"]["near_clipping_time_ranges"][0]
    )


def test_aliases_and_finding_subsets_are_not_double_counted():
    ranges = [{"start": 1, "end": 2, "duration": 1}]
    bands = {"bands": {"bass": {"elevated_time_ranges": ranges}}}
    summary = {"band_power_timeline": bands, "band_energy_timeline": deepcopy(bands)}
    f = {
        "title": "Existing evidence",
        "time_ranges": ranges,
        "evidence_items": [{"label": "Original operand", "time_ranges": ranges}],
    }
    findings = {k: [deepcopy(f)] for k in ("all_findings", "findings_shown", "findings")}
    index = build_range_index(summary, findings)
    assert index.original_count == 3
    assert len(index.rows) == 1
    assert len(index.rows[0].origins) == 3
    fallback = build_range_index({"band_energy_timeline": bands}, {"findings": [f]})
    assert fallback.original_count == 3
    assert any(o.path.startswith("band_energy_timeline") for o in fallback.rows[0].origins)


def test_invalid_or_point_ranges_excluded_without_fabricating_duration():
    s = fixture()
    s["peak_timeline"]["near_clipping_time_ranges"] = [
        {"start": 0, "end": 0},
        {"start": 3, "end": 2},
        {"start": -1, "end": 2},
        {"start": float("nan"), "end": 2},
        {"start": True, "end": 2},
        {},
        None,
    ]
    index = build_range_index(s)
    assert len(index.exclusions) == 7
    assert index.original_count == 3


def test_placement_preserves_overview_standard_and_compact_custom():
    s = fixture()
    assert index_enabled(s)
    for profile in ["compact", "minimal", "standard"]:
        s["graphs"]["profile"] = profile
        assert not index_enabled(s)
    assert index_enabled(s, True)  # presentation evaluation only
    s["graphs"]["profile"] = "full"
    s["analysis_execution"]["mode"] = "compact"
    assert not index_enabled(s)
    assert not index_enabled({}, None)


def test_cached_support_does_not_recompute_or_retime(monkeypatch):
    sr = 8000
    y = np.zeros((sr * 3, 2), dtype=np.float32)
    y[sr] = 1.0
    b = AnalysisBundle(SimpleNamespace(y=y, sr=sr), AnalysisConfig(n_fft=512, hop_length=128))
    result = b.get("peaks")
    summary = {"peak_timeline": result.to_summary_dict()}
    monkeypatch.setattr(b, "get", lambda _: (_ for _ in ()).throw(AssertionError("recomputed")))
    index = build_range_index(summary, bundle=b)
    origin = index.rows[0].origins[0]
    assert origin.footprint_seconds[0] <= 1 < origin.footprint_seconds[1]
    assert origin.original == summary["peak_timeline"]["near_clipping_time_ranges"][0]
    assert set(b.computed_results) == {"peaks"}
    assert origin.footprint_seconds[1] > index.rows[0].end


def test_static_accessible_links_escaping_and_no_severity():
    s = fixture()
    s["band_power_timeline"] = {
        "bands": {"<script>alert(1)</script>": {"elevated_time_ranges": [{"start": 4, "end": 5}]}}
    }
    index = build_range_index(s)
    html = range_index_html(index, ["spectral_shape.png"])
    md = range_index_markdown(index, ["spectral_shape.png"])
    assert "<script>" not in html
    assert 'href="#plot-spectral_shape"' in html
    assert 'href="#technical"' in html
    assert "<details" in html and "<summary>" in html
    assert "1.001" in html  # original precision recoverable
    assert "severity" not in html
    assert "0:01.00" in md
    assert "(spectral_shape.png)" in md
    assert "Support" in html
    assert "source_start" not in md  # no internal support dump


def test_onset_support_is_not_presented_as_instantaneous():
    sr = 8000
    y = np.zeros((sr * 4, 2), dtype=np.float32)
    y[2 * sr : 2 * sr + 100] = 0.2
    b = AnalysisBundle(SimpleNamespace(y=y, sr=sr), AnalysisConfig(n_fft=512, hop_length=128))
    r = b.get("onset")
    index = build_range_index({"onset_density": r.to_summary_dict()}, bundle=b)
    assert index.rows
    origin = index.rows[0].origins[0]
    assert "smoothing" in origin.context
    assert "analysis wide reference" in origin.context
    assert origin.footprint_seconds[0] < index.rows[0].start


def test_empty_index_remains_readable():
    index = build_range_index({})
    assert "No existing time ranges" in range_index_html(index, [])
    assert "No existing time ranges" in range_index_markdown(index, [])


def test_display_rounding_does_not_create_sixty_second_clock():
    from audioatlas.range_index_report import clock

    assert clock(59.999) == "1:00.00"
    assert clock(60.001) == "1:00.00"
    assert clock(0) == "0:00.00"
    assert not index_enabled({"graphs": None})
    assert not index_enabled({"graphs": {"profile": "full"}, "analysis_execution": []})


def test_selected_range_keeps_slice_labels_and_source_guidance(tmp_path, monkeypatch):
    import json

    import soundfile as sf

    import audioatlas.pipeline as pipeline
    from audioatlas.graphs import GraphSelection

    sr = 16000
    y = np.zeros((5 * sr, 2), dtype=np.float32)
    y[4 * sr] = 1.0
    path = tmp_path / "selected.wav"
    sf.write(path, y, sr, subtype="FLOAT")
    captured = []
    original = pipeline.build_range_index

    def record(summary, findings, bundle):
        index = original(summary, findings, bundle)
        captured.append(index)
        return index

    monkeypatch.setattr(pipeline, "build_range_index", record)
    result = pipeline.analyze_file(
        path,
        tmp_path / "report",
        start_seconds=3,
        end_seconds=5,
        selection=GraphSelection(profile="full"),
        config=AnalysisConfig(
            n_fft=512,
            hop_length=128,
            rms_frame_length=512,
            welch_nperseg=512,
            true_peak_oversample=1,
        ),
    )
    assert len(captured) == 1  # one memoized extraction shared by both report writers
    summary = json.loads(result.summary_path.read_text())
    origins = [o for row in captured[0].rows for o in row.origins if o.source.family == "peaks"]
    assert origins
    assert [o.original for o in origins] == summary["peak_timeline"]["near_clipping_time_ranges"]
    assert all(o.original["start"] < 2 for o in origins)
    assert origins[0].footprint_seconds[0] <= 1 < origins[0].footprint_seconds[1]
    for report in [result.report_path, result.html_report_path]:
        text = report.read_text()
        assert "Evidence navigator" in text
        assert "relative to this analyzed range" in text
    assert len(result.plot_paths) == 18
