from __future__ import annotations

import importlib.util
import json
import subprocess
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "export_public_tree.py"


def _module():
    spec = importlib.util.spec_from_file_location("audioatlas_public_export", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(args: list[str], *, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _committed_export_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "stewardship"
    root.mkdir()
    (root / "README.md").write_text("public\n", encoding="utf-8")
    (root / "PROJECT_CHARTER.md").write_text("private\n", encoding="utf-8")
    _git(["init", "-q"], cwd=root)
    _git(["config", "user.name", "AudioAtlas Tests"], cwd=root)
    _git(["config", "user.email", "tests@example.invalid"], cwd=root)
    _git(["add", "."], cwd=root)
    _git(["commit", "-q", "-m", "fixture"], cwd=root)
    return root


def test_public_export_excludes_stewardship_material_but_keeps_user_contracts():
    module = _module()

    excluded = [
        "PROJECT_CHARTER.md",
        "docs/AGENT_TASKS.md",
        "docs/HOPEFUL_SKEPTIC_PROJECT_EDITION.md",
        "docs/LAUNCHER_REHEARSAL.md",
        "docs/calibration/README.md",
        "docs/stewardship/PUBLIC_RELEASE_MODEL.md",
        "scripts/prepare_calibration_review.py",
        "starter_kit/LAUNCHER_REHEARSAL_LOG.md",
        "tests/test_calibration_replay.py",
        "tests/test_public_export.py",
    ]
    included = [
        "AUDIO_RIGHTS.md",
        "README.md",
        "README_EASY_RUN.md",
        "docs/USER_GUIDE.md",
        "docs/FINDING_RULES.md",
        "docs/ALPHA_LIMITATIONS.md",
        "src/audioatlas/pipeline.py",
        "tests/test_pipeline.py",
        ".github/workflows/ci.yml",
        "examples/demo_audio/README.md",
        "examples/demo_audio/audioatlas_demo.wav",
        "examples/demo_audio/guitar.wav",
        "examples/demo_audio/guitar_koto_cello_drums.wav",
    ]

    assert all(module._is_stewardship_only(Path(path)) for path in excluded)
    assert not any(module._is_stewardship_only(Path(path)) for path in included)


def test_public_zip_preserves_mac_launcher_execute_permissions(tmp_path: Path):
    module = _module()
    tree = tmp_path / "AudioAtlas-public"
    launchers = [
        "scripts/run_audioatlas_mac.command",
        "starter_kit/RUN_FULL.command",
        "starter_kit/RUN_MINIMAL.command",
        "starter_kit/RUN_SECTIONS_PROMPTED.command",
        "starter_kit/RUN_STANDARD.command",
    ]
    regular_file = "starter_kit/README_FOR_NON_CODERS.md"
    for relative in [*launchers, regular_file]:
        path = tree / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative, encoding="utf-8")

    destination = tmp_path / "AudioAtlas-public.zip"
    module._write_zip(tree, destination)

    with zipfile.ZipFile(destination) as archive:
        for relative in launchers:
            info = archive.getinfo(f"{tree.name}/{relative}")
            assert info.create_system == 3
            assert info.external_attr >> 16 == 0o100755
        regular_info = archive.getinfo(f"{tree.name}/{regular_file}")
        assert regular_info.create_system == 3
        assert regular_info.external_attr >> 16 == 0o100644


def test_exported_manifest_records_owner_commit_and_excludes_itself(
    tmp_path: Path,
    monkeypatch,
):
    module = _module()
    tree = tmp_path / "AudioAtlas-public"
    source_commit = module._git_commit(ROOT)
    monkeypatch.setattr(module, "_committed_public_source", lambda _root: source_commit)

    assert module.main(["--out", str(tree)]) == 0

    manifest = json.loads((tree / "PUBLIC_SNAPSHOT.json").read_text(encoding="utf-8"))
    assert manifest["source_commit"] == source_commit
    assert "PUBLIC_SNAPSHOT.json" not in {record["path"] for record in manifest["files"]}


@pytest.mark.parametrize("change", ["modified", "staged", "deleted"])
def test_public_export_refuses_tracked_public_changes(tmp_path: Path, change: str):
    module = _module()
    root = _committed_export_fixture(tmp_path)
    readme = root / "README.md"
    if change == "deleted":
        readme.unlink()
    else:
        readme.write_text(f"{change}\n", encoding="utf-8")
    if change == "staged":
        _git(["add", "README.md"], cwd=root)

    with pytest.raises(SystemExit, match="README.md"):
        module._committed_public_source(root)


def test_public_export_allows_dirty_stewardship_only_files(tmp_path: Path):
    module = _module()
    root = _committed_export_fixture(tmp_path)
    (root / "PROJECT_CHARTER.md").write_text("private draft\n", encoding="utf-8")

    assert module._committed_public_source(root) == _git(["rev-parse", "HEAD"], cwd=root)
