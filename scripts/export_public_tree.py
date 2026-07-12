#!/usr/bin/env python3
"""Export a deterministic, user-facing AudioAtlas source tree.

The canonical stewardship checkout retains internal review and calibration
material. This exporter produces the Git-facing public tree without forking the
implementation or editing source files in place.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path, PurePosixPath

FORMAT_VERSION = 1

STEWARDSHIP_ONLY_PREFIXES = (
    "PROJECT_CHARTER.md",
    "docs/AGENT_TASKS.md",
    "docs/HOPEFUL_SKEPTIC_PROJECT_EDITION.md",
    "docs/LAUNCHER_REHEARSAL.md",
    "docs/archive/",
    "docs/calibration/",
    "docs/stewardship/",
    "scripts/export_public_tree.py",
    "scripts/generate_calibration_fixtures.py",
    "scripts/prepare_calibration_review.py",
    "scripts/replay_calibration_rules.py",
    "starter_kit/LAUNCHER_REHEARSAL_LOG.md",
    "tests/test_calibration_fixtures.py",
    "tests/test_calibration_replay.py",
    "tests/test_calibration_review_preparation.py",
    "tests/test_public_export.py",
)

ALWAYS_EXCLUDED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="Public tree output directory.")
    parser.add_argument("--zip", dest="zip_path", type=Path, help="Optional public source ZIP.")
    parser.add_argument("--force", action="store_true", help="Replace an existing output tree/ZIP.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    out = args.out.expanduser().resolve()
    zip_path = args.zip_path.expanduser().resolve() if args.zip_path else None
    _validate_destinations(root, out, zip_path)
    _prepare_destination(out, force=args.force)
    if zip_path is not None:
        _prepare_file_destination(zip_path, force=args.force)

    files = _source_files(root)
    public_files = [path for path in files if not _is_stewardship_only(path)]
    for relative in public_files:
        source = root / relative
        destination = out / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    manifest = _build_manifest(root, out, public_files)
    manifest_path = out / "PUBLIC_SNAPSHOT.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if zip_path is not None:
        _write_zip(out, zip_path)

    print(f"Public AudioAtlas tree: {out}")
    print(f"Included files: {manifest['included_file_count']}")
    print(f"Tree SHA-256: {manifest['public_tree_sha256']}")
    if zip_path is not None:
        print(f"Public source ZIP: {zip_path}")
    return 0


def _source_files(root: Path) -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return sorted(
            path.relative_to(root)
            for path in root.rglob("*")
            if path.is_file() and not (set(path.relative_to(root).parts) & ALWAYS_EXCLUDED_PARTS)
        )

    paths = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        relative = Path(raw.decode("utf-8"))
        if not (root / relative).is_file():
            continue
        if set(relative.parts) & ALWAYS_EXCLUDED_PARTS:
            continue
        paths.append(relative)
    return sorted(paths)


def _is_stewardship_only(path: Path) -> bool:
    posix = PurePosixPath(path.as_posix()).as_posix()
    return any(posix == prefix.rstrip("/") or posix.startswith(prefix) for prefix in STEWARDSHIP_ONLY_PREFIXES)


def _build_manifest(root: Path, out: Path, public_files: list[Path]) -> dict[str, object]:
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    records = []
    digest = hashlib.sha256()
    for relative in public_files:
        data = (out / relative).read_bytes()
        file_hash = hashlib.sha256(data).hexdigest()
        path_text = relative.as_posix()
        records.append({"path": path_text, "sha256": file_hash})
        digest.update(path_text.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\n")
    return {
        "format_version": FORMAT_VERSION,
        "package_version": pyproject["project"]["version"],
        "source_commit": _git_commit(root),
        "included_file_count": len(public_files),
        "public_tree_sha256": digest.hexdigest(),
        "files": records,
    }


def _git_commit(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    value = result.stdout.strip()
    return value or None


def _validate_destinations(root: Path, out: Path, zip_path: Path | None) -> None:
    resolved_root = root.resolve()
    if out == resolved_root or resolved_root in out.parents:
        raise SystemExit("Refusing to write the public tree inside the stewardship checkout.")
    if zip_path is not None and (zip_path == resolved_root or resolved_root in zip_path.parents):
        raise SystemExit("Refusing to write the public ZIP inside the stewardship checkout.")
    if zip_path is not None and zip_path == out:
        raise SystemExit("The public tree and ZIP destinations must differ.")


def _prepare_destination(path: Path, *, force: bool) -> None:
    if path.exists():
        if not force:
            raise SystemExit(f"Output already exists: {path}. Use --force to replace it.")
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    path.mkdir(parents=True)


def _prepare_file_destination(path: Path, *, force: bool) -> None:
    if path.exists():
        if not force:
            raise SystemExit(f"Output already exists: {path}. Use --force to replace it.")
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)


def _write_zip(tree: Path, destination: Path) -> None:
    root_name = tree.name
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(tree.rglob("*")):
            if path.is_file():
                arcname = (Path(root_name) / path.relative_to(tree)).as_posix()
                info = zipfile.ZipInfo(arcname, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, path.read_bytes(), compresslevel=9)


if __name__ == "__main__":
    sys.exit(main())
