#!/usr/bin/env python3
"""Create, notarize, staple, audit, and describe an AudioAtlas DMG."""

from __future__ import annotations

import argparse
import hashlib
import json
import plistlib
import re
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

APP_SIZE_LIMIT_KIB = 281_600
DMG_SIZE_LIMIT_BYTES = 125_829_120
BUNDLE_IDENTIFIER = "com.charlesmish.audioatlas"
MINIMUM_MACOS = "14.0"
ARCHITECTURE = "arm64"
EXPECTED_APP_ENTITLEMENTS = {
    "com.apple.security.cs.allow-jit": True,
    "com.apple.security.cs.allow-unsigned-executable-memory": True,
}
MACOS_DMG_MANIFEST_SCHEMA_VERSION = 1
ALLOWED_NOTARY_STATUS = "Accepted"
DEFAULT_TIMEOUT_SECONDS = 120
SUBMISSION_TIMEOUT_SECONDS = 1_200
LOG_TIMEOUT_SECONDS = 180
SIGNATURE_TIMEOUT_SECONDS = 120
MOUNT_TIMEOUT_SECONDS = 180
DETACH_TIMEOUT_SECONDS = 60
DMG_CREATE_TIMEOUT_SECONDS = 360

MANIFEST_REQUIRED_FIELDS = {
    "schema_version",
    "candidate_id",
    "version",
    "bundle_build",
    "commit",
    "architecture",
    "minimum_macos",
    "bundle_identifier",
    "workflow_url",
    "dmg_filename",
    "dmg_sha256",
    "notarization_submission_id",
    "notarytool_id",
    "notarization_status",
    "signing_team",
    "built_at",
}
REQUIRED_NOTARIZATION_LOG_FIELDS = {"id", "status", "issues", "createdDate"}
REQUIRED_NOTARIZATION_SUBMISSION_FIELDS = {"id", "status"}
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{12,40}$", re.IGNORECASE)
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)


def _run(
    *args: str,
    capture_output: bool = False,
    check: bool = True,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    context: str = "shell command",
) -> subprocess.CompletedProcess[str]:
    command = list(args)
    try:
        return subprocess.run(
            command,
            check=check,
            text=True,
            capture_output=capture_output,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise SystemExit(f"{context} timed out after {timeout}s: {command}") from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            f"{context} failed with exit code {exc.returncode}:\n"
            f"command: {command}\n"
            f"stdout: {exc.stdout}\n"
            f"stderr: {exc.stderr}"
        ) from exc


def _load_json(*, payload: str, context: str) -> dict[str, object]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{context} did not return JSON") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"{context} returned non-object JSON")
    return data


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_notarization_submission(payload: dict[str, object]) -> str:
    submission_id, status = _notarization_submission_identity(payload)
    if status != ALLOWED_NOTARY_STATUS:
        raise SystemExit(
            f"Notarization submission was not accepted: status={status!r}"
        )
    return submission_id


def _notarization_submission_identity(
    payload: dict[str, object],
) -> tuple[str, str]:
    missing = [field for field in REQUIRED_NOTARIZATION_SUBMISSION_FIELDS if field not in payload]
    if missing:
        raise SystemExit(
            f"Notarization submission payload missing required fields: {missing!r}"
        )
    submission_id = payload["id"]
    status = payload["status"]
    if not isinstance(submission_id, str) or not submission_id:
        raise SystemExit("Notarization submission id must be a non-empty string")
    if not isinstance(status, str):
        raise SystemExit("Notarization submission status must be a string")
    return submission_id, status


def _notarization_submission_id_if_available(
    payload: dict[str, object],
) -> str | None:
    submission_id = payload.get("id")
    return submission_id if isinstance(submission_id, str) and submission_id else None


def _validate_notarization_log(
    payload: dict[str, object], *, submission_id: str
) -> None:
    missing = [field for field in REQUIRED_NOTARIZATION_LOG_FIELDS if field not in payload]
    if missing:
        raise SystemExit(
            f"Notarization log payload missing required fields: {missing!r}"
        )
    status = payload["status"]
    issues = payload["issues"]
    log_id = payload["id"]
    if status != ALLOWED_NOTARY_STATUS:
        raise SystemExit(
            f"Notarization log status was {status!r}, expected {ALLOWED_NOTARY_STATUS!r}"
        )
    if not isinstance(issues, list) or issues:
        raise SystemExit("Notarization log must have an empty issues list")
    if not isinstance(log_id, str) or not log_id:
        raise SystemExit("Notarization log id must be a non-empty string")
    if log_id != submission_id:
        raise SystemExit("Notarization log id does not match submission id")
    if not isinstance(payload.get("createdDate"), str) or not payload["createdDate"]:
        raise SystemExit("Notarization log must include a non-empty createdDate")


def _validate_manifest(manifest: dict[str, object]) -> None:
    missing = [field for field in MANIFEST_REQUIRED_FIELDS if field not in manifest]
    if missing:
        raise SystemExit(f"Manifest is missing required fields: {missing!r}")

    if manifest["schema_version"] != MACOS_DMG_MANIFEST_SCHEMA_VERSION:
        raise SystemExit("Manifest schema_version must be 1")

    expected_scalar_fields = {
        "candidate_id": str,
        "version": str,
        "bundle_build": (str, int),
        "commit": str,
        "architecture": str,
        "minimum_macos": str,
        "bundle_identifier": str,
        "workflow_url": str,
        "dmg_filename": str,
        "dmg_sha256": str,
        "notarization_submission_id": str,
        "notarytool_id": str,
        "notarization_status": str,
        "signing_team": str,
        "built_at": str,
    }
    for field, expected_type in expected_scalar_fields.items():
        value = manifest[field]
        if not isinstance(value, expected_type):
            raise SystemExit(f"Manifest field {field!r} must be {expected_type!r}")
        if isinstance(value, str) and not value.strip():
            raise SystemExit(f"Manifest field {field!r} must be non-empty")

    if manifest["architecture"] != ARCHITECTURE:
        raise SystemExit(
            f"Manifest architecture must be {ARCHITECTURE!r}, found {manifest['architecture']!r}"
        )
    if manifest["minimum_macos"] != MINIMUM_MACOS:
        raise SystemExit(
            f"Manifest minimum_macos must be {MINIMUM_MACOS!r}, found {manifest['minimum_macos']!r}"
        )
    if manifest["bundle_identifier"] != BUNDLE_IDENTIFIER:
        raise SystemExit(
            f"Manifest bundle_identifier must be {BUNDLE_IDENTIFIER!r}, found {manifest['bundle_identifier']!r}"
        )
    if not COMMIT_PATTERN.fullmatch(manifest["commit"]):
        raise SystemExit("Manifest commit must be a git-style hex identifier")
    if not HEX_SHA256.fullmatch(manifest["dmg_sha256"]):
        raise SystemExit("Manifest dmg_sha256 must be a SHA-256 hex digest")
    if not manifest["workflow_url"].startswith("https://"):
        raise SystemExit("Manifest workflow_url must be HTTPS")
    if manifest["notarization_status"] != ALLOWED_NOTARY_STATUS:
        raise SystemExit("Manifest notarization_status must be Accepted")
    build_number = manifest["bundle_build"]
    if isinstance(build_number, bool) or not isinstance(build_number, (str, int)):
        raise SystemExit("Manifest bundle_build must be a positive integer")
    if isinstance(build_number, str):
        if not build_number.isdecimal() or int(build_number) <= 0:
            raise SystemExit("Manifest bundle_build must be a positive integer")
    elif build_number <= 0:
        raise SystemExit("Manifest bundle_build must be a positive integer")
    try:
        datetime.fromisoformat(manifest["built_at"])
    except ValueError as exc:
        raise SystemExit("Manifest built_at must be ISO-8601") from exc


def _write_manifest(path: Path, manifest: dict[str, object]) -> None:
    path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _verify_app_identity(
    app: Path,
    *,
    version: str,
    build_number: str,
    signing_team: str,
) -> None:
    info_path = app / "Contents" / "Info.plist"
    with info_path.open("rb") as stream:
        info = plistlib.load(stream)
    expected = {
        "CFBundleIdentifier": BUNDLE_IDENTIFIER,
        "CFBundleShortVersionString": version,
        "CFBundleVersion": build_number,
        "LSMinimumSystemVersion": MINIMUM_MACOS,
    }
    for key, value in expected.items():
        if str(info.get(key)) != value:
            raise SystemExit(f"{key} must be {value!r}, found {info.get(key)!r}")

    _run(
        "codesign",
        "--verify",
        "--deep",
        "--strict",
        "--verbose=2",
        str(app),
        context="Verify app signature",
    )
    details = _run(
        "codesign",
        "-dvvv",
        str(app),
        capture_output=True,
        context="Read app signature details",
    ).stderr
    required = (
        f"Identifier={BUNDLE_IDENTIFIER}",
        f"TeamIdentifier={signing_team}",
        "Authority=Developer ID Application:",
        "Timestamp=",
    )
    for marker in required:
        if marker not in details:
            raise SystemExit(f"Signed app identity is missing {marker!r}")
    if "runtime" not in details:
        raise SystemExit("Signed app does not advertise the hardened runtime")
    _verify_exact_app_entitlements(app)


def _verify_exact_app_entitlements(app: Path) -> None:
    result = _run(
        "codesign",
        "-d",
        "--entitlements",
        ":-",
        str(app),
        capture_output=True,
        context="Read app entitlements",
    )
    try:
        entitlements = plistlib.loads(result.stdout.encode("utf-8"))
    except (plistlib.InvalidFileException, ValueError) as exc:
        raise SystemExit("Signed app entitlements were not a valid plist") from exc
    if entitlements != EXPECTED_APP_ENTITLEMENTS:
        raise SystemExit(
            "Signed app entitlements did not exactly match the approved JIT set: "
            f"{entitlements!r}"
        )


def _verify_mounted_dmg(dmg: Path) -> None:
    attached = _run(
        "hdiutil",
        "attach",
        "-readonly",
        "-nobrowse",
        "-plist",
        str(dmg),
        capture_output=True,
        timeout=MOUNT_TIMEOUT_SECONDS,
        context="Attach DMG for postpackaging audit",
    )
    payload = plistlib.loads(attached.stdout.encode("utf-8"))
    mount_points = [
        entity.get("mount-point")
        for entity in payload.get("system-entities", [])
        if entity.get("mount-point")
    ]
    if len(mount_points) != 1:
        raise SystemExit(f"Expected one mounted DMG volume, found {mount_points!r}")
    mount = Path(mount_points[0])
    try:
        if {entry.name for entry in mount.iterdir()} != {"AudioAtlas.app", "Applications"}:
            raise SystemExit("DMG must contain exactly AudioAtlas.app and Applications")
        applications = mount / "Applications"
        if not applications.is_symlink() or applications.readlink() != Path("/Applications"):
            raise SystemExit("DMG Applications item must link to /Applications")
    finally:
        _run(
            "hdiutil",
            "detach",
            str(mount),
            timeout=DETACH_TIMEOUT_SECONDS,
            context="Detach DMG for postpackaging audit",
        )


def _assert_macos_file_hash_consistent(dmg: Path, manifest: dict[str, object]) -> None:
    expected_hash = manifest["dmg_sha256"]
    observed = _sha256(dmg)
    if expected_hash != observed:
        raise SystemExit(
            f"DMG hash mismatch: manifest {expected_hash!r}, observed {observed!r}"
        )


def _notarize_dmg(
    dmg: Path,
    *,
    api_key: Path,
    api_key_id: str,
    api_issuer_id: str,
    submission_path: Path,
    log_path: Path,
) -> tuple[str, dict[str, object]]:
    """Submit a DMG and retain every available Apple response before failing."""

    submission_result = _run(
        "xcrun",
        "notarytool",
        "submit",
        str(dmg),
        "--key",
        str(api_key.resolve()),
        "--key-id",
        api_key_id,
        "--issuer",
        api_issuer_id,
        "--wait",
        "--output-format",
        "json",
        timeout=SUBMISSION_TIMEOUT_SECONDS,
        check=False,
        capture_output=True,
        context="Run notarytool submit",
    )
    submission_path.write_text(submission_result.stdout, encoding="utf-8")
    submission_payload = _load_json(
        payload=submission_result.stdout,
        context="notarytool submission output",
    )
    submission_id = _notarization_submission_id_if_available(submission_payload)
    log_result: subprocess.CompletedProcess[str] | None = None
    log_payload: dict[str, object] | None = None
    if submission_id is not None:
        log_result = _run(
            "xcrun",
            "notarytool",
            "log",
            submission_id,
            "--key",
            str(api_key.resolve()),
            "--key-id",
            api_key_id,
            "--issuer",
            api_issuer_id,
            "--output-format",
            "json",
            timeout=LOG_TIMEOUT_SECONDS,
            capture_output=True,
            check=False,
            context="Run notarytool log",
        )
        log_path.write_text(log_result.stdout, encoding="utf-8")
        log_payload = _load_json(
            payload=log_result.stdout,
            context="notarytool log output",
        )

    if submission_result.returncode != 0:
        raise SystemExit(
            "Notarytool submission command failed: "
            f"stdout={submission_result.stdout!r} stderr={submission_result.stderr!r}"
        )
    submission_id = _validate_notarization_submission(submission_payload)
    if log_result is None or log_payload is None:  # pragma: no cover - validation invariant
        raise SystemExit("Notarytool submission did not provide an id for log retrieval")
    if log_result.returncode != 0:
        raise SystemExit(
            "Notarytool log command failed: "
            f"stdout={log_result.stdout!r} stderr={log_result.stderr!r}"
        )
    _validate_notarization_log(log_payload, submission_id=submission_id)
    return submission_id, log_payload


def package(args: argparse.Namespace) -> None:
    app = args.app.resolve()
    dmg = args.dmg.resolve()
    submission_path = args.submission_json.resolve()
    log_path = args.notarization_log.resolve()
    manifest_path = args.manifest.resolve()
    if not app.is_dir() or app.is_symlink():
        raise SystemExit(f"App bundle does not exist: {app}")
    if not args.build_number.isdecimal() or int(args.build_number) <= 0:
        raise SystemExit("Bundle build number must be a positive integer")
    if not COMMIT_PATTERN.fullmatch(args.commit):
        raise SystemExit("Commit must be a git-style hex identifier")
    if dmg.exists():
        raise SystemExit(f"Refusing to overwrite existing DMG: {dmg}")
    if not args.workflow_url.startswith("https://"):
        raise SystemExit("workflow-url must use HTTPS")
    for output in (dmg, submission_path, log_path, manifest_path):
        output.parent.mkdir(parents=True, exist_ok=True)

    _verify_app_identity(
        app,
        version=args.version,
        build_number=args.build_number,
        signing_team=args.signing_team,
    )

    with tempfile.TemporaryDirectory(prefix="audioatlas-dmg-") as temporary:
        root = Path(temporary) / "root"
        root.mkdir()
        _run("ditto", str(app), str(root / "AudioAtlas.app"), context="Copy app into DMG staging root")
        _run(
            "ln",
            "-s",
            "/Applications",
            str(root / "Applications"),
            context="Create Applications symlink in DMG staging root",
        )
        _run(
            "hdiutil",
            "create",
            "-volname",
            "AudioAtlas",
            "-srcfolder",
            str(root),
            "-ov",
            "-format",
            "UDZO",
            str(dmg),
            timeout=DMG_CREATE_TIMEOUT_SECONDS,
            context="Create DMG image",
        )

    _run(
        "codesign",
        "--force",
        "--timestamp",
        "--sign",
        args.signing_identity,
        str(dmg),
        timeout=SIGNATURE_TIMEOUT_SECONDS,
        context="Sign DMG",
    )

    submission_id, log_payload = _notarize_dmg(
        dmg,
        api_key=args.api_key,
        api_key_id=args.api_key_id,
        api_issuer_id=args.api_issuer_id,
        submission_path=submission_path,
        log_path=log_path,
    )

    _run(
        "xcrun",
        "stapler",
        "staple",
        str(dmg),
        timeout=SIGNATURE_TIMEOUT_SECONDS,
        context="Staple DMG",
    )
    _run(
        "xcrun",
        "stapler",
        "validate",
        str(dmg),
        timeout=SIGNATURE_TIMEOUT_SECONDS,
        context="Validate stapled DMG",
    )
    _run(
        "spctl",
        "--assess",
        "--type",
        "open",
        "--context",
        "context:primary-signature",
        "--verbose=2",
        str(dmg),
        timeout=SIGNATURE_TIMEOUT_SECONDS,
        context="Gatekeeper assessment",
    )
    _verify_mounted_dmg(dmg)

    app_size_kib = int(
        _run("du", "-sk", str(app), capture_output=True, context="Measure app size").stdout.split()[0]
    )
    if app_size_kib > APP_SIZE_LIMIT_KIB:
        raise SystemExit(f"App size {app_size_kib} KiB exceeds {APP_SIZE_LIMIT_KIB} KiB")
    if dmg.stat().st_size > DMG_SIZE_LIMIT_BYTES:
        raise SystemExit(
            f"DMG size {dmg.stat().st_size} bytes exceeds {DMG_SIZE_LIMIT_BYTES} bytes"
        )

    dmg_hash = _sha256(dmg)
    dmg_hash_path = Path(f"{dmg}.sha256")
    dmg_hash_path.write_text(f"{dmg_hash}  {dmg.name}\n", encoding="utf-8")

    manifest = {
        "schema_version": MACOS_DMG_MANIFEST_SCHEMA_VERSION,
        "candidate_id": (
            f"audioatlas-macos-{args.version}-build-{args.build_number}-{args.commit[:12]}"
        ),
        "version": args.version,
        "bundle_build": args.build_number,
        "commit": args.commit,
        "architecture": ARCHITECTURE,
        "minimum_macos": MINIMUM_MACOS,
        "bundle_identifier": BUNDLE_IDENTIFIER,
        "workflow_url": args.workflow_url,
        "dmg_filename": dmg.name,
        "dmg_sha256": dmg_hash,
        "notarization_submission_id": submission_id,
        "notarytool_id": args.api_key_id,
        "notarization_status": log_payload["status"],
        "signing_team": args.signing_team,
        "built_at": datetime.now(UTC).isoformat(),
    }
    _validate_manifest(manifest)
    _assert_macos_file_hash_consistent(dmg, manifest)
    if not (Path(f"{dmg}.sha256").read_text(encoding="utf-8").strip() == f"{dmg_hash}  {dmg.name}"):
        raise SystemExit("Computed SHA-256 does not match generated checksum file")
    _write_manifest(manifest_path, manifest)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--dmg", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--build-number", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--workflow-url", required=True)
    parser.add_argument("--signing-team", required=True)
    parser.add_argument("--signing-identity", required=True)
    parser.add_argument("--api-key", type=Path, required=True)
    parser.add_argument("--api-key-id", required=True)
    parser.add_argument("--api-issuer-id", required=True)
    parser.add_argument("--submission-json", type=Path, required=True)
    parser.add_argument("--notarization-log", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    return parser


if __name__ == "__main__":
    package(_parser().parse_args())
