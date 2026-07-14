#!/usr/bin/env python3
"""Verify PUBLIC_SNAPSHOT.json against a public AudioAtlas tree."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.public_snapshot import verify_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Public tree root (defaults to this checkout).",
    )
    args = parser.parse_args(argv)
    root = args.root.expanduser().resolve()
    errors = verify_manifest(root)
    if errors:
        print("Public snapshot verification failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"Public snapshot verified: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
