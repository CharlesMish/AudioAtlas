#!/usr/bin/env python3
"""Assemble checksummed internal Windows installer and portable test kits."""

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
from urllib.parse import urlsplit

try:
    from windows_inventory import InventoryVerificationError, verify_app_inventory
except ModuleNotFoundError:  # Imported as a module from the repository root in tests.
    from scripts.windows_inventory import InventoryVerificationError, verify_app_inventory

MAX_PORTABLE_BYTES = 140 * 1024 * 1024
MAX_INSTALLER_BYTES = 140 * 1024 * 1024
HEX_COMMIT = re.compile(r"[0-9a-f]{40}")
MINIMUM_WINDOWS_BUILD = 19045
DEFAULT_INSTALL_LOCATION = r"%LOCALAPPDATA%\Programs\AudioAtlas"


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
            if path.is_symlink():
                raise SystemExit(f"Refusing to archive symlink: {path}")
            if path.is_file():
                archive.write(path, (Path(root_name) / path.relative_to(source)).as_posix())


def _zip_directory(source: Path, destination: Path) -> None:
    with zipfile.ZipFile(
        destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_symlink():
                raise SystemExit(f"Refusing to archive symlink: {path}")
            if path.is_file():
                archive.write(path, (Path(source.name) / path.relative_to(source)).as_posix())


def _write_checksum(path: Path) -> Path:
    sidecar = Path(f"{path}.sha256")
    sidecar.write_text(f"{_sha256(path)}  {path.name}\n", encoding="utf-8")
    return sidecar


def _write_checksums(destination: Path, paths: list[Path]) -> None:
    destination.write_text(
        "".join(f"{_sha256(path)}  {path.name}\n" for path in paths),
        encoding="utf-8",
    )


def _component(path: Path, *, delivered_filename: str | None = None) -> dict[str, object]:
    return {
        "filename": delivered_filename or path.name,
        "sha256": _sha256(path),
        "bytes": path.stat().st_size,
    }


def _assemble_kit(
    *,
    root: Path,
    artifact: Path,
    common: list[Path],
    guide: Path,
    output: Path,
) -> None:
    root.mkdir()
    copied: list[Path] = []
    for source in (artifact, *common):
        target = root / source.name
        shutil.copy2(source, target)
        copied.append(target)
    guide_target = root / "DEMO_AND_ACCEPTANCE_GUIDE.md"
    shutil.copy2(guide, guide_target)
    copied.append(guide_target)
    _write_checksums(root / "SHA256SUMS.txt", copied)
    _zip_directory(root, output)


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
    if not re.fullmatch(r"\d+\.\d+\.\d+a\d+", args.version):
        raise SystemExit("Candidate version must use the supported alpha format")
    if not HEX_COMMIT.fullmatch(args.commit):
        raise SystemExit("Commit must be a full 40-character lowercase hex identifier")
    workflow_url = urlsplit(args.workflow_url)
    if (
        workflow_url.scheme != "https"
        or not workflow_url.netloc
        or workflow_url.username is not None
        or workflow_url.password is not None
        or workflow_url.fragment
    ):
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
    expected_source_names = {
        audit_source: "windows-pe-audit.json",
        licenses_source: "THIRD_PARTY_LICENSES.txt",
        demo_source: "audioatlas_demo.wav",
        rights_source: "AUDIO_RIGHTS.md",
    }
    for path, expected_name in expected_source_names.items():
        if path.name != expected_name:
            raise SystemExit(
                f"Candidate input must use delivered filename {expected_name}: {path.name}"
            )
    try:
        distribution_audit = json.loads(audit_source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit("Windows distribution audit is invalid") from exc
    if (
        not isinstance(distribution_audit, dict)
        or distribution_audit.get("schema_version") != 3
        or distribution_audit.get("architecture") != "x86_64"
        or distribution_audit.get("windows_targets") != ["Windows 10 22H2 x64", "Windows 11 x64"]
        or distribution_audit.get("minimum_windows_build") != MINIMUM_WINDOWS_BUILD
        or distribution_audit.get("signing_status") != "unsigned-internal"
        or not isinstance(distribution_audit.get("installer"), dict)
        or not isinstance(distribution_audit.get("app_bundle"), dict)
        or distribution_audit["app_bundle"].get("version") != args.version
        or distribution_audit["app_bundle"].get("bundle_build") != int(args.build_number)
        or distribution_audit["installer"].get("version_strings", {}).get("ProductVersion")
        != args.version
        or distribution_audit["installer"].get("version_strings", {}).get("FileVersion")
        != args.version
    ):
        raise SystemExit("Windows distribution audit has an invalid contract")
    try:
        inventory_root = verify_app_inventory(app, distribution_audit.get("app_bundle"))
    except InventoryVerificationError as exc:
        raise SystemExit(f"Windows native audit is stale: {exc}") from exc
    if distribution_audit["installer"].get("source_app_inventory_root_sha256") != inventory_root:
        raise SystemExit("Installer source app is not bound to the native inventory")

    output.mkdir(parents=True, exist_ok=True)
    prefix = f"AudioAtlas-{args.version}-build-{args.build_number}-windows-x64-INTERNAL"
    portable = output / f"{prefix}-portable.zip"
    installer = output / f"{prefix}-setup.exe"
    installer_kit = output / f"{prefix}-installer-test-kit.zip"
    portable_kit = output / f"{prefix}-portable-test-kit.zip"
    manifest_path = output / "windows-candidate-manifest.json"
    readme_path = output / "README_FIRST.txt"

    # This check is intentionally adjacent to archive creation. The portable is
    # verified again from its streamed members below by the candidate verifier.
    try:
        if verify_app_inventory(app, distribution_audit["app_bundle"]) != inventory_root:
            raise SystemExit("Windows native inventory changed before packaging")
    except InventoryVerificationError as exc:
        raise SystemExit(f"Windows native audit became stale before packaging: {exc}") from exc
    _zip_tree(app, portable, root_name="AudioAtlas")
    shutil.copy2(installer_source, installer)
    if portable.stat().st_size > MAX_PORTABLE_BYTES:
        raise SystemExit(f"Portable ZIP exceeds {MAX_PORTABLE_BYTES} byte budget")
    if installer.stat().st_size > MAX_INSTALLER_BYTES:
        raise SystemExit(f"Installer exceeds {MAX_INSTALLER_BYTES} byte budget")

    components = {
        "installer": _component(installer),
        "portable": _component(portable),
        "demo_audio": _component(demo_source),
        "pe_audit": _component(audit_source),
        "license_inventory": _component(licenses_source),
        "rights_notice": _component(rights_source),
        "acceptance_guide": _component(
            guide_source, delivered_filename="DEMO_AND_ACCEPTANCE_GUIDE.md"
        ),
    }
    manifest: dict[str, object] = {
        "schema_version": 3,
        "candidate_id": f"{args.version}-build-{args.build_number}-{args.commit[:12]}",
        "version": args.version,
        "bundle_build": int(args.build_number),
        "commit": args.commit,
        "architecture": "x86_64",
        "python_version": "3.11",
        "windows_targets": ["Windows 10 22H2 x64", "Windows 11 x64"],
        "minimum_windows_build": MINIMUM_WINDOWS_BUILD,
        "installation_scope": "per-user",
        "default_install_location": DEFAULT_INSTALL_LOCATION,
        "requires_administrator": False,
        "workflow_url": args.workflow_url,
        "components": components,
        "native_inventory": {
            "schema_version": 1,
            "root_sha256": inventory_root,
            "bindings": {
                "installer_source_app": inventory_root,
                "portable_source_app": inventory_root,
                "portable_archive_app": inventory_root,
            },
        },
        # Retain flat artifact fields for existing internal evidence consumers.
        "portable_filename": portable.name,
        "portable_sha256": components["portable"]["sha256"],
        "installer_filename": installer.name,
        "installer_sha256": components["installer"]["sha256"],
        "demo_audio_sha256": components["demo_audio"]["sha256"],
        "pe_audit_sha256": components["pe_audit"]["sha256"],
        "license_inventory_sha256": components["license_inventory"]["sha256"],
        "signing_status": "unsigned-internal",
        "built_at": datetime.now(UTC).isoformat(),
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    readme_path.write_text(
        "AudioAtlas internal Windows candidate\n"
        "\n"
        "Start with the installer-test-kit ZIP. Verify its adjacent SHA-256 file,\n"
        "extract it normally, and read DEMO_AND_ACCEPTANCE_GUIDE.md before running\n"
        "the setup program. The portable-test-kit is a separate secondary test.\n"
        "\n"
        "These builds are unsigned and internal-only. Do not bypass Windows security.\n",
        encoding="utf-8",
    )

    common = [
        demo_source,
        rights_source,
        manifest_path,
        audit_source,
        licenses_source,
    ]
    with tempfile.TemporaryDirectory(prefix="audioatlas-windows-kits-") as temporary:
        temporary_root = Path(temporary)
        _assemble_kit(
            root=temporary_root
            / f"AudioAtlas-{args.version}-build-{args.build_number}-install-test",
            artifact=installer,
            common=common,
            guide=guide_source,
            output=installer_kit,
        )
        _assemble_kit(
            root=temporary_root
            / f"AudioAtlas-{args.version}-build-{args.build_number}-portable-test",
            artifact=portable,
            common=common,
            guide=guide_source,
            output=portable_kit,
        )

    _write_checksum(installer_kit)
    _write_checksum(portable_kit)
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
