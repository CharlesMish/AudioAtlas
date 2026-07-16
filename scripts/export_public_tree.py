#!/usr/bin/env python3
"""Export a deterministic, user-facing AudioAtlas source tree.

The canonical stewardship checkout retains internal review and calibration
material. This exporter produces the Git-facing public tree without forking the
implementation or editing source files in place.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.public_snapshot import (
    MANIFEST_NAME,
    build_manifest,
    package_version,
    source_files,
    verify_manifest,
    write_manifest,
)

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
    source_commit = _committed_public_source(root)
    _prepare_destination(out, force=args.force)
    if zip_path is not None:
        _prepare_file_destination(zip_path, force=args.force)

    files = source_files(root)
    public_files = [path for path in files if not _is_stewardship_only(path)]
    for relative in public_files:
        source = root / relative
        destination = out / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    manifest = build_manifest(
        out,
        public_files,
        package_version=package_version(root),
        source_commit=source_commit,
    )
    manifest_path = out / MANIFEST_NAME
    write_manifest(manifest_path, manifest)
    errors = verify_manifest(out, expected_source_commit=source_commit)
    if errors:
        details = "\n".join(f"- {error}" for error in errors)
        raise SystemExit(f"Generated public snapshot failed verification:\n{details}")

    if zip_path is not None:
        _write_zip(out, zip_path)

    print(f"Public AudioAtlas tree: {out}")
    print(f"Included files: {manifest['included_file_count']}")
    print(f"Tree SHA-256: {manifest['public_tree_sha256']}")
    if zip_path is not None:
        print(f"Public source ZIP: {zip_path}")
    return 0


def _is_stewardship_only(path: Path) -> bool:
    posix = PurePosixPath(path.as_posix()).as_posix()
    return any(posix == prefix.rstrip("/") or posix.startswith(prefix) for prefix in STEWARDSHIP_ONLY_PREFIXES)


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


def _committed_public_source(root: Path) -> str:
    """Return HEAD only when every tracked public path matches that commit."""

    source_commit = _git_commit(root)
    if source_commit is None:
        raise SystemExit("Cannot export without a committed stewardship Git checkout.")
    try:
        top_level = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        changed = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "diff",
                "--no-renames",
                "--name-only",
                "-z",
                "HEAD",
                "--",
                ".",
            ],
            check=True,
            capture_output=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"Cannot verify committed public source files: {exc}") from exc

    if Path(top_level).resolve() != root.resolve():
        raise SystemExit("Refusing to export outside the root of the stewardship checkout.")
    dirty_public_paths = sorted(
        Path(raw.decode("utf-8"))
        for raw in changed.split(b"\0")
        if raw and not _is_stewardship_only(Path(raw.decode("utf-8")))
    )
    if dirty_public_paths:
        rendered = ", ".join(path.as_posix() for path in dirty_public_paths)
        raise SystemExit(
            "Refusing to export public files that differ from stewardship HEAD. "
            f"Commit the covered changes first: {rendered}"
        )
    return source_commit


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
                info.create_system = 3
                info.compress_type = zipfile.ZIP_DEFLATED
                mode = 0o100755 if path.suffix.lower() == ".command" else 0o100644
                info.external_attr = mode << 16
                archive.writestr(info, path.read_bytes(), compresslevel=9)


if __name__ == "__main__":
    sys.exit(main())
