#!/usr/bin/env python3
"""Verify PUBLIC_SNAPSHOT.json against a public AudioAtlas tree."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

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


def _clean_public_commit(root: Path) -> str:
    """Return HEAD only when it exactly supplies the covered public files."""

    try:
        top_level = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        head = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        tracked_diff = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "diff",
                "--quiet",
                "HEAD",
                "--",
                ".",
                f":(exclude){MANIFEST_NAME}",
            ],
            check=False,
        ).returncode
        untracked = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--others", "--exclude-standard"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"Cannot identify a committed public source tree: {exc}") from exc

    if Path(top_level).resolve() != root:
        raise SystemExit("Refusing to regenerate outside the root of a Git checkout.")
    if tracked_diff != 0 or untracked:
        raise SystemExit(
            "Refusing to regenerate from uncommitted public files; commit covered content first."
        )
    return head


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Public tree root (defaults to this checkout).",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Regenerate an existing manifest from a clean committed public tree.",
    )
    args = parser.parse_args(argv)
    root = args.root.expanduser().resolve()
    expected_source_commit = None
    if args.write:
        if not (root / MANIFEST_NAME).is_file():
            raise SystemExit("Refusing to create a manifest outside an existing public tree.")
        expected_source_commit = _clean_public_commit(root)
        manifest = build_manifest(
            root,
            source_files(root),
            package_version=package_version(root),
            source_commit=expected_source_commit,
        )
        write_manifest(root / MANIFEST_NAME, manifest)

    errors = verify_manifest(root, expected_source_commit=expected_source_commit)
    if errors:
        print("Public snapshot verification failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    action = "regenerated and verified" if args.write else "verified"
    print(f"Public snapshot {action}: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
