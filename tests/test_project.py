from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

import audioatlas.project as project_module
from audioatlas.cli import main
from audioatlas.errors import ProjectError
from audioatlas.project import (
    add_project_revision,
    build_project,
    init_project,
    load_project,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "sine_1k_-6dbfs_2s.wav"


def test_init_project_writes_private_config_and_portable_static_indexes(tmp_path: Path) -> None:
    project = tmp_path / "my song"
    config = init_project(
        project,
        name="My [Song]",
        graphs_profile="compact",
        sections=[("intro", 0.0, 1.0)],
    )

    assert (project / "audioatlas-project.yaml").is_file()
    assert (project / "project.json").is_file()
    assert (project / "project.md").is_file()
    assert (project / "project.html").is_file()
    manifest = json.loads((project / ".audioatlas-output.json").read_text(encoding="utf-8"))
    assert manifest["kind"] == "song-project"

    payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "0.1.0"
    assert payload["project_id_sha256"] == hashlib.sha256(
        config["project_id"].encode("utf-8")
    ).hexdigest()
    serialized = json.dumps(payload)
    assert config["project_id"] not in serialized
    assert str(tmp_path) not in serialized
    assert "My \\[Song\\]" in (project / "project.md").read_text(encoding="utf-8")


def test_add_two_revisions_writes_reports_guarded_diff_and_portable_index(tmp_path: Path) -> None:
    project = tmp_path / "project"
    init_project(project, name="Revision Song", graphs_profile="compact")

    first = add_project_revision(project, FIXTURE, label="Mix 1")
    second = add_project_revision(project, FIXTURE, label="Mix 2")

    assert first["id"] == "001-mix-1"
    assert second["id"] == "002-mix-2"
    assert (project / first["report"] / "report.html").is_file()
    diff = project / second["diff_from_previous"]
    assert (diff / "revision_diff.html").is_file()
    diff_payload = json.loads((diff / "revision_diff.json").read_text(encoding="utf-8"))
    assert diff_payload["comparability"]["status"] == "exact"
    assert diff_payload["same_track"]["basis"] == "matching-user-supplied-track-id-digest"

    payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
    assert [item["label"] for item in payload["revisions"]] == ["Mix 1", "Mix 2"]
    assert all("source" not in item for item in payload["revisions"])
    for filename in ("project.json", "project.md", "project.html"):
        assert str(FIXTURE.parent) not in (project / filename).read_text(encoding="utf-8")


def test_project_add_failure_preserves_config_and_indexes(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    init_project(project, name="Safe Song", graphs_profile="compact")
    before = {
        name: (project / name).read_bytes()
        for name in ("audioatlas-project.yaml", "project.json", "project.md", "project.html")
    }

    def fail_analysis(*args, **kwargs):
        raise ValueError("synthetic analysis failure")

    monkeypatch.setattr("audioatlas.pipeline.analyze_file", fail_analysis)
    with pytest.raises(ValueError, match="synthetic analysis failure"):
        add_project_revision(project, FIXTURE, label="Broken Mix")

    for name, contents in before.items():
        assert (project / name).read_bytes() == contents
    assert not (project / "reports").exists()


def test_project_index_publication_failure_removes_new_revision(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    init_project(project, name="Rollback Song", graphs_profile="compact")
    before = (project / "audioatlas-project.yaml").read_bytes()

    def fail_publication(*args, **kwargs):
        raise OSError("synthetic project index failure")

    monkeypatch.setattr(project_module, "_publish_project_root", fail_publication)
    with pytest.raises(OSError, match="synthetic project index failure"):
        add_project_revision(project, FIXTURE, label="Mix 1")

    assert (project / "audioatlas-project.yaml").read_bytes() == before
    assert not (project / "reports").exists()


def test_project_sections_are_reused_for_each_revision(tmp_path: Path) -> None:
    project = tmp_path / "project"
    init_project(
        project,
        name="Section Song",
        graphs_profile="compact",
        sections=[("opening", 0.0, 0.5)],
    )

    revision = add_project_revision(project, FIXTURE, label="Mix 1")

    assert len(revision["sections"]) == 1
    section_report = project / revision["sections"][0]["report"]
    assert (section_report / "report.html").is_file()
    summary = json.loads((section_report / "summary.json").read_text(encoding="utf-8"))
    assert summary["metadata"]["source_start_seconds"] == 0.0
    assert summary["metadata"]["source_end_seconds"] == 0.5


def test_build_refuses_missing_revision_artifacts(tmp_path: Path) -> None:
    project = tmp_path / "project"
    init_project(project, name="Broken Project", graphs_profile="compact")
    config = load_project(project)
    config["revisions"] = [
        {
            "id": "001-mix",
            "label": "Mix",
            "source": "/private/source.wav",
            "source_filename": "source.wav",
            "added_at": "2026-07-15T00:00:00Z",
            "report": "reports/001-mix",
            "sections": [],
        }
    ]
    (project / "audioatlas-project.yaml").write_text(
        yaml.safe_dump(config, sort_keys=False), encoding="utf-8"
    )

    with pytest.raises(ProjectError, match="missing report artifacts"):
        build_project(project)


def test_project_config_rejects_artifact_path_traversal(tmp_path: Path) -> None:
    project = tmp_path / "project"
    init_project(project, name="Guarded Project", graphs_profile="compact")
    config = load_project(project)
    config["revisions"] = [
        {
            "id": "001-mix",
            "label": "Mix",
            "source": "/private/source.wav",
            "source_filename": "source.wav",
            "added_at": "2026-07-15T00:00:00Z",
            "report": "../private-report",
            "sections": [],
        }
    ]
    (project / "audioatlas-project.yaml").write_text(
        yaml.safe_dump(config, sort_keys=False), encoding="utf-8"
    )

    with pytest.raises(ProjectError, match="must remain inside"):
        load_project(project)


def test_project_cli_init_and_build(tmp_path: Path) -> None:
    runner = CliRunner()
    project = tmp_path / "cli-project"

    initialized = runner.invoke(
        main,
        ["project", "init", str(project), "--name", "CLI Song", "--graphs-profile", "compact"],
    )
    assert initialized.exit_code == 0, initialized.output
    assert "song project created" in initialized.output

    rebuilt = runner.invoke(main, ["project", "build", str(project)])
    assert rebuilt.exit_code == 0, rebuilt.output
    assert "song project rebuilt" in rebuilt.output
