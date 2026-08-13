#!/usr/bin/env python3
"""Verify and optionally extract the exact internal Windows candidate test kits."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import stat
import tempfile
import zipfile
import zlib
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO
from urllib.parse import urlsplit

try:
    from windows_inventory import (
        InventoryVerificationError,
        validate_inventory_payload,
        verify_app_inventory,
        verify_file_inventory,
    )
except ModuleNotFoundError:  # Imported as a module from the repository root in tests.
    from scripts.windows_inventory import (
        InventoryVerificationError,
        validate_inventory_payload,
        verify_app_inventory,
        verify_file_inventory,
    )

EXPECTED_SCHEMA_VERSION = 3
EXPECTED_WINDOWS_TARGETS = ["Windows 10 22H2 x64", "Windows 11 x64"]
MAX_CANDIDATE_ARCHIVE_BYTES = 200 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 20_000
MAX_MEMBER_UNCOMPRESSED_BYTES = 400 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 600 * 1024 * 1024
MAX_COMPRESSION_RATIO = 2_000
MAX_METADATA_BYTES = 2 * 1024 * 1024
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
        raise CandidateVerificationError(f"Windows trims trailing spaces or periods: {component!r}")
    if any(
        character in INVALID_WINDOWS_CHARACTERS or ord(character) < 32 for character in component
    ):
        raise CandidateVerificationError(f"Invalid Windows archive component: {component!r}")
    basename = component.split(".", 1)[0].upper()
    if basename in RESERVED_WINDOWS_NAMES:
        raise CandidateVerificationError(f"Reserved Windows archive component: {component!r}")


def _safe_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    infos = archive.infolist()
    if len(infos) > MAX_ARCHIVE_MEMBERS:
        raise CandidateVerificationError(
            f"Archive member count exceeds limit {MAX_ARCHIVE_MEMBERS}"
        )
    total_size = 0
    members: list[zipfile.ZipInfo] = []
    seen: set[str] = set()
    for info in infos:
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
            raise CandidateVerificationError(f"Duplicate case-insensitive archive path: {name!r}")
        seen.add(folded)
        unix_mode = info.external_attr >> 16
        if stat.S_ISLNK(unix_mode):
            raise CandidateVerificationError(f"Archive contains a symlink: {name!r}")
        if info.flag_bits & 0x1:
            raise CandidateVerificationError(f"Archive contains encrypted data: {name!r}")
        if info.is_dir():
            continue
        if info.file_size > MAX_MEMBER_UNCOMPRESSED_BYTES:
            raise CandidateVerificationError(f"Archive member exceeds uncompressed limit: {name!r}")
        total_size += info.file_size
        if total_size > MAX_TOTAL_UNCOMPRESSED_BYTES:
            raise CandidateVerificationError("Archive total uncompressed size exceeds limit")
        ratio = info.file_size / max(info.compress_size, 1)
        if ratio > MAX_COMPRESSION_RATIO:
            raise CandidateVerificationError(
                f"Archive member compression ratio exceeds limit: {name!r}"
            )
        members.append(info)
    if not members:
        raise CandidateVerificationError("Candidate archive contains no files")
    return members


def _parse_checksum_text(text: str) -> dict[str, str]:
    checksums: dict[str, str] = {}
    folded: set[str] = set()
    for line in text.splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([^/\\]+)", line)
        if match is None:
            raise CandidateVerificationError(f"Malformed checksum line: {line!r}")
        digest, filename = match.groups()
        if filename.casefold() in folded:
            raise CandidateVerificationError(f"Duplicate checksum filename: {filename!r}")
        folded.add(filename.casefold())
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
        "native_inventory",
        "portable_filename",
        "portable_sha256",
        "installer_filename",
        "installer_sha256",
        "demo_audio_sha256",
        "pe_audit_sha256",
        "license_inventory_sha256",
        "signing_status",
        "built_at",
    }
    if set(payload) != required:
        raise CandidateVerificationError(
            "Candidate manifest fields differ: "
            f"missing={sorted(required - payload.keys())!r}, "
            f"unexpected={sorted(payload.keys() - required)!r}"
        )
    if payload["schema_version"] != EXPECTED_SCHEMA_VERSION:
        raise CandidateVerificationError("Unexpected candidate manifest schema")
    version = payload["version"]
    build = payload["bundle_build"]
    commit = payload["commit"]
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+a\d+", version):
        raise CandidateVerificationError("Candidate version is invalid")
    if not isinstance(build, int) or isinstance(build, bool) or build <= 0:
        raise CandidateVerificationError("Candidate build number must be positive")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise CandidateVerificationError("Candidate commit must be a full lowercase SHA")
    if payload["candidate_id"] != f"{version}-build-{build}-{commit[:12]}":
        raise CandidateVerificationError("Candidate identity is inconsistent")
    if payload["architecture"] != "x86_64" or payload["python_version"] != "3.11":
        raise CandidateVerificationError("Candidate runtime identity is unexpected")
    if payload["windows_targets"] != EXPECTED_WINDOWS_TARGETS:
        raise CandidateVerificationError("Candidate Windows targets are unexpected")
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
    workflow = urlsplit(payload["workflow_url"] if isinstance(payload["workflow_url"], str) else "")
    if (
        workflow.scheme != "https"
        or not workflow.netloc
        or workflow.username is not None
        or workflow.password is not None
        or workflow.fragment
    ):
        raise CandidateVerificationError("Candidate workflow URL must be HTTPS")
    try:
        built_at = datetime.fromisoformat(payload["built_at"])
    except (TypeError, ValueError) as exc:
        raise CandidateVerificationError("Candidate timestamp is malformed") from exc
    if built_at.tzinfo is None or built_at.utcoffset() is None:
        raise CandidateVerificationError("Candidate timestamp must include a timezone")

    components = payload["components"]
    labels = {
        "installer",
        "portable",
        "demo_audio",
        "pe_audit",
        "license_inventory",
        "rights_notice",
        "acceptance_guide",
    }
    if not isinstance(components, dict) or set(components) != labels:
        raise CandidateVerificationError("Candidate component inventory is incomplete")
    prefix = f"AudioAtlas-{version}-build-{build}-windows-x64-INTERNAL"
    expected_filenames = {
        "installer": f"{prefix}-setup.exe",
        "portable": f"{prefix}-portable.zip",
        "demo_audio": "audioatlas_demo.wav",
        "pe_audit": "windows-pe-audit.json",
        "license_inventory": "THIRD_PARTY_LICENSES.txt",
        "rights_notice": "AUDIO_RIGHTS.md",
        "acceptance_guide": "DEMO_AND_ACCEPTANCE_GUIDE.md",
    }
    seen_names: set[str] = set()
    for label in sorted(labels):
        component = components[label]
        if not isinstance(component, dict) or set(component) != {"filename", "sha256", "bytes"}:
            raise CandidateVerificationError(f"Invalid component identity: {label}")
        filename = component["filename"]
        if filename != expected_filenames[label]:
            raise CandidateVerificationError(f"Unexpected delivered filename for {label}")
        _validate_component(filename)
        if filename.casefold() in seen_names:
            raise CandidateVerificationError("Candidate component filenames are ambiguous")
        seen_names.add(filename.casefold())
        if not re.fullmatch(r"[0-9a-f]{64}", str(component["sha256"])):
            raise CandidateVerificationError(f"Invalid component hash: {label}")
        if (
            not isinstance(component["bytes"], int)
            or isinstance(component["bytes"], bool)
            or component["bytes"] < 0
        ):
            raise CandidateVerificationError(f"Invalid component size: {label}")
    flat_fields = {
        "portable_filename": ("portable", "filename"),
        "portable_sha256": ("portable", "sha256"),
        "installer_filename": ("installer", "filename"),
        "installer_sha256": ("installer", "sha256"),
        "demo_audio_sha256": ("demo_audio", "sha256"),
        "pe_audit_sha256": ("pe_audit", "sha256"),
        "license_inventory_sha256": ("license_inventory", "sha256"),
    }
    for field, (label, attribute) in flat_fields.items():
        if payload[field] != components[label][attribute]:
            raise CandidateVerificationError(f"Candidate field is inconsistent: {field}")

    native = payload["native_inventory"]
    if (
        not isinstance(native, dict)
        or set(native) != {"schema_version", "root_sha256", "bindings"}
        or native["schema_version"] != 1
        or not re.fullmatch(r"[0-9a-f]{64}", str(native["root_sha256"]))
        or not isinstance(native["bindings"], dict)
        or set(native["bindings"])
        != {"installer_source_app", "portable_source_app", "portable_archive_app"}
        or set(native["bindings"].values()) != {native["root_sha256"]}
    ):
        raise CandidateVerificationError("Candidate native inventory binding is invalid")
    return payload


def _expected_labels(*, role: str) -> set[str]:
    return {
        "installer" if role == "installer" else "portable",
        "demo_audio",
        "pe_audit",
        "license_inventory",
        "rights_notice",
        "acceptance_guide",
    }


def _expected_files(manifest: dict[str, Any], *, role: str) -> set[str]:
    return {
        *(manifest["components"][label]["filename"] for label in _expected_labels(role=role)),
        "windows-candidate-manifest.json",
        "SHA256SUMS.txt",
    }


def _stream_member(
    archive: zipfile.ZipFile, info: zipfile.ZipInfo, output: BinaryIO | None = None
) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    try:
        with archive.open(info) as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                size += len(chunk)
                if size > info.file_size or size > MAX_MEMBER_UNCOMPRESSED_BYTES:
                    raise CandidateVerificationError(
                        f"Archive member exceeded declared size: {info.filename!r}"
                    )
                digest.update(chunk)
                if output is not None:
                    output.write(chunk)
    except (zipfile.BadZipFile, RuntimeError, EOFError, OSError, zlib.error) as exc:
        raise CandidateVerificationError(f"Corrupt archive member: {info.filename!r}") from exc
    if size != info.file_size:
        raise CandidateVerificationError(f"Archive member size differs: {info.filename!r}")
    return digest.hexdigest(), size


def _read_metadata(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    if info.file_size > MAX_METADATA_BYTES:
        raise CandidateVerificationError(f"Metadata member is too large: {info.filename!r}")
    output = io.BytesIO()
    _stream_member(archive, info, output)
    return output.getvalue()


def _validate_distribution_audit(
    payload: Any,
    expected_root: str,
    *,
    expected_version: str,
    expected_build: int,
) -> dict[str, Any]:
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != 3
        or payload.get("architecture") != "x86_64"
        or payload.get("windows_targets") != EXPECTED_WINDOWS_TARGETS
        or payload.get("minimum_windows_build") != 19045
        or payload.get("signing_status") != "unsigned-internal"
        or not isinstance(payload.get("installer"), dict)
        or not isinstance(payload.get("app_bundle"), dict)
        or payload["app_bundle"].get("version") != expected_version
        or payload["app_bundle"].get("bundle_build") != expected_build
        or payload["installer"].get("version_strings", {}).get("ProductVersion") != expected_version
        or payload["installer"].get("version_strings", {}).get("FileVersion") != expected_version
        or payload["installer"].get("source_app_inventory_root_sha256") != expected_root
    ):
        raise CandidateVerificationError("Windows distribution audit contract is invalid")
    try:
        root, _ = validate_inventory_payload(payload.get("app_bundle"))
    except InventoryVerificationError as exc:
        raise CandidateVerificationError(f"Windows native inventory is invalid: {exc}") from exc
    if root != expected_root:
        raise CandidateVerificationError("Windows native inventory root differs from candidate")
    return payload


@contextmanager
def _open_bounded_zip(path: Path) -> Iterator[zipfile.ZipFile]:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise CandidateVerificationError(f"Candidate archive is unavailable: {path.name}") from exc
    if size > MAX_CANDIDATE_ARCHIVE_BYTES:
        raise CandidateVerificationError(
            f"Archive size exceeds limit {MAX_CANDIDATE_ARCHIVE_BYTES}: {path.name}"
        )
    try:
        with zipfile.ZipFile(path) as archive:
            yield archive
    except (zipfile.BadZipFile, OSError) as exc:
        raise CandidateVerificationError(f"Candidate archive is corrupt: {path.name}") from exc


def _extract_transactionally(
    archive: zipfile.ZipFile,
    members: list[zipfile.ZipInfo],
    *,
    root: str,
    destination: Path,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}-partial-", dir=destination.parent)
    )
    try:
        for info in members:
            relative = PurePosixPath(info.filename).relative_to(root)
            target = temporary.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as output:
                _stream_member(archive, info, output)
        if destination.exists() or destination.is_symlink():
            raise CandidateVerificationError(
                f"Extraction destination already exists: {destination.name}"
            )
        temporary.rename(destination)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _verify_portable_archive(
    path: Path,
    *,
    audit: dict[str, Any],
    expected_root: str,
    extract_to: Path | None,
) -> None:
    with _open_bounded_zip(path) as archive:
        members = _safe_members(archive)
        roots = {PurePosixPath(info.filename).parts[0] for info in members}
        if roots != {"AudioAtlas"}:
            raise CandidateVerificationError("Portable archive must contain the AudioAtlas root")

        def opened_files() -> Iterator[tuple[str, int, BinaryIO]]:
            for info in members:
                relative = PurePosixPath(info.filename).relative_to("AudioAtlas").as_posix()
                with archive.open(info) as stream:
                    yield relative, info.file_size, stream

        try:
            root = verify_file_inventory(opened_files(), audit["app_bundle"])
        except (InventoryVerificationError, zipfile.BadZipFile, RuntimeError, zlib.error) as exc:
            raise CandidateVerificationError(
                f"Portable app differs from native inventory: {exc}"
            ) from exc
        if root != expected_root:
            raise CandidateVerificationError("Portable app native inventory root differs")
        if extract_to is not None:
            destination = extract_to / "portable-app"
            _extract_transactionally(
                archive, members, root="AudioAtlas", destination=destination / "AudioAtlas"
            )
            try:
                extracted_root = verify_app_inventory(
                    destination / "AudioAtlas", audit["app_bundle"]
                )
            except InventoryVerificationError as exc:
                shutil.rmtree(destination, ignore_errors=True)
                raise CandidateVerificationError(
                    f"Extracted portable app differs from native inventory: {exc}"
                ) from exc
            if extracted_root != expected_root:
                shutil.rmtree(destination, ignore_errors=True)
                raise CandidateVerificationError("Extracted portable inventory root differs")


def _verify_archive(
    path: Path,
    *,
    role: str,
    authoritative_manifest_bytes: bytes,
    authoritative_manifest: dict[str, Any],
    extract_to: Path | None,
) -> dict[str, Any]:
    with _open_bounded_zip(path) as archive:
        members = _safe_members(archive)
        roots = {PurePosixPath(info.filename).parts[0] for info in members}
        if len(roots) != 1:
            raise CandidateVerificationError(f"{path.name} must contain exactly one root")
        root = next(iter(roots))
        relative_members = {
            PurePosixPath(info.filename).relative_to(root).as_posix(): info for info in members
        }
        if any("/" in name for name in relative_members):
            raise CandidateVerificationError(f"{path.name} contains unexpected nested files")
        manifest_name = "windows-candidate-manifest.json"
        if manifest_name not in relative_members:
            raise CandidateVerificationError(f"{path.name} has no candidate manifest")
        manifest_bytes = _read_metadata(archive, relative_members[manifest_name])
        if manifest_bytes != authoritative_manifest_bytes:
            raise CandidateVerificationError(
                f"{path.name} manifest differs from the authoritative manifest"
            )
        expected = _expected_files(authoritative_manifest, role=role)
        if set(relative_members) != expected:
            raise CandidateVerificationError(
                f"{path.name} contents differ: expected={sorted(expected)!r}, "
                f"actual={sorted(relative_members)!r}"
            )
        checksum_bytes = _read_metadata(archive, relative_members["SHA256SUMS.txt"])
        try:
            checksums = _parse_checksum_text(checksum_bytes.decode("utf-8"))
        except UnicodeDecodeError as exc:
            raise CandidateVerificationError("Checksum file is not UTF-8") from exc
        payload_names = set(relative_members) - {"SHA256SUMS.txt"}
        if set(checksums) != payload_names:
            raise CandidateVerificationError(f"{path.name} checksum inventory differs")

        identities: dict[str, tuple[str, int]] = {}
        for filename in sorted(payload_names):
            identities[filename] = _stream_member(archive, relative_members[filename])
            if identities[filename][0] != checksums[filename]:
                raise CandidateVerificationError(f"Hash mismatch inside {path.name}: {filename}")
        components = authoritative_manifest["components"]
        for label in sorted(_expected_labels(role=role)):
            component = components[label]
            filename = component["filename"]
            if filename not in identities:
                raise CandidateVerificationError(
                    f"Required manifest label is absent from {path.name}: {label}"
                )
            digest, size = identities[filename]
            if digest != component["sha256"] or size != component["bytes"]:
                raise CandidateVerificationError(
                    f"Component differs from the authoritative manifest in {path.name}: {label}"
                )

        audit_component = components["pe_audit"]
        try:
            audit_payload = json.loads(
                _read_metadata(archive, relative_members[audit_component["filename"]])
            )
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise CandidateVerificationError(
                "Windows distribution audit is not valid JSON"
            ) from exc
        expected_root = authoritative_manifest["native_inventory"]["root_sha256"]
        audit = _validate_distribution_audit(
            audit_payload,
            expected_root,
            expected_version=authoritative_manifest["version"],
            expected_build=authoritative_manifest["bundle_build"],
        )

        if extract_to is not None:
            _extract_transactionally(archive, members, root=root, destination=extract_to / role)
        if role == "portable":
            portable_name = components["portable"]["filename"]
            if extract_to is not None:
                portable_path = extract_to / role / portable_name
                _verify_portable_archive(
                    portable_path,
                    audit=audit,
                    expected_root=expected_root,
                    extract_to=extract_to,
                )
            else:
                with tempfile.TemporaryDirectory(prefix="audioatlas-portable-verify-") as temp:
                    portable_path = Path(temp) / portable_name
                    with portable_path.open("wb") as output:
                        _stream_member(archive, relative_members[portable_name], output)
                    _verify_portable_archive(
                        portable_path,
                        audit=audit,
                        expected_root=expected_root,
                        extract_to=None,
                    )
        return {
            "filename": path.name,
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
            "role": role,
            "candidate_id": authoritative_manifest["candidate_id"],
            "manifest_sha256": _bytes_sha256(authoritative_manifest_bytes),
            "native_inventory_root_sha256": expected_root,
        }


def _verify_sidecar(path: Path) -> None:
    if path.stat().st_size > MAX_CANDIDATE_ARCHIVE_BYTES:
        raise CandidateVerificationError(
            f"Archive size exceeds limit {MAX_CANDIDATE_ARCHIVE_BYTES}: {path.name}"
        )
    sidecar = Path(f"{path}.sha256")
    if not sidecar.is_file() or sidecar.stat().st_size > MAX_METADATA_BYTES:
        raise CandidateVerificationError(f"Missing or oversized archive checksum: {sidecar.name}")
    try:
        checksums = _parse_checksum_text(sidecar.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise CandidateVerificationError("Archive checksum is not UTF-8") from exc
    if checksums != {path.name: _sha256(path)}:
        raise CandidateVerificationError(f"Archive checksum differs: {path.name}")


def _refuse_existing_extract_root(extract_root: Path) -> None:
    try:
        mode = extract_root.lstat().st_mode
    except FileNotFoundError:
        return
    except OSError as exc:
        raise CandidateVerificationError(
            f"Extraction destination cannot be inspected: {extract_root.name}"
        ) from exc

    if stat.S_ISLNK(mode):
        target_type = "symlink"
    elif stat.S_ISREG(mode):
        target_type = "file"
    elif stat.S_ISDIR(mode):
        try:
            target_type = (
                "nonempty directory" if any(extract_root.iterdir()) else "directory"
            )
        except OSError as exc:
            raise CandidateVerificationError(
                f"Extraction destination cannot be inspected: {extract_root.name}"
            ) from exc
    else:
        target_type = "unsupported target type"
    raise CandidateVerificationError(
        f"Extraction destination already exists as a {target_type}: {extract_root.name}"
    )


def verify_candidate(candidate_dir: Path, *, extract_root: Path | None = None) -> dict[str, Any]:
    candidate_dir = candidate_dir.resolve()
    if extract_root is not None:
        _refuse_existing_extract_root(extract_root)
    readme = candidate_dir / "README_FIRST.txt"
    if (
        not readme.is_file()
        or readme.is_symlink()
        or readme.stat().st_size > MAX_METADATA_BYTES
        or "installer-test-kit" not in readme.read_text(encoding="utf-8")
    ):
        raise CandidateVerificationError("README_FIRST.txt is missing or incomplete")
    authoritative_path = candidate_dir / "windows-candidate-manifest.json"
    if (
        not authoritative_path.is_file()
        or authoritative_path.is_symlink()
        or authoritative_path.stat().st_size > MAX_METADATA_BYTES
    ):
        raise CandidateVerificationError("Authoritative candidate manifest is missing")
    authoritative_bytes = authoritative_path.read_bytes()
    try:
        authoritative = _validate_manifest(json.loads(authoritative_bytes))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CandidateVerificationError(
            "Authoritative candidate manifest is not valid JSON"
        ) from exc
    roles = {
        "installer": sorted(candidate_dir.glob("*-installer-test-kit.zip")),
        "portable": sorted(candidate_dir.glob("*-portable-test-kit.zip")),
    }
    if any(len(paths) != 1 for paths in roles.values()):
        raise CandidateVerificationError("Expected exactly one installer and one portable test kit")
    extraction_staging: Path | None = None
    if extract_root is not None:
        extract_root.parent.mkdir(parents=True, exist_ok=True)
        extraction_staging = Path(
            tempfile.mkdtemp(prefix=f".{extract_root.name}-partial-", dir=extract_root.parent)
        )
    reports: list[dict[str, Any]] = []
    try:
        for role, paths in roles.items():
            path = paths[0]
            if path.is_symlink():
                raise CandidateVerificationError(
                    f"Candidate kit must not be a symlink: {path.name}"
                )
            _verify_sidecar(path)
            reports.append(
                _verify_archive(
                    path,
                    role=role,
                    authoritative_manifest_bytes=authoritative_bytes,
                    authoritative_manifest=authoritative,
                    extract_to=extraction_staging,
                )
            )
        if extraction_staging is not None:
            _refuse_existing_extract_root(extract_root)
            extraction_staging.rename(extract_root)
    except BaseException:
        if extraction_staging is not None:
            shutil.rmtree(extraction_staging, ignore_errors=True)
        raise
    return {
        "schema_version": 2,
        "candidate_id": authoritative["candidate_id"],
        "native_inventory_root_sha256": authoritative["native_inventory"]["root_sha256"],
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
