#!/usr/bin/env python3
"""Create, notarize, staple, audit, and describe an AudioAtlas DMG."""

from __future__ import annotations

import argparse
import hashlib
import json
import plistlib
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

APP_SIZE_LIMIT_KIB = 281_600
DMG_SIZE_LIMIT_BYTES = 125_829_120
BUNDLE_IDENTIFIER = "com.charlesmish.audioatlas"
MINIMUM_MACOS = "14.0"
ARCHITECTURE = "arm64"


def _run(*args: str, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=True,
        text=True,
        capture_output=capture_output,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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

    _run("codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app))
    details = _run("codesign", "-dvvv", str(app), capture_output=True).stderr
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


def _verify_mounted_dmg(dmg: Path) -> None:
    attached = _run(
        "hdiutil",
        "attach",
        "-readonly",
        "-nobrowse",
        "-plist",
        str(dmg),
        capture_output=True,
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
        _run("hdiutil", "detach", str(mount))


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
    if dmg.exists():
        raise SystemExit(f"Refusing to overwrite existing DMG: {dmg}")
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
        _run("ditto", str(app), str(root / "AudioAtlas.app"))
        (root / "Applications").symlink_to("/Applications")
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
        )

    _run(
        "codesign",
        "--force",
        "--timestamp",
        "--sign",
        args.signing_identity,
        str(dmg),
    )
    submission = subprocess.run(
        [
            "xcrun",
            "notarytool",
            "submit",
            str(dmg),
            "--key",
            str(args.api_key.resolve()),
            "--key-id",
            args.api_key_id,
            "--issuer",
            args.api_issuer_id,
            "--wait",
            "--output-format",
            "json",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    submission_path.write_text(submission.stdout, encoding="utf-8")
    try:
        submission_payload = json.loads(submission.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit("Notarization submission did not return JSON") from exc
    submission_id = submission_payload.get("id")
    if not isinstance(submission_id, str) or not submission_id:
        raise SystemExit("Notarization submission did not return an ID")

    _run(
        "xcrun",
        "notarytool",
        "log",
        submission_id,
        "--key",
        str(args.api_key.resolve()),
        "--key-id",
        args.api_key_id,
        "--issuer",
        args.api_issuer_id,
        str(log_path),
    )
    log_payload = json.loads(log_path.read_text(encoding="utf-8"))
    if log_payload.get("status") != "Accepted" or log_payload.get("issues") not in (None, []):
        raise SystemExit("Notarization log was not Accepted without issues")
    if submission.returncode != 0:
        raise SystemExit("Notarization submission command failed")

    _run("xcrun", "stapler", "staple", str(dmg))
    _run("xcrun", "stapler", "validate", str(dmg))
    _run(
        "spctl",
        "--assess",
        "--type",
        "open",
        "--context",
        "context:primary-signature",
        "--verbose=2",
        str(dmg),
    )
    _verify_mounted_dmg(dmg)

    app_size_kib = int(_run("du", "-sk", str(app), capture_output=True).stdout.split()[0])
    if app_size_kib > APP_SIZE_LIMIT_KIB:
        raise SystemExit(f"App size {app_size_kib} KiB exceeds {APP_SIZE_LIMIT_KIB} KiB")
    if dmg.stat().st_size > DMG_SIZE_LIMIT_BYTES:
        raise SystemExit(
            f"DMG size {dmg.stat().st_size} bytes exceeds {DMG_SIZE_LIMIT_BYTES} bytes"
        )

    dmg_hash = _sha256(dmg)
    Path(f"{dmg}.sha256").write_text(f"{dmg_hash}  {dmg.name}\n", encoding="utf-8")
    short_commit = args.commit[:12]
    manifest = {
        "schema_version": 1,
        "candidate_id": (
            f"audioatlas-macos-{args.version}-build-{args.build_number}-{short_commit}"
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
        "notarization_status": log_payload["status"],
        "signing_team": args.signing_team,
        "built_at": datetime.now(UTC).isoformat(),
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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
