#!/usr/bin/env python3
"""Compare prepared Python distributions with a PyPI-compatible JSON index."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-json-url", required=True)
    parser.add_argument("--dist-dir", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument(
        "--require-present",
        action="store_true",
        help="Fail instead of requesting publication when the version is absent.",
    )
    parser.add_argument(
        "--provenance-base-url",
        help="Require a non-empty PyPI integrity response for every distribution.",
    )
    return parser.parse_args()


def distribution_hashes(dist_dir: Path) -> dict[str, str]:
    files = sorted([*dist_dir.glob("*.whl"), *dist_dir.glob("*.tar.gz")])
    if len(files) != 2 or len({path.name for path in files}) != 2:
        raise ValueError("Expected exactly one wheel and one source distribution.")
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in files
    }


def fetch_index(url: str) -> dict[str, Any] | None:
    _require_https_url(url)
    try:
        with urllib.request.urlopen(url, timeout=30) as response:  # nosec B310
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise RuntimeError(f"Package index returned HTTP {exc.code}.") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Could not read the package-index JSON response.") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Package-index JSON must be an object.")
    return payload


def compare_release(
    payload: dict[str, Any] | None,
    *,
    version: str,
    expected: dict[str, str],
) -> str:
    if payload is None:
        return "absent"
    releases = payload.get("releases")
    if not isinstance(releases, dict):
        raise ValueError("Package-index JSON lacks a releases mapping.")
    files = releases.get(version)
    if not files:
        return "absent"
    if not isinstance(files, list):
        raise ValueError(f"Indexed release {version!r} has an invalid file list.")
    indexed: dict[str, str] = {}
    for entry in files:
        if not isinstance(entry, dict):
            raise ValueError(f"Indexed release {version!r} has an invalid file entry.")
        filename = entry.get("filename")
        digests = entry.get("digests")
        sha256 = digests.get("sha256") if isinstance(digests, dict) else None
        if not isinstance(filename, str) or not isinstance(sha256, str):
            raise ValueError(f"Indexed release {version!r} lacks a filename or SHA-256.")
        if filename in indexed:
            raise ValueError(f"Indexed release {version!r} repeats {filename!r}.")
        indexed[filename] = sha256
    if indexed != expected:
        missing = sorted(set(expected) - set(indexed))
        unexpected = sorted(set(indexed) - set(expected))
        changed = sorted(
            name for name in set(expected) & set(indexed) if expected[name] != indexed[name]
        )
        raise ValueError(
            f"Indexed release {version!r} conflicts with prepared distributions: "
            f"missing={missing!r}, unexpected={unexpected!r}, changed={changed!r}."
        )
    return "exact"


def require_provenance(base_url: str, *, version: str, filenames: set[str]) -> None:
    for filename in sorted(filenames):
        url = (
            f"{base_url.rstrip('/')}/{urllib.parse.quote(version, safe='')}/"
            f"{urllib.parse.quote(filename, safe='')}/provenance"
        )
        _require_https_url(url)
        try:
            with urllib.request.urlopen(url, timeout=30) as response:  # nosec B310
                payload = json.load(response)
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Could not verify provenance for {filename!r}.") from exc
        bundles = payload.get("attestation_bundles") if isinstance(payload, dict) else None
        if not isinstance(bundles, list) or not bundles:
            raise ValueError(f"Distribution {filename!r} has no published attestation bundle.")


def _require_https_url(url: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username is not None:
        raise ValueError("Package-index URLs must be unauthenticated HTTPS URLs.")


def write_github_output(name: str, value: str) -> None:
    destination = os.environ.get("GITHUB_OUTPUT")
    if destination:
        with Path(destination).open("a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def main() -> int:
    args = parse_args()
    expected = distribution_hashes(args.dist_dir)
    state = compare_release(
        fetch_index(args.index_json_url), version=args.version, expected=expected
    )
    if args.require_present and state != "exact":
        raise SystemExit(f"Release {args.version!r} is not present on the package index.")
    if args.provenance_base_url:
        if state != "exact":
            raise SystemExit("Provenance cannot be verified before the exact release exists.")
        require_provenance(
            args.provenance_base_url,
            version=args.version,
            filenames=set(expected),
        )
    publish_needed = state == "absent"
    write_github_output("publish_needed", str(publish_needed).lower())
    write_github_output("index_state", state)
    print(f"Package-index state for {args.version}: {state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
