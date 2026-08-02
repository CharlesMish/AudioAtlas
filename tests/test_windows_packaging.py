from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from audioatlas import __version__

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


def _candidate_audit(app: Path) -> dict[str, object]:
    path = app / "AudioAtlas.exe"
    record = {
        "path": "AudioAtlas.exe",
        "size": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "pe_classification": "executable",
        "architecture": "x86_64",
        "imports": [],
        "resolved_imports": [],
    }
    root = hashlib.sha256(
        json.dumps([record], ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )
    ).hexdigest()
    return {
        "schema_version": 3,
        "architecture": "x86_64",
        "windows_targets": ["Windows 10 22H2 x64", "Windows 11 x64"],
        "minimum_windows_build": 19045,
        "signing_status": "unsigned-internal",
        "app_bundle": {
            "schema_version": 2,
            "architecture": "x86_64",
            "version": "0.2.0a8",
            "bundle_build": 42,
            "pe_files": [record],
            "inventory_root_sha256": root,
        },
        "installer": {
            "source_app_inventory_root_sha256": root,
            "version_strings": {
                "ProductVersion": "0.2.0a8",
                "FileVersion": "0.2.0a8",
            },
        },
    }


def _write_minimal_pe(path: Path) -> None:
    payload = bytearray(256)
    payload[:2] = b"MZ"
    payload[60:64] = (128).to_bytes(4, "little")
    payload[128:132] = b"PE\x00\x00"
    path.write_bytes(payload)


def test_windows_build_refuses_non_windows_host(monkeypatch: pytest.MonkeyPatch) -> None:
    build = _script("build_windows_app")
    monkeypatch.setattr(build.sys, "platform", "darwin")

    with pytest.raises(SystemExit, match="x64 Windows"):
        build.main([])


def test_windows_version_metadata_accepts_alpha_version() -> None:
    build = _script("build_windows_app")

    payload = build._windows_version_info("0.2.0a8")

    assert "filevers=(0, 2, 0, 8)" in payload
    assert "ProductVersion', '0.2.0a8'" in payload
    assert "OriginalFilename', 'AudioAtlas.exe'" in payload


def test_windows_build_preserves_custom_work_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build = _script("build_windows_app")
    work = tmp_path / "shared-work"
    work.mkdir()
    sentinel = work / "diagnostic.txt"
    sentinel.write_text("retain", encoding="utf-8")
    dist = tmp_path / "dist"
    audit = tmp_path / "audit.json"

    def fake_build(*args: object, **kwargs: object) -> SimpleNamespace:
        app = dist / "AudioAtlas"
        app.mkdir(parents=True)
        (app / "AudioAtlas.exe").write_bytes(b"PE")
        return SimpleNamespace(stdout="", stderr="")

    monkeypatch.setattr(build.sys, "platform", "win32")
    monkeypatch.setattr(build.sys, "version_info", (3, 11))
    monkeypatch.setattr(build.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(build, "_run_with_environment", fake_build)
    monkeypatch.setattr(
        build,
        "audit_windows_bundle",
        lambda app: {"schema_version": 1, "pe_files": []},
    )
    monkeypatch.setenv("AUDIOATLAS_BUNDLE_BUILD_NUMBER", "42")

    assert build.main(["--dist", str(dist), "--work", str(work), "--audit", str(audit)]) == 0
    assert sentinel.read_text(encoding="utf-8") == "retain"
    assert json.loads(audit.read_text(encoding="utf-8"))["bundle_build"] == 42


def _expected_installer_numeric_version() -> str:
    """Derive the installer's four-part numeric version from the package version.

    ``build_windows_app._windows_version_info`` is the single production place
    that maps a PEP 440 alpha version (``0.2.0a8``) to the Windows four-part
    numeric tuple (``0.2.0.8``) used for the frozen app's own version resource.
    Reusing it here keeps the Inno Setup installer's numeric version locked to
    the app it installs, so a future alpha bump cannot silently reintroduce the
    drift that once left the installer pinned to a stale ``0.2.0.7``.
    """

    build = _script("build_windows_app")
    version_info = build._windows_version_info(__version__)
    match = re.search(r"filevers=\((\d+), (\d+), (\d+), (\d+)\)", version_info)
    assert match is not None, version_info
    return ".".join(match.groups())


def test_windows_installer_is_strictly_per_user_and_has_no_app_registry() -> None:
    installer = (ROOT / "packaging" / "windows" / "AudioAtlas.iss").read_text(encoding="utf-8")

    required = (
        "PrivilegesRequired=lowest",
        r"DefaultDirName={localappdata}\Programs\AudioAtlas",
        "SetupArchitecture=x64",
        "ArchitecturesAllowed=x64os",
        "MinVersion=10.0.19045",
        "ChangesAssociations=no",
        "ChangesEnvironment=no",
    )
    for marker in required:
        assert marker in installer
    # The installer's binary numeric version must track the authoritative package
    # version (0.2.0a8 -> 0.2.0.8), not a hardcoded literal. This fails against
    # the previously stale 0.2.0.7 and guards future alpha bumps from drifting.
    expected_numeric = _expected_installer_numeric_version()
    assert expected_numeric == "0.2.0.8"
    assert f"VersionInfoVersion={expected_numeric}" in installer
    assert f"VersionInfoProductVersion={expected_numeric}" in installer
    assert "VersionInfoTextVersion={#MyAppVersion}" in installer
    assert "VersionInfoProductTextVersion={#MyAppVersion}" in installer
    assert "internal Windows candidate build {#MyBuildNumber}" in installer
    for forbidden in ("[Registry]", "runascurrentuser", "PrivilegesRequired=admin"):
        assert forbidden not in installer


def test_windows_acceptance_guide_is_installer_first_and_security_preserving() -> None:
    guide = (ROOT / "docs" / "WINDOWS_DEMO_GUIDE.md").read_text(encoding="utf-8")

    assert "Get-FileHash -Algorithm SHA256" in guide
    assert "installer-test-kit.zip" in guide
    assert "%LOCALAPPDATA%\\Programs\\AudioAtlas" in guide
    assert guide.index("Windows 11 compatibility evidence") < guide.index(
        "Windows 10 22H2 compatibility evidence"
    )
    assert "Do not disable or bypass Windows security controls" in guide
    assert "must not request administrator access" in guide


def test_windows_spec_is_onedir_x64_and_uses_shared_runtime_hook() -> None:
    spec = (ROOT / "packaging" / "windows" / "AudioAtlas.spec").read_text(encoding="utf-8")

    assert '"layout": "onedir"' in spec
    assert '"architectures": ["x86_64"]' in spec
    assert '"common" / "audioatlas_runtime_hook.py"' in spec
    assert '"numba.np.ufunc.omppool"' in spec
    assert '"numba.np.ufunc.tbbpool"' in spec
    assert "COLLECT(" in spec
    assert "disable_windowed_traceback=True" in spec

    build = (ROOT / "scripts" / "build_windows_app.py").read_text(encoding="utf-8")
    assert "_has_pe_headers(" in build
    assert "inventory_root_sha256" in build
    assert "_resolve_pe_import(" in build


def test_windows_candidate_kit_contains_every_promised_file(tmp_path: Path) -> None:
    package = _script("package_windows_candidate")
    app = tmp_path / "app"
    app.mkdir()
    _write_minimal_pe(app / "AudioAtlas.exe")
    installer = tmp_path / "source-setup.exe"
    installer.write_bytes(b"installer")
    audit = tmp_path / "windows-pe-audit.json"
    audit.write_text(
        json.dumps(_candidate_audit(app), indent=2, sort_keys=True) + "\n",
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
    out = tmp_path / "out"

    manifest = package.package(
        SimpleNamespace(
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
    )

    assert manifest["signing_status"] == "unsigned-internal"
    assert manifest["bundle_build"] == 42
    assert manifest["schema_version"] == 3
    assert manifest["minimum_windows_build"] == 19045
    assert manifest["installation_scope"] == "per-user"
    assert manifest["default_install_location"] == r"%LOCALAPPDATA%\Programs\AudioAtlas"
    assert manifest["requires_administrator"] is False
    assert manifest["components"]["acceptance_guide"]["filename"] == (
        "DEMO_AND_ACCEPTANCE_GUIDE.md"
    )
    assert set(manifest["native_inventory"]["bindings"].values()) == {
        manifest["native_inventory"]["root_sha256"]
    }
    assert set(manifest["components"]) == {
        "installer",
        "portable",
        "demo_audio",
        "pe_audit",
        "license_inventory",
        "rights_notice",
        "acceptance_guide",
    }
    kits = {
        "installer": next(out.glob("*-installer-test-kit.zip")),
        "portable": next(out.glob("*-portable-test-kit.zip")),
    }
    common = {
        "audioatlas_demo.wav",
        "AUDIO_RIGHTS.md",
        "DEMO_AND_ACCEPTANCE_GUIDE.md",
        "windows-candidate-manifest.json",
        "windows-pe-audit.json",
        "THIRD_PARTY_LICENSES.txt",
        "SHA256SUMS.txt",
    }
    for role, kit in kits.items():
        with zipfile.ZipFile(kit) as archive:
            basenames = {Path(name).name for name in archive.namelist()}
        assert common <= basenames
        assert Path(f"{kit}.sha256").is_file()
        if role == "installer":
            assert any(name.endswith("-setup.exe") for name in basenames)
            assert not any(name.endswith("-portable.zip") for name in basenames)
        else:
            assert any(name.endswith("-portable.zip") for name in basenames)
            assert not any(name.endswith("-setup.exe") for name in basenames)
    assert "installer-test-kit" in (out / "README_FIRST.txt").read_text(encoding="utf-8")


def test_windows_candidate_rejects_nonpositive_build(tmp_path: Path) -> None:
    package = _script("package_windows_candidate")

    with pytest.raises(SystemExit, match="positive integer"):
        package.package(
            SimpleNamespace(
                app=tmp_path,
                installer=tmp_path / "missing",
                audit=tmp_path / "missing",
                licenses=tmp_path / "missing",
                demo_audio=tmp_path / "missing",
                rights=tmp_path / "missing",
                guide=tmp_path / "missing",
                out=tmp_path / "out",
                version="0.2.0a8",
                build_number="0",
                commit="cafebabe" * 5,
                workflow_url="https://example.invalid/run",
            )
        )
