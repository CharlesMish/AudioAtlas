#!/usr/bin/env python3
"""Extend the frozen-app PE audit with the delivered Windows setup executable."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from build_windows_app import AMD64_MACHINE, SYSTEM_DLLS


def _decode(value: bytes | str) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip()
    return value.strip()


def _version_strings(pe: Any) -> dict[str, str]:
    values: dict[str, str] = {}
    for group in pe.FileInfo or []:
        for entry in group:
            for table in getattr(entry, "StringTable", []):
                values.update({_decode(key): _decode(value) for key, value in table.entries.items()})
    return values


def _manifest_text(pe: Any, pefile: Any) -> str:
    resource_root = getattr(pe, "DIRECTORY_ENTRY_RESOURCE", None)
    if resource_root is None:
        raise SystemExit("Setup executable has no PE resources")
    manifest_id = pefile.RESOURCE_TYPE["RT_MANIFEST"]
    payloads: list[bytes] = []
    for type_entry in resource_root.entries:
        if type_entry.id != manifest_id:
            continue
        for name_entry in type_entry.directory.entries:
            for language_entry in name_entry.directory.entries:
                data = language_entry.data.struct
                payloads.append(pe.get_data(data.OffsetToData, data.Size))
    if len(payloads) != 1:
        raise SystemExit(f"Setup executable must contain one manifest, found {len(payloads)}")
    payload = payloads[0]
    for encoding in ("utf-8-sig", "utf-16"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise SystemExit("Setup manifest is not valid UTF-8 or UTF-16")


def _imports(pe: Any) -> list[str]:
    imported: set[str] = set()
    for attribute in ("DIRECTORY_ENTRY_IMPORT", "DIRECTORY_ENTRY_DELAY_IMPORT"):
        for entry in getattr(pe, attribute, []):
            imported.add(entry.dll.decode("ascii").casefold())
    return sorted(imported)


def _validate_setup_contract(
    *,
    machine: int,
    imports: list[str],
    manifest: str,
    version_strings: dict[str, str],
    signature_status: str,
    expected_version: str,
    expected_build: int,
) -> dict[str, Any]:
    if machine != AMD64_MACHINE:
        raise SystemExit(f"Setup executable is not AMD64: machine={machine:#x}")
    unresolved = [
        name
        for name in imports
        if name not in SYSTEM_DLLS
        and not name.startswith("api-ms-win-")
        and not name.startswith("ext-ms-win-")
    ]
    if unresolved:
        raise SystemExit(f"Setup executable has unresolved non-system imports: {unresolved!r}")
    match = re.search(
        r"<requestedExecutionLevel\s+level=[\"']([^\"']+)[\"']\s+"
        r"uiAccess=[\"']([^\"']+)[\"']\s*/>",
        manifest,
    )
    if match is None or match.groups() != ("asInvoker", "false"):
        raise SystemExit("Setup executable must request asInvoker with uiAccess=false")
    if "requireAdministrator" in manifest or "highestAvailable" in manifest:
        raise SystemExit("Setup executable contains an elevation request")
    if version_strings.get("ProductName") != "AudioAtlas":
        raise SystemExit("Setup ProductName is not AudioAtlas")
    if version_strings.get("ProductVersion") != expected_version:
        raise SystemExit("Setup ProductVersion does not match the candidate version")
    if version_strings.get("FileVersion") != expected_version:
        raise SystemExit("Setup FileVersion does not match the candidate version")
    expected_description = f"AudioAtlas internal Windows candidate build {expected_build}"
    if version_strings.get("FileDescription") != expected_description:
        raise SystemExit("Setup FileDescription does not match the candidate build")
    if signature_status != "NotSigned":
        raise SystemExit(
            f"Internal setup signature status must be NotSigned, got {signature_status!r}"
        )
    return {
        "architecture": "x86_64",
        "imports": imports,
        "requested_execution_level": "asInvoker",
        "ui_access": False,
        "signature_status": "unsigned-internal",
        "version_strings": version_strings,
        "unresolved_imports": [],
    }


def audit_distribution(
    *,
    bundle_audit: Path,
    installer: Path,
    signature_status: str,
    version: str,
    build_number: int,
) -> dict[str, Any]:
    import pefile

    if not bundle_audit.is_file() or not installer.is_file():
        raise SystemExit("Bundle audit and setup executable are required")
    try:
        app = json.loads(bundle_audit.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit("Frozen-app PE audit is invalid") from exc
    if not isinstance(app, dict) or app.get("architecture") != "x86_64":
        raise SystemExit("Frozen-app PE audit has an unexpected architecture")
    pe = pefile.PE(str(installer), fast_load=False)
    try:
        setup = _validate_setup_contract(
            machine=pe.FILE_HEADER.Machine,
            imports=_imports(pe),
            manifest=_manifest_text(pe, pefile),
            version_strings=_version_strings(pe),
            signature_status=signature_status,
            expected_version=version,
            expected_build=build_number,
        )
    finally:
        pe.close()
    return {
        "schema_version": 2,
        "architecture": "x86_64",
        "windows_targets": ["Windows 10 22H2 x64", "Windows 11 x64"],
        "minimum_windows_build": 19045,
        "signing_status": "unsigned-internal",
        "app_bundle": app,
        "installer": setup,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-audit", type=Path, required=True)
    parser.add_argument("--installer", type=Path, required=True)
    parser.add_argument("--signature-status", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--build-number", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    report = audit_distribution(
        bundle_audit=args.bundle_audit,
        installer=args.installer,
        signature_status=args.signature_status,
        version=args.version,
        build_number=args.build_number,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"AudioAtlas Windows distribution audit: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
