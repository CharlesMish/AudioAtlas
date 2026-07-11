from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

import audioatlas.pipeline as pipeline_module
from audioatlas.batch import analyze_folder
from audioatlas.config import AnalysisConfig
from audioatlas.errors import AudioLoadError
from audioatlas.graphs import all_graphs
from audioatlas.graphs.selection import GraphSelection
from audioatlas.output import OUTPUT_MARKER_FILENAME, SINGLE_REPORT_FILENAMES
from audioatlas.pipeline import analyze_file
from audioatlas.release import (
    FINDING_RULESET_VERSION,
    FINDINGS_SCHEMA_VERSION,
    SUMMARY_SCHEMA_VERSION,
)


def _small_config() -> AnalysisConfig:
    return AnalysisConfig(
        n_fft=512,
        hop_length=128,
        rms_frame_length=512,
        welch_nperseg=512,
        true_peak_oversample=1,
    )


def _write_short_sine(path: Path, sr: int) -> None:
    t = np.arange(sr // 4, dtype=np.float64) / sr
    y = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sf.write(path, y, sr)


def test_pipeline_writes_expected_outputs(tmp_path: Path, sr: int):
    path = tmp_path / "song.wav"
    _write_short_sine(path, sr)

    result = analyze_file(path, tmp_path / "report", config=_small_config())

    assert result.summary_path.exists()
    assert result.findings_path.exists()
    assert result.report_path.exists()
    assert result.html_report_path.exists()
    assert result.html_report_path.name == "report.html"
    assert (result.out_dir / OUTPUT_MARKER_FILENAME).exists()
    for plot_path in result.plot_paths:
        assert plot_path.exists()

    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
    findings = json.loads(result.findings_path.read_text(encoding="utf-8"))
    html = result.html_report_path.read_text(encoding="utf-8")

    assert summary["schema_version"] == SUMMARY_SCHEMA_VERSION
    assert summary["metadata"]["path"] == "song.wav"
    assert summary["metadata"]["path_kind"] == "basename"
    assert summary["metadata"]["local_paths_included"] is False
    assert summary["source_identity"] == {"kind": "none", "track_id_sha256": None}
    provenance = summary["analysis_provenance"]
    assert provenance["audioatlas_version"] == "0.2.0a4"
    assert provenance["summary_schema_version"] == SUMMARY_SCHEMA_VERSION
    assert len(provenance["analysis_config_sha256"]) == 64
    assert len(provenance["measurement_code_sha256"]) == 64
    assert len(provenance["compatible_analysis_sha256"]) == 64
    assert len(provenance["exact_environment_sha256"]) == 64
    assert str(tmp_path) not in json.dumps(summary)
    assert "levels" in summary
    assert "peak_timeline" in summary
    assert summary["average_spectrum"]["band_measurement"] == (
        "relative_mean_power_per_fft_bin"
    )
    assert "band_mean_power" in summary["average_spectrum"]
    assert "band_energies" in summary["average_spectrum"]
    assert "spectral_shape" in summary
    assert "band_power_timeline" in summary
    assert "band_energy_timeline" in summary
    assert summary["band_energy_timeline"] == summary["band_power_timeline"]
    assert "onset_density" in summary
    assert "chroma_cqt" in summary
    assert "short_term_lufs" in summary
    assert "stereo_correlation" in summary
    assert "mid_side_energy" in summary
    assert "crest_factor_timeline" in summary

    selected_graphs = GraphSelection().resolve(all_graphs())
    expected_plots = [graph.filename for graph in selected_graphs]
    assert summary["plots"] == expected_plots
    assert summary["graphs"] == {
        "profile": "standard",
        "selected": [graph.key for graph in selected_graphs],
        "available": [graph.key for graph in all_graphs()],
        "selected_filenames": expected_plots,
    }
    assert len(summary["plots"]) == 14

    assert findings["schema_version"] == FINDINGS_SCHEMA_VERSION
    assert findings["ruleset_version"] == FINDING_RULESET_VERSION
    assert "findings" in findings
    assert findings["count"] == len(result.findings["findings"])
    all_titles = [item["title"] for item in findings["all_findings"]]
    assert len(all_titles) <= 4
    assert not any("band energy" in title.lower() for title in all_titles)

    assert "Findings" in html
    assert "Key metrics" in html
    assert "waveform_rms.png" in html
    image_srcs = re.findall(r'<img src="([^"]+)"', html)
    assert sorted(image_srcs) == sorted(expected_plots)
    for src in image_srcs:
        assert "://" not in src
        assert not src.startswith(("/", "\\"))
        assert (result.out_dir / src).exists()


def test_pipeline_track_id_is_hashed_and_never_serializes_the_raw_token(
    tmp_path: Path, sr: int
):
    path = tmp_path / "revision.wav"
    _write_short_sine(path, sr)
    token = "high-entropy-private-revision-token"

    result = analyze_file(
        path,
        tmp_path / "report",
        config=_small_config(),
        selection=GraphSelection(profile="minimal"),
        track_id=token,
    )

    summary_text = result.summary_path.read_text(encoding="utf-8")
    markdown = result.report_path.read_text(encoding="utf-8")
    html = result.html_report_path.read_text(encoding="utf-8")
    identity = result.summary["source_identity"]
    assert identity["kind"] == "user-supplied-sha256"
    assert isinstance(identity["track_id_sha256"], str)
    assert len(identity["track_id_sha256"]) == 64
    assert token not in summary_text
    assert token not in markdown
    assert token not in html


def test_pipeline_reduced_graph_selection_keeps_summary_complete_and_supports_path_opt_in(
    tmp_path: Path, sr: int
):
    path = tmp_path / "private-layout" / "song.wav"
    path.parent.mkdir()
    _write_short_sine(path, sr)
    cfg = _small_config()

    result = analyze_file(
        path,
        tmp_path / "report",
        config=cfg,
        selection=GraphSelection(profile="minimal"),
        include_local_paths=True,
    )

    assert result.summary["plots"] == [
        "waveform_rms.png",
        "rms_timeline.png",
        "log_spectrogram.png",
        "sample_histogram.png",
    ]
    assert result.summary["graphs"] == {
        "profile": "minimal",
        "selected": ["waveform_rms", "rms_timeline", "log_spectrogram", "sample_histogram"],
        "available": [graph.key for graph in all_graphs()],
        "selected_filenames": [
            "waveform_rms.png",
            "rms_timeline.png",
            "log_spectrogram.png",
            "sample_histogram.png",
        ],
    }
    assert result.summary["analysis_config"] == asdict(cfg)
    assert result.summary["metadata"]["path"] == str(path.resolve())
    assert result.summary["metadata"]["path_kind"] == "absolute"
    assert result.summary["metadata"]["local_paths_included"] is True
    for block in [
        "levels",
        "rms_envelope",
        "crest_factor_timeline",
        "peak_timeline",
        "average_spectrum",
        "spectral_shape",
        "band_power_timeline",
        "band_energy_timeline",
        "onset_density",
        "chroma_cqt",
        "short_term_lufs",
        "stereo_correlation",
        "mid_side_energy",
    ]:
        assert block in result.summary
    assert "frame_peak_dbfs" in result.summary["peak_timeline"]
    assert "frame_peak_linear" in result.summary["peak_timeline"]


def test_rerun_removes_stale_owned_plot_preserves_human_files_and_survives_bad_input(
    tmp_path: Path, sr: int
):
    path = tmp_path / "song.wav"
    _write_short_sine(path, sr)
    out = tmp_path / "report"
    cfg = _small_config()

    analyze_file(
        path,
        out,
        config=cfg,
        selection=GraphSelection(profile="minimal", enable=("chroma_cqt",)),
    )
    stale_plot = out / "chroma_cqt.png"
    assert stale_plot.exists()
    human_file = out / "my-listening-notes.txt"
    human_file.write_text("keep this", encoding="utf-8")

    result = analyze_file(
        path,
        out,
        config=cfg,
        selection=GraphSelection(profile="minimal"),
    )

    assert not stale_plot.exists()
    assert human_file.read_text(encoding="utf-8") == "keep this"
    assert {item.name for item in out.glob("*.png")} == set(result.summary["plots"])
    assert len(list(out.glob("*.png"))) == 4
    manifest = json.loads((out / OUTPUT_MARKER_FILENAME).read_text(encoding="utf-8"))
    assert manifest["format"] == "audioatlas-output-manifest"
    assert manifest["kind"] == "single-track-report"

    before = {
        item.name: item.read_bytes()
        for item in out.iterdir()
        if item.is_file()
    }
    corrupt = tmp_path / "private-folder" / "broken.wav"
    corrupt.parent.mkdir()
    corrupt.write_bytes(b"not-audio")

    with pytest.raises(AudioLoadError):
        analyze_file(
            corrupt,
            out,
            config=cfg,
            selection=GraphSelection(profile="minimal"),
        )

    after = {
        item.name: item.read_bytes()
        for item in out.iterdir()
        if item.is_file()
    }
    assert after == before
    assert not list(tmp_path.glob(".report.audioatlas-*"))



def test_pipeline_hashes_optional_track_identity_without_storing_the_token(
    tmp_path: Path, sr: int
):
    path = tmp_path / "song.wav"
    _write_short_sine(path, sr)
    token = "private revision family token"

    result = analyze_file(
        path,
        tmp_path / "report",
        config=_small_config(),
        selection=GraphSelection(profile="minimal"),
        track_id=token,
    )

    identity = result.summary["source_identity"]
    assert identity["kind"] == "user-supplied-sha256"
    assert isinstance(identity["track_id_sha256"], str)
    assert len(identity["track_id_sha256"]) == 64
    serialized = result.summary_path.read_text(encoding="utf-8")
    assert token not in serialized


def test_analyze_file_collects_renderer_cycles_after_success(
    monkeypatch: pytest.MonkeyPatch,
):
    events: list[str] = []
    sentinel = object()

    def fake_impl(*args: object, **kwargs: object) -> object:
        events.append("analysis")
        return sentinel

    def fake_collect() -> int:
        events.append("collect")
        return 0

    monkeypatch.setattr(pipeline_module, "_analyze_file_impl", fake_impl)
    monkeypatch.setattr(pipeline_module.gc, "collect", fake_collect)

    result = pipeline_module.analyze_file("track.wav", "report")

    assert result is sentinel
    assert events == ["analysis", "collect"]


def test_analyze_file_collects_renderer_cycles_after_failure(
    monkeypatch: pytest.MonkeyPatch,
):
    events: list[str] = []

    def fake_impl(*args: object, **kwargs: object) -> object:
        events.append("analysis")
        raise RuntimeError("analysis failed")

    def fake_collect() -> int:
        events.append("collect")
        return 0

    monkeypatch.setattr(pipeline_module, "_analyze_file_impl", fake_impl)
    monkeypatch.setattr(pipeline_module.gc, "collect", fake_collect)

    with pytest.raises(RuntimeError, match="analysis failed"):
        pipeline_module.analyze_file("track.wav", "report")

    assert events == ["analysis", "collect"]


def test_reusing_output_between_catalog_and_single_report_removes_only_known_artifacts(
    tmp_path: Path, sr: int
):
    input_dir = tmp_path / "audio"
    input_dir.mkdir()
    path = input_dir / "song.wav"
    _write_short_sine(path, sr)
    out = tmp_path / "shared-output"
    cfg = _small_config()
    selection = GraphSelection(profile="minimal")

    analyze_folder(input_dir, out, config=cfg, selection=selection)
    human_file = out / "my-listening-notes.txt"
    human_file.write_text("keep this", encoding="utf-8")
    assert (out / "catalog.html").exists()
    assert (out / "song" / "report.html").exists()

    single = analyze_file(path, out, config=cfg, selection=selection)

    assert single.html_report_path.exists()
    assert not (out / "catalog.html").exists()
    assert not (out / "catalog.md").exists()
    assert not (out / "catalog_summary.json").exists()
    assert not (out / "song").exists()
    assert human_file.read_text(encoding="utf-8") == "keep this"

    analyze_folder(input_dir, out, config=cfg, selection=selection)

    assert (out / "catalog.html").exists()
    assert (out / "song" / "report.html").exists()
    for filename in SINGLE_REPORT_FILENAMES:
        assert not (out / filename).exists()
    assert not list(out.glob("*.png"))
    assert human_file.read_text(encoding="utf-8") == "keep this"
