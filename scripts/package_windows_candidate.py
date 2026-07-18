#!/usr/bin/env python3
"""Assemble checksummed internal Windows portable, installer, and demo artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

MAX_PORTABLE_BYTES = 140 * 1024 * 1024
MAX_INSTALLER_BYTES = 140 * 1024 * 1024
HEX_COMMIT = re.compile(r"[0-9a-f]{40}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _zip_tree(source: Path, destination: Path, *, root_name: str) -> None:
    with zipfile.ZipFile(
        destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file() and not path.is_symlink():
                archive.write(path, (Path(root_name) / path.relative_to(source)).as_posix())


def _zip_directory(source: Path, destination: Path) -> None:
    with zipfile.ZipFile(
        destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file() and not path.is_symlink():
                archive.write(path, (Path(source.name) / path.relative_to(source)).as_posix())


def package(args: argparse.Namespace) -> dict[str, object]:
    app = args.app.resolve()
    installer_source = args.installer.resolve()
    audit_source = args.audit.resolve()
    licenses_source = args.licenses.resolve()
    demo_source = args.demo_audio.resolve()
    rights_source = args.rights.resolve()
    guide_source = args.guide.resolve()
    output = args.out.resolve()
    if not re.fullmatch(r"[1-9][0-9]*", args.build_number):
        raise SystemExit("Bundle build number must be a positive integer")
    if not HEX_COMMIT.fullmatch(args.commit):
        raise SystemExit("Commit must be a full 40-character lowercase hex identifier")
    if not args.workflow_url.startswith("https://"):
        raise SystemExit("Workflow URL must use HTTPS")
    required_files = [
        installer_source,
        audit_source,
        licenses_source,
        demo_source,
        rights_source,
        guide_source,
    ]
    if not app.is_dir() or app.is_symlink() or not (app / "AudioAtlas.exe").is_file():
        raise SystemExit(f"Windows app directory is invalid: {app}")
    for path in required_files:
        if not path.is_file() or path.is_symlink():
            raise SystemExit(f"Required candidate input is missing: {path}")

    output.mkdir(parents=True, exist_ok=True)
    prefix = f"AudioAtlas-{args.version}-build-{args.build_number}-windows-x64-INTERNAL"
    portable = output / f"{prefix}-portable.zip"
    installer = output / f"{prefix}-setup.exe"
    kit = output / f"{prefix}-demo-kit.zip"
    manifest_path = output / "windows-candidate-manifest.json"
    checksums_path = output / "SHA256SUMS.txt"

    _zip_tree(app, portable, root_name="AudioAtlas")
    shutil.copy2(installer_source, installer)
    if portable.stat().st_size > MAX_PORTABLE_BYTES:
        raise SystemExit(f"Portable ZIP exceeds {MAX_PORTABLE_BYTES} byte budget")
    if installer.stat().st_size > MAX_INSTALLER_BYTES:
        raise SystemExit(f"Installer exceeds {MAX_INSTALLER_BYTES} byte budget")

    audit_hash = _sha256(audit_source)
    licenses_hash = _sha256(licenses_source)
    manifest: dict[str, object] = {
        "schema_version": 1,
        "candidate_id": f"{args.version}-build-{args.build_number}-{args.commit[:12]}",
        "version": args.version,
        "bundle_build": int(args.build_number),
        "commit": args.commit,
        "architecture": "x86_64",
        "python_version": "3.11",
        "windows_targets": ["Windows 10 22H2 x64", "Windows 11 x64"],
        "workflow_url": args.workflow_url,
        "portable_filename": portable.name,
        "portable_sha256": _sha256(portable),
        "installer_filename": installer.name,
        "installer_sha256": _sha256(installer),
        "pe_audit_sha256": audit_hash,
        "license_inventory_sha256": licenses_hash,
        "signing_status": "unsigned-internal",
        "built_at": datetime.now(UTC).isoformat(),
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    checksum_files = [portable, installer, audit_source, licenses_source, demo_source]
    checksums_path.write_text(
        "".join(f"{_sha256(path)}  {path.name}\n" for path in checksum_files),
        encoding="utf-8",
    )
    Path(f"{portable}.sha256").write_text(
        f"{manifest['portable_sha256']}  {portable.name}\n", encoding="utf-8"
    )
    Path(f"{installer}.sha256").write_text(
        f"{manifest['installer_sha256']}  {installer.name}\n", encoding="utf-8"
    )

    with tempfile.TemporaryDirectory(prefix="audioatlas-windows-kit-") as temporary:
        kit_root = Path(temporary) / prefix.removesuffix("-INTERNAL")
        kit_root.mkdir()
        for source in (
            portable,
            installer,
            manifest_path,
            checksums_path,
            audit_source,
            licenses_source,
            demo_source,
            rights_source,
        ):
            shutil.copy2(source, kit_root / source.name)
        shutil.copy2(guide_source, kit_root / "DEMO_AND_ACCEPTANCE_GUIDE.md")
        _zip_directory(kit_root, kit)
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--installer", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--licenses", type=Path, required=True)
    parser.add_argument("--demo-audio", type=Path, required=True)
    parser.add_argument("--rights", type=Path, required=True)
    parser.add_argument("--guide", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--build-number", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--workflow-url", required=True)
    return parser


if __name__ == "__main__":
    package(_parser().parse_args())
