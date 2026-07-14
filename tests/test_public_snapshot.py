from __future__ import annotations

import json
from pathlib import Path

from scripts.public_snapshot import (
    MANIFEST_NAME,
    build_manifest,
    source_files,
    verify_manifest,
    write_manifest,
)

SOURCE_COMMIT = "a" * 40


def _tree(tmp_path: Path) -> Path:
    root = tmp_path / "public"
    (root / "src").mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "fixture"\nversion = "1.2.3"\n', encoding="utf-8"
    )
    (root / "README.md").write_text("hello\n", encoding="utf-8")
    (root / "src" / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    manifest = build_manifest(
        root,
        source_files(root),
        package_version="1.2.3",
        source_commit=SOURCE_COMMIT,
    )
    write_manifest(root / MANIFEST_NAME, manifest)
    return root


def test_public_snapshot_accepts_canonical_tree(tmp_path: Path) -> None:
    assert verify_manifest(_tree(tmp_path)) == []


def test_public_snapshot_detects_modified_file(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    (root / "README.md").write_text("changed\n", encoding="utf-8")

    errors = verify_manifest(root)

    assert "stale file hash: README.md" in errors
    assert any(error.startswith("public_tree_sha256:") for error in errors)


def test_public_snapshot_detects_missing_file(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    (root / "src" / "module.py").unlink()

    errors = verify_manifest(root)

    assert "listed file is missing: src/module.py" in errors
    assert any(error.startswith("included_file_count:") for error in errors)


def test_public_snapshot_detects_unexpected_file(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    (root / "extra.txt").write_text("unexpected\n", encoding="utf-8")

    errors = verify_manifest(root)

    assert "included file is unlisted: extra.txt" in errors
    assert any(error.startswith("included_file_count:") for error in errors)


def test_public_snapshot_detects_deterministic_metadata_drift(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    path = root / MANIFEST_NAME
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["format_version"] = 99
    manifest["package_version"] = "9.9.9"
    manifest["source_commit"] = "not-a-commit"
    manifest["included_file_count"] = 99
    manifest["public_tree_sha256"] = "0" * 64
    write_manifest(path, manifest)

    errors = verify_manifest(root)

    assert any(error.startswith("format_version:") for error in errors)
    assert any(error.startswith("package_version:") for error in errors)
    assert any(error.startswith("source_commit:") for error in errors)
    assert any(error.startswith("included_file_count:") for error in errors)
    assert any(error.startswith("public_tree_sha256:") for error in errors)
