from __future__ import annotations

import importlib.util
import json
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


def test_windows_build_refuses_non_windows_host(monkeypatch: pytest.MonkeyPatch) -> None:
    build = _script("build_windows_app")
    monkeypatch.setattr(build.sys, "platform", "darwin")

    with pytest.raises(SystemExit, match="x64 Windows"):
        build.main([])


def test_windows_version_metadata_accepts_alpha_version() -> None:
    build = _script("build_windows_app")

    payload = build._windows_version_info("0.2.0a7")

    assert "filevers=(0, 2, 0, 7)" in payload
    assert "ProductVersion', '0.2.0a7'" in payload
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

    assert (
        build.main(
            ["--dist", str(dist), "--work", str(work), "--audit", str(audit)]
        )
        == 0
    )
    assert sentinel.read_text(encoding="utf-8") == "retain"
    assert json.loads(audit.read_text(encoding="utf-8"))["bundle_build"] == 42


def test_windows_installer_is_strictly_per_user_and_has_no_app_registry() -> None:
    installer = (ROOT / "packaging" / "windows" / "AudioAtlas.iss").read_text(
        encoding="utf-8"
    )

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
    assert "VersionInfoVersion=0.2.0.7" in installer
    assert "VersionInfoProductVersion=0.2.0.7" in installer
    assert "VersionInfoTextVersion={#MyAppVersion}" in installer
    assert "VersionInfoProductTextVersion={#MyAppVersion}" in installer
    assert "internal Windows candidate build {#MyBuildNumber}" in installer
    for forbidden in ("[Registry]", "runascurrentuser", "PrivilegesRequired=admin"):
        assert forbidden not in installer


def test_windows_spec_is_onedir_x64_and_uses_shared_runtime_hook() -> None:
    spec = (ROOT / "packaging" / "windows" / "AudioAtlas.spec").read_text(
        encoding="utf-8"
    )

    assert '"layout": "onedir"' in spec
    assert '"architectures": ["x86_64"]' in spec
    assert '"common" / "audioatlas_runtime_hook.py"' in spec
    assert '"numba.np.ufunc.omppool"' in spec
    assert '"numba.np.ufunc.tbbpool"' in spec
    assert "COLLECT(" in spec


def test_windows_candidate_kit_contains_every_promised_file(tmp_path: Path) -> None:
    package = _script("package_windows_candidate")
    app = tmp_path / "app"
    app.mkdir()
    (app / "AudioAtlas.exe").write_bytes(b"PE app")
    installer = tmp_path / "source-setup.exe"
    installer.write_bytes(b"installer")
    audit = tmp_path / "windows-pe-audit.json"
    audit.write_text('{"schema_version": 1}\n', encoding="utf-8")
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
            version="0.2.0a7",
            build_number="42",
            commit="cafebabe" * 5,
            workflow_url="https://example.invalid/actions/runs/42",
        )
    )

    assert manifest["signing_status"] == "unsigned-internal"
    assert manifest["bundle_build"] == 42
    kit = next(out.glob("*-demo-kit.zip"))
    with zipfile.ZipFile(kit) as archive:
        basenames = {Path(name).name for name in archive.namelist()}
    promised = {
        "audioatlas_demo.wav",
        "AUDIO_RIGHTS.md",
        "DEMO_AND_ACCEPTANCE_GUIDE.md",
        "windows-candidate-manifest.json",
        "windows-pe-audit.json",
        "THIRD_PARTY_LICENSES.txt",
        "SHA256SUMS.txt",
    }
    assert promised <= basenames
    assert any(name.endswith("-portable.zip") for name in basenames)
    assert any(name.endswith("-setup.exe") for name in basenames)


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
                version="0.2.0a7",
                build_number="0",
                commit="cafebabe" * 5,
                workflow_url="https://example.invalid/run",
            )
        )
