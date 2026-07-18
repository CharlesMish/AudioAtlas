from __future__ import annotations

import hashlib
import importlib.util
import plistlib
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "package_macos_dmg",
    ROOT / "scripts" / "package_macos_dmg.py",
)
assert SPEC is not None and SPEC.loader is not None
package_macos_dmg = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package_macos_dmg)


def _write_info(app: Path, **overrides: str) -> None:
    info = {
        "CFBundleIdentifier": package_macos_dmg.BUNDLE_IDENTIFIER,
        "CFBundleShortVersionString": "0.2.0a7",
        "CFBundleVersion": "42",
        "LSMinimumSystemVersion": package_macos_dmg.MINIMUM_MACOS,
    }
    info.update(overrides)
    contents = app / "Contents"
    contents.mkdir(parents=True)
    with (contents / "Info.plist").open("wb") as stream:
        plistlib.dump(info, stream)


def test_package_sha256_streams_exact_file(tmp_path: Path) -> None:
    payload = tmp_path / "candidate.dmg"
    payload.write_bytes(b"AudioAtlas candidate")

    assert package_macos_dmg._sha256(payload) == hashlib.sha256(payload.read_bytes()).hexdigest()


def test_verify_app_identity_checks_plist_and_developer_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = tmp_path / "AudioAtlas.app"
    _write_info(app)
    calls = []
    details = "\n".join(
        (
            f"Identifier={package_macos_dmg.BUNDLE_IDENTIFIER}",
            "TeamIdentifier=TEAM123",
            "Authority=Developer ID Application: Example",
            "flags=0x10000(runtime)",
            "Timestamp=Jul 18, 2026",
        )
    )

    def run(*args: str, capture_output: bool = False):
        calls.append(args)
        return SimpleNamespace(stdout="", stderr=details if capture_output else "")

    monkeypatch.setattr(package_macos_dmg, "_run", run)

    package_macos_dmg._verify_app_identity(
        app,
        version="0.2.0a7",
        build_number="42",
        signing_team="TEAM123",
    )

    assert calls[0][:3] == ("codesign", "--verify", "--deep")
    assert calls[1] == ("codesign", "-dvvv", str(app))


def test_verify_app_identity_rejects_a_mismatched_build(tmp_path: Path) -> None:
    app = tmp_path / "AudioAtlas.app"
    _write_info(app, CFBundleVersion="41")

    with pytest.raises(SystemExit, match="CFBundleVersion"):
        package_macos_dmg._verify_app_identity(
            app,
            version="0.2.0a7",
            build_number="42",
            signing_team="TEAM123",
        )


def test_packaging_script_records_required_candidate_manifest_fields() -> None:
    source = Path(package_macos_dmg.__file__).read_text(encoding="utf-8")
    required = {
        '"candidate_id"',
        '"version"',
        '"bundle_build"',
        '"commit"',
        '"architecture"',
        '"minimum_macos"',
        '"workflow_url"',
        '"dmg_sha256"',
        '"notarization_submission_id"',
        '"notarization_status"',
        '"signing_team"',
        '"built_at"',
    }

    for field in required:
        assert field in source
