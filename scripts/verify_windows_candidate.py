#!/usr/bin/env python3
"""Verify and optionally extract the exact internal Windows candidate test kits."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

EXPECTED_SCHEMA_VERSION = 2
RESERVED_WINDOWS_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}
INVALID_WINDOWS_CHARACTERS = set('<>:"\\|?*')


class CandidateVerificationError(ValueError):
    """The delivered archive or its evidence does not match the candidate contract."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bytes_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _validate_component(component: str) -> None:
    if not component or component in {".", ".."}:
        raise CandidateVerificationError(f"Unsafe archive component: {component!r}")
    if component.endswith((" ", ".")):
        raise CandidateVerificationError(
            f"Windows trims trailing spaces or periods: {component!r}"
        )
    if any(character in INVALID_WINDOWS_CHARACTERS or ord(character) < 32 for character in component):
        raise CandidateVerificationError(f"Invalid Windows archive component: {component!r}")
    basename = component.split(".", 1)[0].upper()
    if basename in RESERVED_WINDOWS_NAMES:
        raise CandidateVerificationError(f"Reserved Windows archive component: {component!r}")


def _safe_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members: list[zipfile.ZipInfo] = []
    seen: set[str] = set()
    for info in archive.infolist():
        name = info.filename
        if not name or "\\" in name or name.startswith(("/", "\\")):
            raise CandidateVerificationError(f"Unsafe archive path: {name!r}")
        if re.match(r"^[A-Za-z]:", name):
            raise CandidateVerificationError(f"Drive-qualified archive path: {name!r}")
        path = PurePosixPath(name)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            raise CandidateVerificationError(f"Unsafe archive path: {name!r}")
        for part in path.parts:
            _validate_component(part)
        folded = name.casefold()
        if folded in seen:
            raise CandidateVerificationError(
                f"Duplicate case-insensitive archive path: {name!r}"
            )
        seen.add(folded)
        unix_mode = info.external_attr >> 16
        if stat.S_ISLNK(unix_mode):
            raise CandidateVerificationError(f"Archive contains a symlink: {name!r}")
        if info.flag_bits & 0x1:
            raise CandidateVerificationError(f"Archive contains encrypted data: {name!r}")
        if info.is_dir():
            continue
        members.append(info)
    if not members:
        raise CandidateVerificationError("Candidate archive contains no files")
    return members


def _parse_checksum_text(text: str) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for line in text.splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([^/\\]+)", line)
        if match is None:
            raise CandidateVerificationError(f"Malformed checksum line: {line!r}")
        digest, filename = match.groups()
        if filename.casefold() in {name.casefold() for name in checksums}:
            raise CandidateVerificationError(f"Duplicate checksum filename: {filename!r}")
        checksums[filename] = digest
    if not checksums:
        raise CandidateVerificationError("Checksum file contains no entries")
    return checksums


def _validate_manifest(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise CandidateVerificationError("Candidate manifest must be an object")
    required = {
        "schema_version",
        "candidate_id",
        "version",
        "bundle_build",
        "commit",
        "architecture",
        "python_version",
        "windows_targets",
        "minimum_windows_build",
        "installation_scope",
        "default_install_location",
        "requires_administrator",
        "workflow_url",
        "components",
        "signing_status",
        "built_at",
    }
    missing = required - payload.keys()
    if missing:
        raise CandidateVerificationError(f"Candidate manifest is missing: {sorted(missing)!r}")
    if payload["schema_version"] != EXPECTED_SCHEMA_VERSION:
        raise CandidateVerificationError("Unexpected candidate manifest schema")
    if not isinstance(payload["bundle_build"], int) or payload["bundle_build"] <= 0:
        raise CandidateVerificationError("Candidate build number must be positive")
    if not re.fullmatch(r"[0-9a-f]{40}", str(payload["commit"])):
        raise CandidateVerificationError("Candidate commit must be a full lowercase SHA")
    if payload["architecture"] != "x86_64":
        raise CandidateVerificationError("Candidate architecture must be x86_64")
    if payload["minimum_windows_build"] != 19045:
        raise CandidateVerificationError("Candidate minimum Windows build must be 19045")
    if payload["installation_scope"] != "per-user":
        raise CandidateVerificationError("Candidate installation must be per-user")
    if payload["default_install_location"] != r"%LOCALAPPDATA%\Programs\AudioAtlas":
        raise CandidateVerificationError("Candidate default install location is unexpected")
    if payload["requires_administrator"] is not False:
        raise CandidateVerificationError("Candidate must not require administrator access")
    if payload["signing_status"] != "unsigned-internal":
        raise CandidateVerificationError("Candidate signing status must be unsigned-internal")
    components = payload["components"]
    required_components = {
        "installer",
        "portable",
        "demo_audio",
        "pe_audit",
        "license_inventory",
        "rights_notice",
        "acceptance_guide",
    }
    if not isinstance(components, dict) or set(components) != required_components:
        raise CandidateVerificationError("Candidate component inventory is incomplete")
    for label, component in components.items():
        if not isinstance(component, dict) or set(component) != {"filename", "sha256", "bytes"}:
            raise CandidateVerificationError(f"Invalid component identity: {label}")
        if not isinstance(component["filename"], str):
            raise CandidateVerificationError(f"Invalid component filename: {label}")
        _validate_component(component["filename"])
        if not re.fullmatch(r"[0-9a-f]{64}", str(component["sha256"])):
            raise CandidateVerificationError(f"Invalid component hash: {label}")
        if not isinstance(component["bytes"], int) or component["bytes"] < 0:
            raise CandidateVerificationError(f"Invalid component size: {label}")
    return payload


def _expected_files(manifest: dict[str, Any], *, role: str) -> set[str]:
    components = manifest["components"]
    primary = "installer" if role == "installer" else "portable"
    labels = {
        primary,
        "demo_audio",
        "pe_audit",
        "license_inventory",
        "rights_notice",
    }
    return {
        *(components[label]["filename"] for label in labels),
        "DEMO_AND_ACCEPTANCE_GUIDE.md",
        "windows-candidate-manifest.json",
        "SHA256SUMS.txt",
    }


def _verify_archive(path: Path, *, role: str, extract_to: Path | None) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        members = _safe_members(archive)
        roots = {PurePosixPath(info.filename).parts[0] for info in members}
        if len(roots) != 1:
            raise CandidateVerificationError(f"{path.name} must contain exactly one root")
        root = next(iter(roots))
        relative_members = {
            PurePosixPath(info.filename).relative_to(root).as_posix(): info
            for info in members
        }
        if any("/" in name for name in relative_members):
            raise CandidateVerificationError(f"{path.name} contains unexpected nested files")
        manifest_name = "windows-candidate-manifest.json"
        if manifest_name not in relative_members:
            raise CandidateVerificationError(f"{path.name} has no candidate manifest")
        manifest_bytes = archive.read(relative_members[manifest_name])
        try:
            manifest = _validate_manifest(json.loads(manifest_bytes))
        except json.JSONDecodeError as exc:
            raise CandidateVerificationError("Candidate manifest is not valid JSON") from exc
        expected = _expected_files(manifest, role=role)
        if set(relative_members) != expected:
            raise CandidateVerificationError(
                f"{path.name} contents differ: expected={sorted(expected)!r}, "
                f"actual={sorted(relative_members)!r}"
            )
        checksum_info = relative_members["SHA256SUMS.txt"]
        checksums = _parse_checksum_text(archive.read(checksum_info).decode("utf-8"))
        payload_names = set(relative_members) - {"SHA256SUMS.txt"}
        if set(checksums) != payload_names:
            raise CandidateVerificationError(f"{path.name} checksum inventory differs")
        for filename in payload_names:
            payload = archive.read(relative_members[filename])
            if _bytes_sha256(payload) != checksums[filename]:
                raise CandidateVerificationError(f"Hash mismatch inside {path.name}: {filename}")

        component_by_filename = {
            value["filename"]: value for value in manifest["components"].values()
        }
        for filename in payload_names & component_by_filename.keys():
            component = component_by_filename[filename]
            payload = archive.read(relative_members[filename])
            if len(payload) != component["bytes"] or _bytes_sha256(payload) != component["sha256"]:
                raise CandidateVerificationError(
                    f"Manifest component identity differs in {path.name}: {filename}"
                )

        if extract_to is not None:
            destination = extract_to / role
            if destination.exists():
                shutil.rmtree(destination)
            destination.mkdir(parents=True)
            for info in members:
                relative = PurePosixPath(info.filename).relative_to(root)
                target = destination.joinpath(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
        return {
            "filename": path.name,
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
            "role": role,
            "candidate_id": manifest["candidate_id"],
            "manifest_sha256": _bytes_sha256(manifest_bytes),
        }


def _verify_sidecar(path: Path) -> None:
    sidecar = Path(f"{path}.sha256")
    if not sidecar.is_file():
        raise CandidateVerificationError(f"Missing archive checksum: {sidecar.name}")
    checksums = _parse_checksum_text(sidecar.read_text(encoding="utf-8"))
    if checksums != {path.name: _sha256(path)}:
        raise CandidateVerificationError(f"Archive checksum differs: {path.name}")


def verify_candidate(candidate_dir: Path, *, extract_root: Path | None = None) -> dict[str, Any]:
    candidate_dir = candidate_dir.resolve()
    readme = candidate_dir / "README_FIRST.txt"
    if not readme.is_file() or "installer-test-kit" not in readme.read_text(encoding="utf-8"):
        raise CandidateVerificationError("README_FIRST.txt is missing or incomplete")
    roles = {
        "installer": sorted(candidate_dir.glob("*-installer-test-kit.zip")),
        "portable": sorted(candidate_dir.glob("*-portable-test-kit.zip")),
    }
    if any(len(paths) != 1 for paths in roles.values()):
        raise CandidateVerificationError("Expected exactly one installer and one portable test kit")
    reports: list[dict[str, Any]] = []
    for role, paths in roles.items():
        path = paths[0]
        _verify_sidecar(path)
        reports.append(_verify_archive(path, role=role, extract_to=extract_root))
    candidate_ids = {report["candidate_id"] for report in reports}
    manifest_hashes = {report["manifest_sha256"] for report in reports}
    if len(candidate_ids) != 1 or len(manifest_hashes) != 1:
        raise CandidateVerificationError("Installer and portable kits have different identities")
    return {
        "schema_version": 1,
        "candidate_id": next(iter(candidate_ids)),
        "kits": reports,
        "verified": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--extract-root", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    report = verify_candidate(args.candidate_dir, extract_root=args.extract_root)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
