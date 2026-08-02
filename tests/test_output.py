from __future__ import annotations

import json
from pathlib import Path

import pytest

import audioatlas.output as output_module
from audioatlas.errors import OutputBusyError, OutputOwnershipError
from audioatlas.output import (
    OUTPUT_MARKER_FILENAME,
    SourceBinding,
    output_transaction,
    publish_staged_output,
    staged_output_directory,
    write_output_manifest,
)


def test_output_lock_identity_folds_case_on_windows(monkeypatch) -> None:
    monkeypatch.setattr(
        output_module.os.path,
        "normcase",
        lambda value: value.casefold().replace("/", "\\"),
    )

    assert output_module._output_lock_digest(
        Path("C:/Music/AudioAtlas Report")
    ) == output_module._output_lock_digest(Path("c:/music/audioatlas report"))


def test_output_transaction_uses_guard_when_cache_lock_is_denied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_root = tmp_path / "cache"
    temporary_root = tmp_path / "temporary"
    real_file_lock = output_module.FileLock

    class DeniedLock:
        def acquire(self) -> None:
            raise PermissionError("cache is restricted")

    def lock_factory(path: Path, *, timeout: int):
        if Path(path).is_relative_to(cache_root):
            return DeniedLock()
        return real_file_lock(path, timeout=timeout)

    monkeypatch.setattr(output_module, "user_cache_path", lambda *args, **kwargs: cache_root)
    monkeypatch.setattr(output_module.tempfile, "gettempdir", lambda: str(temporary_root))
    monkeypatch.setattr(output_module, "FileLock", lock_factory)
    destination = tmp_path / "report"

    with output_transaction(destination) as transaction:
        assert transaction.destination == destination.resolve()
        with (
            pytest.raises(OutputBusyError, match="already updating"),
            output_transaction(destination),
        ):
            pass


def test_publish_replaces_owned_artifacts_and_preserves_unknown_files(tmp_path: Path):
    target = tmp_path / "report"
    target.mkdir()
    (target / "catalog.html").write_text("old catalog", encoding="utf-8")
    (target / "catalog.md").write_text("stale catalog", encoding="utf-8")
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
                "generated_files": [
                    "catalog.html",
                    "catalog.md",
                    OUTPUT_MARKER_FILENAME,
                ],
                "generated_directories": ["old-track"],
            }
        ),
        encoding="utf-8",
    )

    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "catalog.html").write_text("new catalog", encoding="utf-8")
    (staging / "catalog_summary.json").write_text("{}", encoding="utf-8")
    (staging / "new-track").mkdir()
    (staging / "new-track" / "report.html").write_text("new track", encoding="utf-8")
    write_output_manifest(
        staging,
        kind="batch-catalog",
        generated_files=["catalog.html", "catalog_summary.json"],
        generated_directories=["new-track"],
    )

    publish_staged_output(
        staging,
        target,
        allowed_staged_filenames={"catalog.html", "catalog_summary.json"},
    )

    assert (target / "catalog.html").read_text(encoding="utf-8") == "new catalog"
    assert (target / "catalog_summary.json").read_text(encoding="utf-8") == "{}"
    assert not (target / "catalog.md").exists()
    assert not (target / "old-track").exists()
    assert (target / "new-track" / "report.html").exists()
    assert (target / "notes.txt").read_text(encoding="utf-8") == "human notes"
    assert (target / "user-folder" / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_publish_preserves_undeclared_reserved_name_from_previous_report(tmp_path: Path):
    target = tmp_path / "report"
    target.mkdir()
    (target / "report.html").write_text("old report", encoding="utf-8")
    unrelated_catalog = target / "catalog.html"
    unrelated_catalog.write_bytes(b"unrelated reserved-name file")
    write_output_manifest(
        target,
        kind="single-track-report",
        generated_files=["report.html", OUTPUT_MARKER_FILENAME],
    )

    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "report.html").write_text("new report", encoding="utf-8")
    write_output_manifest(
        staging,
        kind="single-track-report",
        generated_files=["report.html", OUTPUT_MARKER_FILENAME],
    )

    publish_staged_output(
        staging,
        target,
        allowed_staged_filenames={"report.html", "catalog.html"},
    )

    assert (target / "report.html").read_text(encoding="utf-8") == "new report"
    assert unrelated_catalog.read_bytes() == b"unrelated reserved-name file"


def test_publish_refuses_to_replace_undeclared_reserved_name(tmp_path: Path):
    target = tmp_path / "report"
    target.mkdir()
    (target / "summary.json").write_text("old summary", encoding="utf-8")
    unrelated_report = target / "report.html"
    unrelated_report.write_bytes(b"unrelated report")
    write_output_manifest(
        target,
        kind="single-track-report",
        generated_files=["summary.json", OUTPUT_MARKER_FILENAME],
    )
    old_manifest = (target / OUTPUT_MARKER_FILENAME).read_bytes()

    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "report.html").write_text("new report", encoding="utf-8")
    write_output_manifest(
        staging,
        kind="single-track-report",
        generated_files=["report.html", OUTPUT_MARKER_FILENAME],
    )

    with pytest.raises(OutputOwnershipError, match="unowned output file.*report.html"):
        publish_staged_output(
            staging,
            target,
            allowed_staged_filenames={"summary.json", "report.html"},
        )

    assert unrelated_report.read_bytes() == b"unrelated report"
    assert (target / "summary.json").read_text(encoding="utf-8") == "old summary"
    assert (target / OUTPUT_MARKER_FILENAME).read_bytes() == old_manifest


def test_publish_refuses_mismatched_source_binding_before_mutation(tmp_path: Path):
    target = tmp_path / "report"
    target.mkdir()
    report = target / "report.html"
    report.write_bytes(b"first source report")
    write_output_manifest(
        target,
        kind="single-track-report",
        generated_files=["report.html", OUTPUT_MARKER_FILENAME],
        source_binding=SourceBinding("a" * 64),
    )
    old_manifest = (target / OUTPUT_MARKER_FILENAME).read_bytes()

    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "report.html").write_bytes(b"second source report")
    write_output_manifest(
        staging,
        kind="single-track-report",
        generated_files=["report.html", OUTPUT_MARKER_FILENAME],
        source_binding=SourceBinding("b" * 64),
    )

    with pytest.raises(OutputOwnershipError, match="different or ambiguously bound"):
        publish_staged_output(
            staging,
            target,
            allowed_staged_filenames={"report.html"},
        )

    assert report.read_bytes() == b"first source report"
    assert (target / OUTPUT_MARKER_FILENAME).read_bytes() == old_manifest


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
    write_output_manifest(staging, kind="single-track-report", generated_files=[])

    with pytest.raises(OutputOwnershipError, match="unreadable or unrecognized"):
        publish_staged_output(staging, target, allowed_staged_filenames=set())

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
                "generated_files": [OUTPUT_MARKER_FILENAME],
                "generated_directories": ["user-folder"],
            }
        ),
        encoding="utf-8",
    )

    staging = tmp_path / "staging"
    staging.mkdir()
    write_output_manifest(staging, kind="batch-catalog", generated_files=[])

    publish_staged_output(staging, target, allowed_staged_filenames=set())

    assert (target / "user-folder" / "keep.txt").exists()


@pytest.mark.parametrize(
    ("kind", "generated_files", "generated_directories"),
    [
        ("single-track-report", ["../outside.txt"], []),
        ("single-track-report", ["nested/report.html"], []),
        ("single-track-report", [r"nested\report.html"], []),
        ("single-track-report", ["/tmp/report.html"], []),
        ("single-track-report", ["unsupported.txt"], []),
        ("single-track-report", ["report.html", "report.html"], []),
        ("batch-catalog", ["catalog.html"], ["Track", "track"]),
        ("batch-catalog", ["catalog.html"], [".."]),
    ],
)
def test_malformed_manifest_cannot_authorize_deletion(
    tmp_path: Path,
    kind: str,
    generated_files: list[str],
    generated_directories: list[str],
):
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"outside bytes")
    target = tmp_path / "report"
    target.mkdir()
    unrelated_catalog = target / "catalog.html"
    unrelated_catalog.write_bytes(b"unrelated catalog bytes")
    (target / OUTPUT_MARKER_FILENAME).write_text(
        json.dumps(
            {
                "format": "audioatlas-output-manifest",
                "manifest_version": 1,
                "kind": kind,
                "generated_files": generated_files,
                "generated_directories": generated_directories,
            }
        ),
        encoding="utf-8",
    )

    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "summary.json").write_text("{}", encoding="utf-8")
    write_output_manifest(
        staging,
        kind="single-track-report",
        generated_files=["summary.json", OUTPUT_MARKER_FILENAME],
    )

    with pytest.raises(OutputOwnershipError, match="unsafe or malformed"):
        publish_staged_output(
            staging,
            target,
            allowed_staged_filenames={"summary.json"},
        )

    assert outside.read_bytes() == b"outside bytes"
    assert unrelated_catalog.read_bytes() == b"unrelated catalog bytes"


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
    (target / "catalog.html").write_text("old catalog", encoding="utf-8")
    (target / "track").mkdir()
    (target / "track" / "keep.txt").write_text("human data", encoding="utf-8")
    write_output_manifest(
        target,
        kind="batch-catalog",
        generated_files=["catalog.html", OUTPUT_MARKER_FILENAME],
    )

    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "catalog.html").write_text("new catalog", encoding="utf-8")
    (staging / "track").mkdir()
    (staging / "track" / "report.html").write_text("generated", encoding="utf-8")
    write_output_manifest(
        staging,
        kind="batch-catalog",
        generated_files=["catalog.html"],
        generated_directories=["track"],
    )

    with pytest.raises(OutputOwnershipError, match="unowned output directory"):
        publish_staged_output(
            staging,
            target,
            allowed_staged_filenames={"catalog.html"},
        )

    assert (target / "catalog.html").read_text(encoding="utf-8") == "old catalog"
    assert (target / "track" / "keep.txt").read_text(encoding="utf-8") == "human data"


def test_publish_refuses_file_over_directory_before_mutation(tmp_path: Path):
    target = tmp_path / "report"
    target.mkdir()
    (target / "summary.json").mkdir()
    (target / "summary.json" / "keep.txt").write_text("human data", encoding="utf-8")
    (target / "chroma_cqt.png").write_bytes(b"old")
    write_output_manifest(
        target,
        kind="single-track-report",
        generated_files=["chroma_cqt.png", OUTPUT_MARKER_FILENAME],
    )

    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "summary.json").write_text("{}", encoding="utf-8")
    write_output_manifest(staging, kind="single-track-report", generated_files=["summary.json"])

    with pytest.raises(OutputOwnershipError, match="replace an output directory with a file"):
        publish_staged_output(
            staging,
            target,
            allowed_staged_filenames={"summary.json", "chroma_cqt.png"},
        )

    assert (target / "summary.json" / "keep.txt").read_text(encoding="utf-8") == (
        "human data"
    )
    assert (target / "chroma_cqt.png").read_bytes() == b"old"


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

    publish_staged_output(
        staging,
        target,
        allowed_staged_filenames={"catalog_summary.json"},
    )

    assert (target / "track-a" / "report.html").read_text(encoding="utf-8") == "new"


def test_publish_rolls_back_files_after_mid_publication_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    target = tmp_path / "report"
    target.mkdir()
    (target / "report.html").write_text("old report", encoding="utf-8")
    (target / "chroma_cqt.png").write_bytes(b"old plot")
    (target / "notes.txt").write_text("human notes", encoding="utf-8")
    unrelated_catalog = target / "catalog.html"
    unrelated_catalog.write_bytes(b"unrelated catalog")
    write_output_manifest(
        target,
        kind="single-track-report",
        generated_files=["report.html", "chroma_cqt.png", OUTPUT_MARKER_FILENAME],
    )
    old_manifest = (target / OUTPUT_MARKER_FILENAME).read_bytes()

    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "report.html").write_text("new report", encoding="utf-8")
    (staging / "waveform_rms.png").write_bytes(b"new plot")
    write_output_manifest(
        staging,
        kind="single-track-report",
        generated_files=["report.html", "waveform_rms.png", OUTPUT_MARKER_FILENAME],
    )

    real_replace = output_module.os.replace

    def fail_on_new_plot(source: str | Path, destination: str | Path) -> None:
        source_path = Path(source)
        if source_path.parent == staging and source_path.name == "waveform_rms.png":
            raise OSError("injected publish failure")
        real_replace(source, destination)

    monkeypatch.setattr(output_module.os, "replace", fail_on_new_plot)

    with pytest.raises(OSError, match="injected publish failure"):
        publish_staged_output(
            staging,
            target,
            allowed_staged_filenames={"report.html", "waveform_rms.png"},
        )

    assert (target / "report.html").read_text(encoding="utf-8") == "old report"
    assert (target / "chroma_cqt.png").read_bytes() == b"old plot"
    assert not (target / "waveform_rms.png").exists()
    assert (target / OUTPUT_MARKER_FILENAME).read_bytes() == old_manifest
    assert (target / "notes.txt").read_text(encoding="utf-8") == "human notes"
    assert unrelated_catalog.read_bytes() == b"unrelated catalog"
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
            allowed_staged_filenames={"catalog.html"},
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
    write_output_manifest(
        target,
        kind="single-track-report",
        generated_files=["report.html", OUTPUT_MARKER_FILENAME],
    )

    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "report.html").write_text("new report", encoding="utf-8")
    (staging / "summary.json").write_text("{}", encoding="utf-8")
    write_output_manifest(
        staging,
        kind="single-track-report",
        generated_files=[
            "report.html",
            "summary.json",
            OUTPUT_MARKER_FILENAME,
        ],
    )

    with pytest.raises(ValueError, match="unowned staged file"):
        publish_staged_output(
            staging,
            target,
            allowed_staged_filenames={"report.html"},
        )

    assert (target / "report.html").read_text(encoding="utf-8") == "old report"
    assert not (target / "summary.json").exists()


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

    with pytest.raises(OutputOwnershipError, match="song-project root"):
        publish_staged_output(
            staging,
            destination,
            allowed_staged_filenames={"report.html"},
        )

    assert (destination / "audioatlas-project.yaml").is_file()
    assert not (destination / "report.html").exists()


def test_output_transaction_rejects_concurrent_destination(tmp_path: Path) -> None:
    destination = tmp_path / "report"

    with (
        output_transaction(destination),
        pytest.raises(OutputBusyError, match="already updating"),
        output_transaction(destination),
    ):
        raise AssertionError("contended transaction unexpectedly acquired")


def test_publish_refuses_output_folder_symlink(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    destination = tmp_path / "report"
    destination.symlink_to(real, target_is_directory=True)
    staging = tmp_path / "staging"
    staging.mkdir()
    write_output_manifest(staging, kind="single-track-report", generated_files=[])

    with pytest.raises(OutputOwnershipError, match="symlink"):
        publish_staged_output(
            staging,
            destination,
            allowed_staged_filenames=set(),
        )

    assert not list(real.iterdir())
