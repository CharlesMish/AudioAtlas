from __future__ import annotations

import hashlib
import importlib.util
import json
import stat
import struct
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_pe(path: Path, marker: bytes) -> None:
    payload = bytearray(512)
    payload[:2] = b"MZ"
    payload[60:64] = (128).to_bytes(4, "little")
    payload[128:132] = b"PE\x00\x00"
    payload[256 : 256 + len(marker)] = marker
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _distribution_audit(app: Path) -> dict[str, object]:
    records = []
    for path, classification in (
        (app / "AudioAtlas.exe", "executable"),
        (app / "library.dll", "dll"),
    ):
        records.append(
            {
                "path": path.relative_to(app).as_posix(),
                "size": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "pe_classification": classification,
                "architecture": "x86_64",
                "imports": [],
                "resolved_imports": [],
            }
        )
    canonical = json.dumps(
        records, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    root = hashlib.sha256(canonical).hexdigest()
    app_bundle = {
        "schema_version": 2,
        "architecture": "x86_64",
        "version": "0.2.0a8",
        "bundle_build": 42,
        "pe_files": records,
        "inventory_root_sha256": root,
    }
    return {
        "schema_version": 3,
        "architecture": "x86_64",
        "windows_targets": ["Windows 10 22H2 x64", "Windows 11 x64"],
        "minimum_windows_build": 19045,
        "signing_status": "unsigned-internal",
        "app_bundle": app_bundle,
        "installer": {
            "source_app_inventory_root_sha256": root,
            "version_strings": {
                "ProductVersion": "0.2.0a8",
                "FileVersion": "0.2.0a8",
            },
        },
    }


def _candidate_args(tmp_path: Path) -> SimpleNamespace:
    app = tmp_path / "app"
    app.mkdir()
    _write_pe(app / "AudioAtlas.exe", b"app")
    _write_pe(app / "library.dll", b"dll")
    installer = tmp_path / "source-setup.exe"
    installer.write_bytes(b"installer")
    audit = tmp_path / "windows-pe-audit.json"
    audit.write_text(
        json.dumps(_distribution_audit(app), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    licenses = tmp_path / "THIRD_PARTY_LICENSES.txt"
    licenses.write_text("licenses\n", encoding="utf-8")
    demo = tmp_path / "audioatlas_demo.wav"
    demo.write_bytes(b"RIFF demo")
    rights = tmp_path / "AUDIO_RIGHTS.md"
    rights.write_text("rights\n", encoding="utf-8")
    guide = tmp_path / "WINDOWS_DEMO_GUIDE.md"
    guide.write_text("guide\n", encoding="utf-8")
    out = tmp_path / "candidate"
    return SimpleNamespace(
        app=app,
        installer=installer,
        audit=audit,
        licenses=licenses,
        demo_audio=demo,
        rights=rights,
        guide=guide,
        out=out,
        version="0.2.0a8",
        build_number="42",
        commit="cafebabe" * 5,
        workflow_url="https://example.invalid/actions/runs/42",
    )


def _candidate(tmp_path: Path) -> Path:
    package = _script("package_windows_candidate")
    args = _candidate_args(tmp_path)
    package.package(args)
    return args.out


def test_candidate_verifier_round_trips_both_exact_kits(tmp_path: Path) -> None:
    verifier = _script("verify_windows_candidate")
    candidate = _candidate(tmp_path)
    extracted = tmp_path / "extracted"

    report = verifier.verify_candidate(candidate, extract_root=extracted)

    assert report["verified"] is True
    assert report["candidate_id"] == "0.2.0a8-build-42-cafebabecafe"
    assert {kit["role"] for kit in report["kits"]} == {"installer", "portable"}
    assert len(list((extracted / "installer").glob("*-setup.exe"))) == 1
    assert len(list((extracted / "portable").glob("*-portable.zip"))) == 1
    assert (extracted / "portable-app" / "AudioAtlas" / "AudioAtlas.exe").is_file()


def test_candidate_verifier_rejects_outer_hash_mismatch(tmp_path: Path) -> None:
    verifier = _script("verify_windows_candidate")
    candidate = _candidate(tmp_path)
    kit = next(candidate.glob("*-installer-test-kit.zip"))
    Path(f"{kit}.sha256").write_text(f"{'0' * 64}  {kit.name}\n", encoding="utf-8")

    with pytest.raises(verifier.CandidateVerificationError, match="checksum differs"):
        verifier.verify_candidate(candidate)


def test_candidate_verifier_rejects_rechecksummed_guide_with_unchanged_authority(
    tmp_path: Path,
) -> None:
    verifier = _script("verify_windows_candidate")
    candidate = _candidate(tmp_path)
    authoritative = candidate / "windows-candidate-manifest.json"
    authoritative_before = authoritative.read_bytes()
    kit = next(candidate.glob("*-installer-test-kit.zip"))
    replacement = tmp_path / "replacement.zip"
    with (
        zipfile.ZipFile(kit) as source,
        zipfile.ZipFile(replacement, "w", compression=zipfile.ZIP_DEFLATED) as target,
    ):
        payloads = {info.filename: source.read(info) for info in source.infolist()}
        guide_name = next(
            name for name in payloads if name.endswith("/DEMO_AND_ACCEPTANCE_GUIDE.md")
        )
        checksum_name = next(name for name in payloads if name.endswith("/SHA256SUMS.txt"))
        payloads[guide_name] = b"attacker-controlled acceptance instructions\n"
        lines = payloads[checksum_name].decode("utf-8").splitlines()
        guide_digest = hashlib.sha256(payloads[guide_name]).hexdigest()
        payloads[checksum_name] = (
            "\n".join(
                f"{guide_digest}  DEMO_AND_ACCEPTANCE_GUIDE.md"
                if line.endswith("  DEMO_AND_ACCEPTANCE_GUIDE.md")
                else line
                for line in lines
            )
            + "\n"
        ).encode("utf-8")
        for name, payload in payloads.items():
            target.writestr(name, payload)
    replacement.replace(kit)
    Path(f"{kit}.sha256").write_text(
        f"{hashlib.sha256(kit.read_bytes()).hexdigest()}  {kit.name}\n",
        encoding="utf-8",
    )

    assert authoritative.read_bytes() == authoritative_before
    with pytest.raises(verifier.CandidateVerificationError, match="authoritative manifest"):
        verifier.verify_candidate(candidate)


def test_candidate_verifier_requires_nested_manifest_to_equal_authority(
    tmp_path: Path,
) -> None:
    verifier = _script("verify_windows_candidate")
    candidate = _candidate(tmp_path)
    kit = next(candidate.glob("*-portable-test-kit.zip"))
    replacement = tmp_path / "replacement.zip"
    with (
        zipfile.ZipFile(kit) as source,
        zipfile.ZipFile(replacement, "w", compression=zipfile.ZIP_DEFLATED) as target,
    ):
        payloads = {info.filename: source.read(info) for info in source.infolist()}
        manifest_name = next(
            name for name in payloads if name.endswith("/windows-candidate-manifest.json")
        )
        checksum_name = next(name for name in payloads if name.endswith("/SHA256SUMS.txt"))
        nested = json.loads(payloads[manifest_name])
        nested["built_at"] = "2030-01-01T00:00:00+00:00"
        payloads[manifest_name] = (json.dumps(nested, indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        )
        digest = hashlib.sha256(payloads[manifest_name]).hexdigest()
        payloads[checksum_name] = (
            "\n".join(
                f"{digest}  windows-candidate-manifest.json"
                if line.endswith("  windows-candidate-manifest.json")
                else line
                for line in payloads[checksum_name].decode("utf-8").splitlines()
            )
            + "\n"
        ).encode("utf-8")
        for name, payload in payloads.items():
            target.writestr(name, payload)
    replacement.replace(kit)
    Path(f"{kit}.sha256").write_text(
        f"{hashlib.sha256(kit.read_bytes()).hexdigest()}  {kit.name}\n",
        encoding="utf-8",
    )

    with pytest.raises(verifier.CandidateVerificationError, match="authoritative manifest"):
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


def test_candidate_packaging_rejects_stale_native_audit(tmp_path: Path) -> None:
    package = _script("package_windows_candidate")
    args = _candidate_args(tmp_path)
    (args.app / "library.dll").write_bytes(b"replacement after audit")

    with pytest.raises(SystemExit, match="native audit is stale"):
        package.package(args)


def test_candidate_packaging_rechecks_immediately_before_archiving(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = _script("package_windows_candidate")
    args = _candidate_args(tmp_path)
    original = package.verify_app_inventory
    calls = 0

    def mutate_after_initial_check(app: Path, payload: object) -> str:
        nonlocal calls
        result = original(app, payload)
        calls += 1
        if calls == 1:
            (app / "library.dll").write_bytes(b"post-audit DLL replacement")
        return result

    monkeypatch.setattr(package, "verify_app_inventory", mutate_after_initial_check)
    with pytest.raises(SystemExit, match="became stale before packaging"):
        package.package(args)


def test_candidate_verifier_applies_member_count_limit_before_reading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    verifier = _script("verify_windows_candidate")
    path = tmp_path / "many.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("root/a", b"a")
        archive.writestr("root/b", b"b")
    with zipfile.ZipFile(path) as archive:
        monkeypatch.setattr(verifier, "MAX_ARCHIVE_MEMBERS", 1)
        monkeypatch.setattr(
            archive,
            "open",
            lambda *args, **kwargs: pytest.fail("member data was read before limits"),
        )
        with pytest.raises(verifier.CandidateVerificationError, match="member count"):
            verifier._safe_members(archive)


def test_candidate_verifier_rejects_archive_bomb_ratio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    verifier = _script("verify_windows_candidate")
    path = tmp_path / "bomb.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("root/bomb", b"0" * 100_000)
    monkeypatch.setattr(verifier, "MAX_COMPRESSION_RATIO", 2)
    with (
        zipfile.ZipFile(path) as archive,
        pytest.raises(verifier.CandidateVerificationError, match="compression ratio"),
    ):
        verifier._safe_members(archive)


@pytest.mark.parametrize(
    ("limit_name", "limit", "message"),
    [
        ("MAX_MEMBER_UNCOMPRESSED_BYTES", 5, "member exceeds"),
        ("MAX_TOTAL_UNCOMPRESSED_BYTES", 10, "total uncompressed"),
    ],
)
def test_candidate_verifier_rejects_uncompressed_size_limits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    limit_name: str,
    limit: int,
    message: str,
) -> None:
    verifier = _script("verify_windows_candidate")
    path = tmp_path / "large.zip"
    with zipfile.ZipFile(path, "w") as writer:
        writer.writestr("root/one", b"123456")
        writer.writestr("root/two", b"123456")
    monkeypatch.setattr(verifier, limit_name, limit)
    with (
        zipfile.ZipFile(path) as archive,
        pytest.raises(verifier.CandidateVerificationError, match=message),
    ):
        verifier._safe_members(archive)


def test_candidate_verifier_rejects_outer_archive_size_before_opening(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    verifier = _script("verify_windows_candidate")
    candidate = _candidate(tmp_path)
    monkeypatch.setattr(verifier, "MAX_CANDIDATE_ARCHIVE_BYTES", 1)
    monkeypatch.setattr(
        verifier.zipfile,
        "ZipFile",
        lambda *args, **kwargs: pytest.fail("oversized archive was opened"),
    )

    with pytest.raises(verifier.CandidateVerificationError, match="Archive size exceeds"):
        verifier.verify_candidate(candidate)


def test_candidate_verifier_rejects_corrupt_member(tmp_path: Path) -> None:
    verifier = _script("verify_windows_candidate")
    candidate = _candidate(tmp_path)
    kit = next(candidate.glob("*-installer-test-kit.zip"))
    with zipfile.ZipFile(kit) as archive:
        info = next(
            item for item in archive.infolist() if item.filename.endswith("/AUDIO_RIGHTS.md")
        )
        header = kit.read_bytes()[info.header_offset : info.header_offset + 30]
        filename_size, extra_size = struct.unpack_from("<HH", header, 26)
        data_offset = info.header_offset + 30 + filename_size + extra_size
    damaged = bytearray(kit.read_bytes())
    damaged[data_offset] ^= 0xFF
    kit.write_bytes(damaged)
    Path(f"{kit}.sha256").write_text(
        f"{hashlib.sha256(damaged).hexdigest()}  {kit.name}\n", encoding="utf-8"
    )

    with pytest.raises(verifier.CandidateVerificationError, match="Corrupt archive member"):
        verifier.verify_candidate(candidate)


def test_failed_streaming_extraction_removes_partial_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    verifier = _script("verify_windows_candidate")
    archive_path = tmp_path / "files.zip"
    with zipfile.ZipFile(archive_path, "w") as writer:
        writer.writestr("root/one.txt", b"one")
        writer.writestr("root/two.txt", b"two")
    destination = tmp_path / "extracted" / "role"
    original = verifier._stream_member
    calls = 0

    def fail_second(*args: object, **kwargs: object) -> tuple[str, int]:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise verifier.CandidateVerificationError("injected corrupt member")
        return original(*args, **kwargs)

    monkeypatch.setattr(verifier, "_stream_member", fail_second)
    with zipfile.ZipFile(archive_path) as archive:
        members = verifier._safe_members(archive)
        with pytest.raises(verifier.CandidateVerificationError, match="injected"):
            verifier._extract_transactionally(
                archive, members, root="root", destination=destination
            )
    assert not destination.exists()
    assert not list(destination.parent.glob(".role-partial-*"))


def test_candidate_manifest_rejects_missing_install_contract(tmp_path: Path) -> None:
    verifier = _script("verify_windows_candidate")
    candidate = _candidate(tmp_path)
    manifest = json.loads((candidate / "windows-candidate-manifest.json").read_text())
    del manifest["minimum_windows_build"]

    with pytest.raises(verifier.CandidateVerificationError, match="missing"):
        verifier._validate_manifest(manifest)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("candidate_id", "unrelated", "identity"),
        ("version", "0.2.0", "version"),
        ("python_version", "3.12", "runtime identity"),
        ("windows_targets", ["Windows 11 x64"], "Windows targets"),
        ("workflow_url", "http://example.invalid/run", "HTTPS"),
        ("built_at", "not-a-time", "timestamp"),
    ],
)
def test_candidate_manifest_rejects_semantically_invalid_identity(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    verifier = _script("verify_windows_candidate")
    candidate = _candidate(tmp_path)
    manifest = json.loads((candidate / "windows-candidate-manifest.json").read_text())
    manifest[field] = value

    with pytest.raises(verifier.CandidateVerificationError, match=message):
        verifier._validate_manifest(manifest)


def test_candidate_manifest_rejects_wrong_label_to_filename_mapping(tmp_path: Path) -> None:
    verifier = _script("verify_windows_candidate")
    candidate = _candidate(tmp_path)
    manifest = json.loads((candidate / "windows-candidate-manifest.json").read_text())
    manifest["components"]["acceptance_guide"]["filename"] = "WINDOWS_DEMO_GUIDE.md"

    with pytest.raises(verifier.CandidateVerificationError, match="acceptance_guide"):
        verifier._validate_manifest(manifest)


def _valid_setup_contract(audit):
    return {
        "machine": audit.AMD64_MACHINE,
        "imports": ["kernel32.dll", "api-ms-win-core-file-l1-1-0.dll"],
        "manifest": ('<requestedExecutionLevel level="asInvoker" uiAccess="false"/>'),
        "version_strings": {
            "ProductName": "AudioAtlas",
            "ProductVersion": "0.2.0a8",
            "FileVersion": "0.2.0a8",
            "FileDescription": "AudioAtlas internal Windows candidate build 42",
        },
        "signature_status": "NotSigned",
        "expected_version": "0.2.0a8",
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


def test_distribution_audit_rejects_app_changed_after_native_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    audit = _script("audit_windows_distribution")
    app = tmp_path / "app"
    app.mkdir()
    _write_pe(app / "AudioAtlas.exe", b"app")
    _write_pe(app / "library.dll", b"dll")
    bundle_audit = tmp_path / "bundle-audit.json"
    bundle_audit.write_text(json.dumps(_distribution_audit(app)["app_bundle"]), encoding="utf-8")
    installer = tmp_path / "setup.exe"
    installer.write_bytes(b"setup")
    (app / "library.dll").write_bytes(b"changed after audit")
    monkeypatch.setitem(sys.modules, "pefile", SimpleNamespace())

    with pytest.raises(SystemExit, match="PE audit is stale"):
        audit.audit_distribution(
            app_dir=app,
            bundle_audit=bundle_audit,
            installer=installer,
            signature_status="NotSigned",
            version="0.2.0a8",
            build_number=42,
        )


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
