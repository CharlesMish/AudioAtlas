"""Shared deterministic PUBLIC_SNAPSHOT.json generation and verification."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tomllib
from collections.abc import Iterable
from pathlib import Path

FORMAT_VERSION = 1
MANIFEST_NAME = "PUBLIC_SNAPSHOT.json"
ALWAYS_EXCLUDED_PARTS = {
    ".git",
    ".hypothesis",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
}
_COMMIT_RE = re.compile(r"[0-9a-f]{40}")


def source_files(root: Path) -> list[Path]:
    """Return sorted artifact files, preferring Git's tracked-file contract."""

    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        paths = (path.relative_to(root) for path in root.rglob("*") if path.is_file())
    else:
        paths = (
            Path(raw.decode("utf-8"))
            for raw in result.stdout.split(b"\0")
            if raw
        )

    return sorted(
        relative
        for relative in paths
        if relative.as_posix() != MANIFEST_NAME
        and not (set(relative.parts) & ALWAYS_EXCLUDED_PARTS)
        and (root / relative).is_file()
    )


def file_records(tree: Path, files: Iterable[Path]) -> list[dict[str, str]]:
    """Hash files in canonical path order."""

    return [
        {
            "path": relative.as_posix(),
            "sha256": hashlib.sha256((tree / relative).read_bytes()).hexdigest(),
        }
        for relative in sorted(files)
    ]


def public_tree_sha256(records: Iterable[dict[str, str]]) -> str:
    """Hash canonical ``path NUL file-hash newline`` records."""

    digest = hashlib.sha256()
    for record in records:
        digest.update(record["path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(record["sha256"].encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def build_manifest(
    tree: Path,
    files: Iterable[Path],
    *,
    package_version: str,
    source_commit: str | None,
) -> dict[str, object]:
    """Build the canonical manifest; the manifest itself is never included."""

    records = file_records(tree, files)
    return {
        "format_version": FORMAT_VERSION,
        "package_version": package_version,
        "source_commit": source_commit,
        "included_file_count": len(records),
        "public_tree_sha256": public_tree_sha256(records),
        "files": records,
    }


def package_version(root: Path) -> str:
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    return str(pyproject["project"]["version"])


def write_manifest(path: Path, manifest: dict[str, object]) -> None:
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify_manifest(
    root: Path,
    *,
    expected_source_commit: str | None = None,
) -> list[str]:
    """Return all deterministic manifest disagreements for a public artifact."""

    manifest_path = root / MANIFEST_NAME
    if not manifest_path.is_file():
        return [f"missing manifest: {MANIFEST_NAME}"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"invalid manifest: {exc}"]

    errors: list[str] = []
    if manifest.get("format_version") != FORMAT_VERSION:
        errors.append(
            f"format_version: expected {FORMAT_VERSION!r}, got {manifest.get('format_version')!r}"
        )

    expected_package_version = package_version(root)
    if manifest.get("package_version") != expected_package_version:
        errors.append(
            "package_version: "
            f"expected {expected_package_version!r}, got {manifest.get('package_version')!r}"
        )

    source_commit = manifest.get("source_commit")
    if not isinstance(source_commit, str) or _COMMIT_RE.fullmatch(source_commit) is None:
        errors.append("source_commit: expected a 40-character lowercase Git object ID")
    if expected_source_commit is not None and source_commit != expected_source_commit:
        errors.append(
            f"source_commit: expected {expected_source_commit!r}, got {source_commit!r}"
        )

    raw_records = manifest.get("files")
    if not isinstance(raw_records, list):
        return [*errors, "files: expected a list"]
    records = [record for record in raw_records if isinstance(record, dict)]
    if len(records) != len(raw_records):
        errors.append("files: every entry must be an object")

    listed_paths = [record.get("path") for record in records]
    if any(not isinstance(path, str) for path in listed_paths):
        return [*errors, "files: every entry must contain a string path"]
    listed = {str(path) for path in listed_paths}
    if len(listed) != len(listed_paths):
        errors.append("files: duplicate paths are not allowed")

    actual_files = source_files(root)
    actual = {path.as_posix() for path in actual_files}
    for path in sorted(listed - actual):
        errors.append(f"listed file is missing: {path}")
    for path in sorted(actual - listed):
        errors.append(f"included file is unlisted: {path}")

    actual_records = file_records(root, actual_files)
    actual_hashes = {record["path"]: record["sha256"] for record in actual_records}
    for record in records:
        path = record.get("path")
        if (
            isinstance(path, str)
            and path in actual_hashes
            and record.get("sha256") != actual_hashes[path]
        ):
            errors.append(f"stale file hash: {path}")

    if manifest.get("included_file_count") != len(actual_records):
        errors.append(
            "included_file_count: "
            f"expected {len(actual_records)}, got {manifest.get('included_file_count')!r}"
        )
    expected_tree_hash = public_tree_sha256(actual_records)
    if manifest.get("public_tree_sha256") != expected_tree_hash:
        errors.append(
            "public_tree_sha256: "
            f"expected {expected_tree_hash}, got {manifest.get('public_tree_sha256')!r}"
        )
    return errors
