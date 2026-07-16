from __future__ import annotations

import json
from pathlib import Path

import pytest

import audioatlas.output as output_module
from audioatlas.output import (
    OUTPUT_MARKER_FILENAME,
    publish_staged_output,
    staged_output_directory,
    write_output_manifest,
)


def test_publish_replaces_owned_artifacts_and_preserves_unknown_files(tmp_path: Path):
    target = tmp_path / "report"
    target.mkdir()
    (target / "report.html").write_text("old report", encoding="utf-8")
    (target / "old_plot.png").write_bytes(b"old plot")
    (target / "notes.txt").write_text("human notes", encoding="utf-8")
    (target / "old-track").mkdir()
    (target / "old-track" / "report.html").write_text("old track", encoding="utf-8")
    write_output_manifest(
        target / "old-track",
        kind="single-track-report",
        generated_files=["report.html"],
    )
    (target / "user-folder").mkdir()
    (target / "user-folder" / "keep.txt").write_text("keep", encoding="utf-8")
    (target / OUTPUT_MARKER_FILENAME).write_text(
        json.dumps(
            {
                "format": "audioatlas-output-manifest",
                "manifest_version": 1,
                "kind": "batch-catalog",
                "generated_directories": ["old-track"],
            }
        ),
        encoding="utf-8",
    )

    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "report.html").write_text("new report", encoding="utf-8")
    (staging / "new_plot.png").write_bytes(b"new plot")
    (staging / "new-track").mkdir()
    (staging / "new-track" / "report.html").write_text("new track", encoding="utf-8")
    write_output_manifest(
        staging,
        kind="test",
        generated_files=["report.html", "new_plot.png"],
        generated_directories=["new-track"],
    )

    publish_staged_output(
        staging,
        target,
        owned_filenames={"report.html", "old_plot.png", "new_plot.png"},
    )

    assert (target / "report.html").read_text(encoding="utf-8") == "new report"
    assert (target / "new_plot.png").read_bytes() == b"new plot"
    assert not (target / "old_plot.png").exists()
    assert not (target / "old-track").exists()
    assert (target / "new-track" / "report.html").exists()
    assert (target / "notes.txt").read_text(encoding="utf-8") == "human notes"
    assert (target / "user-folder" / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_unrecognized_marker_cannot_claim_user_directories(tmp_path: Path):
    target = tmp_path / "report"
    target.mkdir()
    (target / "user-folder").mkdir()
    (target / "user-folder" / "keep.txt").write_text("keep", encoding="utf-8")
    (target / OUTPUT_MARKER_FILENAME).write_text(
        json.dumps({"generated_directories": ["user-folder"]}), encoding="utf-8"
    )

    staging = tmp_path / "staging"
    staging.mkdir()
    write_output_manifest(staging, kind="test", generated_files=[])

    publish_staged_output(staging, target, owned_filenames=set())

    assert (target / "user-folder" / "keep.txt").exists()


def test_parent_manifest_cannot_claim_directory_without_child_manifest(tmp_path: Path):
    target = tmp_path / "report"
    target.mkdir()
    (target / "user-folder").mkdir()
    (target / "user-folder" / "keep.txt").write_text("keep", encoding="utf-8")
    (target / OUTPUT_MARKER_FILENAME).write_text(
        json.dumps(
            {
                "format": "audioatlas-output-manifest",
                "manifest_version": 1,
                "kind": "batch-catalog",
                "generated_directories": ["user-folder"],
            }
        ),
        encoding="utf-8",
    )

    staging = tmp_path / "staging"
    staging.mkdir()
    write_output_manifest(staging, kind="batch-catalog", generated_files=[])

    publish_staged_output(staging, target, owned_filenames=set())

    assert (target / "user-folder" / "keep.txt").exists()


def test_staging_directory_is_cleaned_after_failure(tmp_path: Path):
    target = tmp_path / "report"
    captured: Path | None = None

    with (
        pytest.raises(RuntimeError, match="render failed"),
        staged_output_directory(target) as staging,
    ):
        captured = staging
        (staging / "partial.txt").write_text("partial", encoding="utf-8")
        raise RuntimeError("render failed")

    assert captured is not None
    assert not captured.exists()
    assert not target.exists()


def test_publish_refuses_to_replace_unowned_directory_before_mutation(tmp_path: Path):
    target = tmp_path / "report"
    target.mkdir()
    (target / "report.html").write_text("old report", encoding="utf-8")
    (target / "track").mkdir()
    (target / "track" / "keep.txt").write_text("human data", encoding="utf-8")

    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "report.html").write_text("new report", encoding="utf-8")
    (staging / "track").mkdir()
    (staging / "track" / "report.html").write_text("generated", encoding="utf-8")
    write_output_manifest(
        staging,
        kind="batch-catalog",
        generated_files=["report.html"],
        generated_directories=["track"],
    )

    with pytest.raises(ValueError, match="unowned output directory"):
        publish_staged_output(staging, target, owned_filenames={"report.html"})

    assert (target / "report.html").read_text(encoding="utf-8") == "old report"
    assert (target / "track" / "keep.txt").read_text(encoding="utf-8") == "human data"


def test_publish_refuses_file_over_directory_before_mutation(tmp_path: Path):
    target = tmp_path / "report"
    target.mkdir()
    (target / "summary.json").mkdir()
    (target / "summary.json" / "keep.txt").write_text("human data", encoding="utf-8")
    (target / "old_plot.png").write_bytes(b"old")

    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "summary.json").write_text("{}", encoding="utf-8")
    write_output_manifest(staging, kind="single-track-report", generated_files=["summary.json"])

    with pytest.raises(ValueError, match="replace an output directory with a file"):
        publish_staged_output(
            staging,
            target,
            owned_filenames={"summary.json", "old_plot.png"},
        )

    assert (target / "summary.json" / "keep.txt").read_text(encoding="utf-8") == (
        "human data"
    )
    assert (target / "old_plot.png").read_bytes() == b"old"


def test_legacy_v01_catalog_adopts_only_complete_report_directories(tmp_path: Path):
    target = tmp_path / "catalog"
    target.mkdir()
    legacy_track = target / "track-a"
    legacy_track.mkdir()
    for filename in ("report.html", "summary.json", "findings.json"):
        (legacy_track / filename).write_text("old", encoding="utf-8")
    (target / "catalog_summary.json").write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "tracks": [{"report_path": "track-a/report.html"}],
            }
        ),
        encoding="utf-8",
    )

    staging = tmp_path / "staging"
    staging.mkdir()
    new_track = staging / "track-a"
    new_track.mkdir()
    (new_track / "report.html").write_text("new", encoding="utf-8")
    write_output_manifest(
        staging,
        kind="batch-catalog",
        generated_files=[],
        generated_directories=["track-a"],
    )

    publish_staged_output(staging, target, owned_filenames={"catalog_summary.json"})

    assert (target / "track-a" / "report.html").read_text(encoding="utf-8") == "new"


def test_publish_rolls_back_files_after_mid_publication_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    target = tmp_path / "report"
    target.mkdir()
    (target / "report.html").write_text("old report", encoding="utf-8")
    (target / "old_plot.png").write_bytes(b"old plot")
    (target / "notes.txt").write_text("human notes", encoding="utf-8")
    write_output_manifest(
        target,
        kind="single-track-report",
        generated_files=["report.html", "old_plot.png", OUTPUT_MARKER_FILENAME],
    )
    old_manifest = (target / OUTPUT_MARKER_FILENAME).read_bytes()

    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "report.html").write_text("new report", encoding="utf-8")
    (staging / "new_plot.png").write_bytes(b"new plot")
    write_output_manifest(
        staging,
        kind="single-track-report",
        generated_files=["report.html", "new_plot.png", OUTPUT_MARKER_FILENAME],
    )

    real_replace = output_module.os.replace

    def fail_on_new_plot(source: str | Path, destination: str | Path) -> None:
        source_path = Path(source)
        if source_path.parent == staging and source_path.name == "new_plot.png":
            raise OSError("injected publish failure")
        real_replace(source, destination)

    monkeypatch.setattr(output_module.os, "replace", fail_on_new_plot)

    with pytest.raises(OSError, match="injected publish failure"):
        publish_staged_output(
            staging,
            target,
            owned_filenames={"report.html", "old_plot.png", "new_plot.png"},
        )

    assert (target / "report.html").read_text(encoding="utf-8") == "old report"
    assert (target / "old_plot.png").read_bytes() == b"old plot"
    assert not (target / "new_plot.png").exists()
    assert (target / OUTPUT_MARKER_FILENAME).read_bytes() == old_manifest
    assert (target / "notes.txt").read_text(encoding="utf-8") == "human notes"
    assert not list(tmp_path.glob(".report.backup-*"))


def test_publish_rolls_back_directories_after_mid_publication_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    target = tmp_path / "catalog"
    target.mkdir()
    (target / "catalog.html").write_text("old catalog", encoding="utf-8")
    old_track = target / "track-a"
    old_track.mkdir()
    (old_track / "report.html").write_text("old track", encoding="utf-8")
    write_output_manifest(
        old_track,
        kind="single-track-report",
        generated_files=["report.html", OUTPUT_MARKER_FILENAME],
    )
    write_output_manifest(
        target,
        kind="batch-catalog",
        generated_files=["catalog.html", OUTPUT_MARKER_FILENAME],
        generated_directories=["track-a"],
    )
    old_manifest = (target / OUTPUT_MARKER_FILENAME).read_bytes()

    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "catalog.html").write_text("new catalog", encoding="utf-8")
    for name in ("track-a", "track-b"):
        track = staging / name
        track.mkdir()
        (track / "report.html").write_text(f"new {name}", encoding="utf-8")
    write_output_manifest(
        staging,
        kind="batch-catalog",
        generated_files=["catalog.html", OUTPUT_MARKER_FILENAME],
        generated_directories=["track-a", "track-b"],
    )

    real_replace = output_module.os.replace

    def fail_on_second_track(source: str | Path, destination: str | Path) -> None:
        source_path = Path(source)
        if source_path.parent == staging and source_path.name == "track-b":
            raise OSError("injected directory publish failure")
        real_replace(source, destination)

    monkeypatch.setattr(output_module.os, "replace", fail_on_second_track)

    with pytest.raises(OSError, match="injected directory publish failure"):
        publish_staged_output(
            staging,
            target,
            owned_filenames={"catalog.html"},
        )

    assert (target / "catalog.html").read_text(encoding="utf-8") == "old catalog"
    assert (target / "track-a" / "report.html").read_text(encoding="utf-8") == (
        "old track"
    )
    assert not (target / "track-b").exists()
    assert (target / OUTPUT_MARKER_FILENAME).read_bytes() == old_manifest
    assert not list(tmp_path.glob(".catalog.backup-*"))


def test_publish_refuses_unowned_staged_file_before_mutation(tmp_path: Path):
    target = tmp_path / "report"
    target.mkdir()
    (target / "report.html").write_text("old report", encoding="utf-8")

    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "report.html").write_text("new report", encoding="utf-8")
    (staging / "surprise.tmp").write_text("unexpected", encoding="utf-8")
    write_output_manifest(
        staging,
        kind="single-track-report",
        generated_files=[
            "report.html",
            "surprise.tmp",
            OUTPUT_MARKER_FILENAME,
        ],
    )

    with pytest.raises(ValueError, match="unowned staged file"):
        publish_staged_output(staging, target, owned_filenames={"report.html"})

    assert (target / "report.html").read_text(encoding="utf-8") == "old report"
    assert not (target / "surprise.tmp").exists()


def test_normal_report_cannot_replace_song_project_root(tmp_path: Path) -> None:
    destination = tmp_path / "project"
    destination.mkdir()
    (destination / "audioatlas-project.yaml").write_text("schema_version: 0.1.0\n")
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "report.html").write_text("new report", encoding="utf-8")
    write_output_manifest(
        staging,
        kind="single-track-report",
        generated_files=["report.html", OUTPUT_MARKER_FILENAME],
    )

    with pytest.raises(ValueError, match="song-project root"):
        publish_staged_output(staging, destination, owned_filenames={"report.html"})

    assert (destination / "audioatlas-project.yaml").is_file()
    assert not (destination / "report.html").exists()
