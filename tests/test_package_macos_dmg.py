from __future__ import annotations

import hashlib
import importlib.util
import json
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
    details = "\n".join(
        (
            f"Identifier={package_macos_dmg.BUNDLE_IDENTIFIER}",
            "TeamIdentifier=TEAM123",
            "Authority=Developer ID Application: Example",
            "flags=0x10000(runtime)",
            "Timestamp=Jul 18, 2026",
        )
    )

    def run(
        *args: str,
        capture_output: bool = False,
        check: bool = True,
        timeout: int = 0,
        context: str = "",
    ) -> SimpleNamespace:
        if "--entitlements" in args:
            payload = plistlib.dumps(package_macos_dmg.EXPECTED_APP_ENTITLEMENTS).decode(
                "utf-8"
            )
            return SimpleNamespace(stdout=payload, stderr="")
        if capture_output:
            return SimpleNamespace(stdout="", stderr=details)
        return SimpleNamespace(stdout="", stderr="")

    monkeypatch.setattr(package_macos_dmg, "_run", run)

    package_macos_dmg._verify_app_identity(
        app,
        version="0.2.0a7",
        build_number="42",
        signing_team="TEAM123",
    )


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


@pytest.mark.parametrize(
    "entitlements",
    [
        {"com.apple.security.cs.allow-jit": True},
        {
            **package_macos_dmg.EXPECTED_APP_ENTITLEMENTS,
            "com.apple.security.get-task-allow": True,
        },
    ],
)
def test_exact_entitlements_reject_missing_or_extra_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    entitlements: dict[str, bool],
) -> None:
    app = tmp_path / "AudioAtlas.app"
    app.mkdir()
    payload = plistlib.dumps(entitlements).decode("utf-8")
    monkeypatch.setattr(
        package_macos_dmg,
        "_run",
        lambda *args, **kwargs: SimpleNamespace(stdout=payload, stderr=""),
    )

    with pytest.raises(SystemExit, match="approved JIT set"):
        package_macos_dmg._verify_exact_app_entitlements(app)


def test_exact_entitlements_accept_only_approved_jit_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = tmp_path / "AudioAtlas.app"
    app.mkdir()
    payload = plistlib.dumps(package_macos_dmg.EXPECTED_APP_ENTITLEMENTS).decode("utf-8")
    monkeypatch.setattr(
        package_macos_dmg,
        "_run",
        lambda *args, **kwargs: SimpleNamespace(stdout=payload, stderr=""),
    )

    package_macos_dmg._verify_exact_app_entitlements(app)


def test_notarization_submission_rejects_partial_status() -> None:
    payload = {"id": "submit-123", "status": "In Progress"}

    with pytest.raises(SystemExit, match="not accepted"):
        package_macos_dmg._validate_notarization_submission(payload)


def test_notarization_submission_rejects_missing_id() -> None:
    payload: dict[str, object] = {"status": package_macos_dmg.ALLOWED_NOTARY_STATUS}

    with pytest.raises(SystemExit, match="missing required fields"):
        package_macos_dmg._validate_notarization_submission(payload)


def test_notarization_log_rejects_open_issues() -> None:
    payload = {
        "id": "submit-123",
        "status": package_macos_dmg.ALLOWED_NOTARY_STATUS,
        "issues": [{"message": "warning"}],
        "createdDate": "2026-07-18T00:00:00+00:00",
    }

    with pytest.raises(SystemExit, match="empty issues"):
        package_macos_dmg._validate_notarization_log(payload, submission_id="submit-123")


def test_notarization_log_rejects_mismatched_submission_reference() -> None:
    payload = {
        "id": "submit-456",
        "status": package_macos_dmg.ALLOWED_NOTARY_STATUS,
        "issues": [],
        "createdDate": "2026-07-18T00:00:00+00:00",
    }

    with pytest.raises(SystemExit, match="does not match submission id"):
        package_macos_dmg._validate_notarization_log(payload, submission_id="submit-123")


def test_notarization_log_rejects_missing_created_date() -> None:
    payload = {
        "id": "submit-123",
        "status": package_macos_dmg.ALLOWED_NOTARY_STATUS,
        "issues": [],
    }

    with pytest.raises(SystemExit, match="createdDate"):
        package_macos_dmg._validate_notarization_log(payload, submission_id="submit-123")


@pytest.mark.parametrize(
    ("submit_status", "submit_returncode", "message"),
    [
        ("Invalid", 0, "not accepted"),
        ("Accepted", 1, "submission command failed"),
    ],
)
def test_notarization_failure_retains_submission_and_log_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    submit_status: str,
    submit_returncode: int,
    message: str,
) -> None:
    submission = {"id": "submit-123", "status": submit_status}
    log = {
        "id": "submit-123",
        "status": submit_status,
        "issues": [] if submit_status == "Accepted" else [{"message": "rejected"}],
        "createdDate": "2026-07-18T00:00:00+00:00",
    }
    responses = iter(
        (
            SimpleNamespace(
                returncode=submit_returncode,
                stdout=json.dumps(submission),
                stderr="submit failed" if submit_returncode else "",
            ),
            SimpleNamespace(returncode=0, stdout=json.dumps(log), stderr=""),
        )
    )
    monkeypatch.setattr(package_macos_dmg, "_run", lambda *args, **kwargs: next(responses))
    submission_path = tmp_path / "submission.json"
    log_path = tmp_path / "log.json"

    with pytest.raises(SystemExit, match=message):
        package_macos_dmg._notarize_dmg(
            tmp_path / "candidate.dmg",
            api_key=tmp_path / "AuthKey.p8",
            api_key_id="KEY123",
            api_issuer_id="ISSUER123",
            submission_path=submission_path,
            log_path=log_path,
        )

    assert json.loads(submission_path.read_text(encoding="utf-8")) == submission
    assert json.loads(log_path.read_text(encoding="utf-8")) == log


def test_malformed_notarization_response_is_retained_before_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        package_macos_dmg,
        "_run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1, stdout="not json", stderr="failed"
        ),
    )
    submission_path = tmp_path / "submission.json"

    with pytest.raises(SystemExit, match="did not return JSON"):
        package_macos_dmg._notarize_dmg(
            tmp_path / "candidate.dmg",
            api_key=tmp_path / "AuthKey.p8",
            api_key_id="KEY123",
            api_issuer_id="ISSUER123",
            submission_path=submission_path,
            log_path=tmp_path / "log.json",
        )

    assert submission_path.read_text(encoding="utf-8") == "not json"


def test_partial_submission_with_id_retrieves_log_before_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    submission = {"id": "submit-123"}
    log = {
        "id": "submit-123",
        "status": "Invalid",
        "issues": [{"message": "invalid bundle"}],
        "createdDate": "2026-07-18T00:00:00+00:00",
    }
    responses = iter(
        (
            SimpleNamespace(returncode=0, stdout=json.dumps(submission), stderr=""),
            SimpleNamespace(returncode=0, stdout=json.dumps(log), stderr=""),
        )
    )
    monkeypatch.setattr(package_macos_dmg, "_run", lambda *args, **kwargs: next(responses))
    submission_path = tmp_path / "submission.json"
    log_path = tmp_path / "log.json"

    with pytest.raises(SystemExit, match="missing required fields"):
        package_macos_dmg._notarize_dmg(
            tmp_path / "candidate.dmg",
            api_key=tmp_path / "AuthKey.p8",
            api_key_id="KEY123",
            api_issuer_id="ISSUER123",
            submission_path=submission_path,
            log_path=log_path,
        )

    assert json.loads(submission_path.read_text(encoding="utf-8")) == submission
    assert json.loads(log_path.read_text(encoding="utf-8")) == log


def test_accepted_notarization_retains_evidence_and_returns_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    submission = {
        "id": "submit-123",
        "status": package_macos_dmg.ALLOWED_NOTARY_STATUS,
    }
    log = {
        "id": "submit-123",
        "status": package_macos_dmg.ALLOWED_NOTARY_STATUS,
        "issues": [],
        "createdDate": "2026-07-18T00:00:00+00:00",
    }
    responses = iter(
        (
            SimpleNamespace(returncode=0, stdout=json.dumps(submission), stderr=""),
            SimpleNamespace(returncode=0, stdout=json.dumps(log), stderr=""),
        )
    )
    monkeypatch.setattr(package_macos_dmg, "_run", lambda *args, **kwargs: next(responses))
    submission_path = tmp_path / "submission.json"
    log_path = tmp_path / "log.json"

    submission_id, returned_log = package_macos_dmg._notarize_dmg(
        tmp_path / "candidate.dmg",
        api_key=tmp_path / "AuthKey.p8",
        api_key_id="KEY123",
        api_issuer_id="ISSUER123",
        submission_path=submission_path,
        log_path=log_path,
    )

    assert submission_id == "submit-123"
    assert returned_log == log
    assert json.loads(submission_path.read_text(encoding="utf-8")) == submission
    assert json.loads(log_path.read_text(encoding="utf-8")) == log


def test_packaging_manifest_schema_rejects_malformed_hash() -> None:
    manifest = {
        "schema_version": 1,
        "candidate_id": "candidate",
        "version": "0.2.0a7",
        "bundle_build": "42",
        "commit": "cafebabe" * 5,
        "architecture": "arm64",
        "minimum_macos": "14.0",
        "bundle_identifier": "com.charlesmish.audioatlas",
        "workflow_url": "https://example.invalid/release-run",
        "dmg_filename": "AudioAtlas-0.2.0a7-macos.dmg",
        "dmg_sha256": "bad-digest",
        "notarization_submission_id": "submit-123",
        "notarytool_id": "ABC123",
        "notarization_status": package_macos_dmg.ALLOWED_NOTARY_STATUS,
        "signing_team": "TEAM123",
        "built_at": "2026-07-18T00:00:00+00:00",
    }

    with pytest.raises(SystemExit, match="dmg_sha256"):
        package_macos_dmg._validate_manifest(manifest)


def test_packaging_manifest_schema_rejects_invalid_bundle_build() -> None:
    manifest = {
        "schema_version": 1,
        "candidate_id": "candidate",
        "version": "0.2.0a7",
        "bundle_build": "x-42",
        "commit": "cafebabe" * 5,
        "architecture": "arm64",
        "minimum_macos": "14.0",
        "bundle_identifier": "com.charlesmish.audioatlas",
        "workflow_url": "https://example.invalid/release-run",
        "dmg_filename": "AudioAtlas-0.2.0a7-macos.dmg",
        "dmg_sha256": "a" * 64,
        "notarization_submission_id": "submit-123",
        "notarytool_id": "ABC123",
        "notarization_status": package_macos_dmg.ALLOWED_NOTARY_STATUS,
        "signing_team": "TEAM123",
        "built_at": "2026-07-18T00:00:00+00:00",
    }

    with pytest.raises(SystemExit, match="bundle_build"):
        package_macos_dmg._validate_manifest(manifest)


@pytest.mark.parametrize("bundle_build", [0, -1, "0", "-1", True])
def test_packaging_manifest_schema_rejects_nonpositive_bundle_build(
    bundle_build: object,
) -> None:
    manifest = {
        "schema_version": 1,
        "candidate_id": "candidate",
        "version": "0.2.0a7",
        "bundle_build": bundle_build,
        "commit": "cafebabe" * 5,
        "architecture": "arm64",
        "minimum_macos": "14.0",
        "bundle_identifier": "com.charlesmish.audioatlas",
        "workflow_url": "https://example.invalid/release-run",
        "dmg_filename": "AudioAtlas-0.2.0a7-macos.dmg",
        "dmg_sha256": "a" * 64,
        "notarization_submission_id": "submit-123",
        "notarytool_id": "ABC123",
        "notarization_status": package_macos_dmg.ALLOWED_NOTARY_STATUS,
        "signing_team": "TEAM123",
        "built_at": "2026-07-18T00:00:00+00:00",
    }

    with pytest.raises(SystemExit, match="bundle_build"):
        package_macos_dmg._validate_manifest(manifest)


def test_packaging_manifest_schema_rejects_missing_fields() -> None:
    manifest = {"schema_version": 1, "version": "0.2.0a7"}

    with pytest.raises(SystemExit, match="missing required fields"):
        package_macos_dmg._validate_manifest(manifest)


def test_packaging_script_records_required_candidate_manifest_fields() -> None:
    source = Path(package_macos_dmg.__file__).read_text(encoding="utf-8")
    required = {
        '"schema_version"',
        '"candidate_id"',
        '"version"',
        '"bundle_build"',
        '"commit"',
        '"architecture"',
        '"minimum_macos"',
        '"bundle_identifier"',
        '"workflow_url"',
        '"dmg_sha256"',
        '"notarization_submission_id"',
        '"notarytool_id"',
        '"notarization_status"',
        '"signing_team"',
        '"built_at"',
    }

    for field in required:
        assert field in source
