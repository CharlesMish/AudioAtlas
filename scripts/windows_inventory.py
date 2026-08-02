"""Validate a frozen Windows app against its canonical native-image inventory."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


class InventoryVerificationError(ValueError):
    """The app tree does not match its audited native inventory."""


def _stream_sha256(stream: BinaryIO) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        size += len(chunk)
        digest.update(chunk)
    return digest.hexdigest(), size


def stream_is_pe(stream: BinaryIO, *, size: int, name: str) -> bool:
    """Identify PE images by their DOS and PE signatures, independent of suffix."""

    dos_header = stream.read(64)
    if not dos_header.startswith(b"MZ"):
        return False
    if len(dos_header) < 64:
        raise InventoryVerificationError(f"Malformed DOS header in app file: {name}")
    pe_offset = int.from_bytes(dos_header[60:64], "little")
    if pe_offset < 64 or pe_offset > size - 24:
        raise InventoryVerificationError(f"Malformed PE header offset in app file: {name}")
    stream.seek(pe_offset)
    if stream.read(4) != b"PE\x00\x00":
        raise InventoryVerificationError(f"Malformed PE signature in app file: {name}")
    return True


def validate_inventory_payload(payload: Any) -> tuple[str, dict[str, dict[str, Any]]]:
    """Validate the native audit structure and return its root and path records."""

    if not isinstance(payload, dict) or payload.get("schema_version") != 2:
        raise InventoryVerificationError("Native inventory has an unsupported schema")
    if payload.get("architecture") != "x86_64":
        raise InventoryVerificationError("Native inventory architecture is not x86_64")
    records = payload.get("pe_files")
    if not isinstance(records, list) or not records:
        raise InventoryVerificationError("Native inventory contains no PE records")
    by_path: dict[str, dict[str, Any]] = {}
    folded: set[str] = set()
    required = {
        "path",
        "size",
        "sha256",
        "pe_classification",
        "architecture",
        "imports",
        "resolved_imports",
    }
    for record in records:
        if not isinstance(record, dict) or set(record) != required:
            raise InventoryVerificationError("Native inventory contains a malformed PE record")
        name = record["path"]
        if not isinstance(name, str):
            raise InventoryVerificationError("Native inventory contains a non-string path")
        path = PurePosixPath(name)
        if (
            not name
            or "\\" in name
            or path.is_absolute()
            or path.as_posix() != name
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise InventoryVerificationError(f"Native inventory path is unsafe: {name!r}")
        if name.casefold() in folded:
            raise InventoryVerificationError(
                f"Native inventory path is case-insensitively ambiguous: {name!r}"
            )
        folded.add(name.casefold())
        if (
            not isinstance(record["size"], int)
            or isinstance(record["size"], bool)
            or record["size"] < 0
            or not SHA256_PATTERN.fullmatch(str(record["sha256"]))
            or record["architecture"] != "x86_64"
            or not isinstance(record["imports"], list)
            or not isinstance(record["resolved_imports"], list)
        ):
            raise InventoryVerificationError(f"Native inventory record is invalid: {name!r}")
        by_path[name] = record
    canonical = json.dumps(
        records, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    root = hashlib.sha256(canonical).hexdigest()
    if payload.get("inventory_root_sha256") != root:
        raise InventoryVerificationError("Native inventory root does not match its records")
    return root, by_path


def verify_file_inventory(files: Iterable[tuple[str, int, BinaryIO]], payload: Any) -> str:
    """Compare streamed app files with the exact native record set and identities."""

    root, expected = validate_inventory_payload(payload)
    actual: dict[str, tuple[int, str]] = {}
    folded: set[str] = set()
    for name, declared_size, stream in files:
        if name.casefold() in folded:
            raise InventoryVerificationError(
                f"App tree path is case-insensitively ambiguous: {name!r}"
            )
        folded.add(name.casefold())
        if not stream_is_pe(stream, size=declared_size, name=name):
            continue
        stream.seek(0)
        digest, actual_size = _stream_sha256(stream)
        if actual_size != declared_size:
            raise InventoryVerificationError(f"App file changed while reading: {name!r}")
        actual[name] = (actual_size, digest)
    if set(actual) != set(expected):
        raise InventoryVerificationError(
            "Native app paths differ from the audited inventory: "
            f"expected={sorted(expected)!r}, actual={sorted(actual)!r}"
        )
    for name, (size, digest) in actual.items():
        record = expected[name]
        if size != record["size"] or digest != record["sha256"]:
            raise InventoryVerificationError(
                f"Native app file differs from the audited inventory: {name}"
            )
    return root


def verify_app_inventory(app: Path, payload: Any) -> str:
    """Bind a local app directory to an already-created native inventory."""

    if app.is_symlink() or not app.is_dir():
        raise InventoryVerificationError("Native inventory requires a real app directory")
    app = app.resolve(strict=True)
    entries = sorted(app.rglob("*"))
    symlinks = [path.relative_to(app).as_posix() for path in entries if path.is_symlink()]
    if symlinks:
        raise InventoryVerificationError(f"App tree contains symlinks: {symlinks!r}")

    def opened_files() -> Iterable[tuple[str, int, BinaryIO]]:
        for path in entries:
            if path.is_file():
                with path.open("rb") as stream:
                    yield path.relative_to(app).as_posix(), path.stat().st_size, stream

    return verify_file_inventory(opened_files(), payload)
