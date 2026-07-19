from __future__ import annotations

import importlib.util
import json
import stat
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _candidate(tmp_path: Path):
    package = _script("package_windows_candidate")
    app = tmp_path / "app"
    app.mkdir()
    (app / "AudioAtlas.exe").write_bytes(b"PE app")
    (app / "library.dll").write_bytes(b"PE dll")
    installer = tmp_path / "source-setup.exe"
    installer.write_bytes(b"installer")
    audit = tmp_path / "windows-pe-audit.json"
    audit.write_text('{"schema_version": 2}\n', encoding="utf-8")
    licenses = tmp_path / "THIRD_PARTY_LICENSES.txt"
    licenses.write_text("licenses\n", encoding="utf-8")
    demo = tmp_path / "audioatlas_demo.wav"
    demo.write_bytes(b"RIFF demo")
    rights = tmp_path / "AUDIO_RIGHTS.md"
    rights.write_text("rights\n", encoding="utf-8")
    guide = tmp_path / "WINDOWS_DEMO_GUIDE.md"
    guide.write_text("guide\n", encoding="utf-8")
    out = tmp_path / "candidate"
    package.package(
        SimpleNamespace(
            app=app,
            installer=installer,
            audit=audit,
            licenses=licenses,
            demo_audio=demo,
            rights=rights,
            guide=guide,
            out=out,
            version="0.2.0a7",
            build_number="42",
            commit="cafebabe" * 5,
            workflow_url="https://example.invalid/actions/runs/42",
        )
    )
    return out


def test_candidate_verifier_round_trips_both_exact_kits(tmp_path: Path) -> None:
    verifier = _script("verify_windows_candidate")
    candidate = _candidate(tmp_path)
    extracted = tmp_path / "extracted"

    report = verifier.verify_candidate(candidate, extract_root=extracted)

    assert report["verified"] is True
    assert report["candidate_id"] == "0.2.0a7-build-42-cafebabecafe"
    assert {kit["role"] for kit in report["kits"]} == {"installer", "portable"}
    assert len(list((extracted / "installer").glob("*-setup.exe"))) == 1
    assert len(list((extracted / "portable").glob("*-portable.zip"))) == 1


def test_candidate_verifier_rejects_outer_hash_mismatch(tmp_path: Path) -> None:
    verifier = _script("verify_windows_candidate")
    candidate = _candidate(tmp_path)
    kit = next(candidate.glob("*-installer-test-kit.zip"))
    Path(f"{kit}.sha256").write_text(f"{'0' * 64}  {kit.name}\n", encoding="utf-8")

    with pytest.raises(verifier.CandidateVerificationError, match="checksum differs"):
        verifier.verify_candidate(candidate)


@pytest.mark.parametrize(
    "names, message",
    [
        (["root/../escape.txt"], "Unsafe archive"),
        (["root/CON.txt"], "Reserved Windows"),
        (["root/trailing."], "trailing spaces or periods"),
        (["root/File.txt", "root/file.TXT"], "Duplicate case-insensitive"),
        (["C:/root/file.txt"], "Drive-qualified"),
        (["root/bad?.txt"], "Invalid Windows"),
    ],
)
def test_candidate_verifier_rejects_unsafe_archive_names(
    tmp_path: Path, names: list[str], message: str
) -> None:
    verifier = _script("verify_windows_candidate")
    archive_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        for name in names:
            archive.writestr(name, b"payload")

    with (
        zipfile.ZipFile(archive_path) as archive,
        pytest.raises(verifier.CandidateVerificationError, match=message),
    ):
        verifier._safe_members(archive)


def test_candidate_verifier_rejects_symlink(tmp_path: Path) -> None:
    verifier = _script("verify_windows_candidate")
    archive_path = tmp_path / "symlink.zip"
    info = zipfile.ZipInfo("root/link")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(info, "target")

    with (
        zipfile.ZipFile(archive_path) as archive,
        pytest.raises(verifier.CandidateVerificationError, match="symlink"),
    ):
        verifier._safe_members(archive)


def test_candidate_manifest_rejects_missing_install_contract(tmp_path: Path) -> None:
    verifier = _script("verify_windows_candidate")
    candidate = _candidate(tmp_path)
    manifest = json.loads((candidate / "windows-candidate-manifest.json").read_text())
    del manifest["minimum_windows_build"]

    with pytest.raises(verifier.CandidateVerificationError, match="missing"):
        verifier._validate_manifest(manifest)


def _valid_setup_contract(audit):
    return {
        "machine": audit.AMD64_MACHINE,
        "imports": ["kernel32.dll", "api-ms-win-core-file-l1-1-0.dll"],
        "manifest": (
            '<requestedExecutionLevel level="asInvoker" uiAccess="false"/>'
        ),
        "version_strings": {
            "ProductName": "AudioAtlas",
            "ProductVersion": "0.2.0a7",
            "FileVersion": "0.2.0a7",
            "FileDescription": "AudioAtlas internal Windows candidate build 42",
        },
        "signature_status": "NotSigned",
        "expected_version": "0.2.0a7",
        "expected_build": 42,
    }


def test_setup_distribution_contract_accepts_exact_internal_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    audit = _script("audit_windows_distribution")

    result = audit._validate_setup_contract(**_valid_setup_contract(audit))

    assert result["requested_execution_level"] == "asInvoker"
    assert result["signature_status"] == "unsigned-internal"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("machine", 0x14C, "not AMD64"),
        ("imports", ["mystery.dll"], "unresolved"),
        (
            "manifest",
            '<requestedExecutionLevel level="requireAdministrator" uiAccess="false"/>',
            "asInvoker",
        ),
        ("signature_status", "Valid", "must be NotSigned"),
    ],
)
def test_setup_distribution_contract_rejects_unsafe_variants(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
    message: str,
) -> None:
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    audit = _script("audit_windows_distribution")
    contract = _valid_setup_contract(audit)
    contract[field] = value

    with pytest.raises(SystemExit, match=message):
        audit._validate_setup_contract(**contract)
