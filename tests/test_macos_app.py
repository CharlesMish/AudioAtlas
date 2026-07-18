from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _build_script():
    spec = importlib.util.spec_from_file_location(
        "build_macos_app",
        ROOT / "scripts" / "build_macos_app.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(sys.platform != "darwin", reason="native Cocoa contract")
def test_cocoa_delegate_imports_and_registers_without_prototype_errors():
    pytest.importorskip("AppKit")

    from audioatlas.macos_app import _make_app_delegate

    delegate = _make_app_delegate()

    assert type(delegate).__name__ == "AppDelegate"
    assert callable(delegate.applicationDidFinishLaunching_)
    assert callable(delegate.application_openFiles_)
    assert callable(delegate.applicationShouldTerminate_)
    assert callable(delegate.windowShouldClose_)
    assert callable(delegate.cancelAnalysis_)
    assert callable(delegate._applyControllerState_)
    assert callable(delegate._showLargeConfirmation_)


def test_cocoa_submission_starts_worker_before_metadata_inspection() -> None:
    source = (ROOT / "src" / "audioatlas" / "macos_app.py").read_text(encoding="utf-8")
    submit = source[source.index("def submitFile_") : source.index("def cancelAnalysis_")]

    assert "inspect_app_input" not in submit
    assert "controller.start" in submit
    controller = (ROOT / "src" / "audioatlas" / "desktop_controller.py").read_text(
        encoding="utf-8"
    )
    assert "daemon=False" in controller
    assert "Starting the local analysis engine…" in controller


def test_bundle_contract_is_arm64_macos_14_and_has_no_openmp_pool() -> None:
    spec = (ROOT / "packaging" / "macos" / "AudioAtlas.spec").read_text(encoding="utf-8")
    hook = (ROOT / "packaging" / "common" / "audioatlas_runtime_hook.py").read_text(
        encoding="utf-8"
    )
    build = (ROOT / "scripts" / "build_macos_app.py").read_text(encoding="utf-8")

    assert '"minimum_macos": "14.0"' in spec
    assert '"LSMinimumSystemVersion": PACKAGING_CONTRACT["minimum_macos"]' in spec
    assert '"CFBundleVersion": bundle_build_version' in spec
    assert '"numba.np.ufunc.omppool"' in spec
    assert hook.index('NUMBA_THREADING_LAYER", "workqueue') < hook.index("import numba")
    assert 'dependency.startswith(("/System/", "/usr/lib/"))' in build
    assert 'requires macOS {minimum_version}' in build
    assert "PYINSTALLER_TIMEOUT_SECONDS = 900" in build
    assert "shutil.rmtree" not in build


def test_build_preserves_a_preexisting_custom_work_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build = _build_script()
    work = tmp_path / "shared-work"
    work.mkdir()
    sentinel = work / "diagnostic.txt"
    sentinel.write_text("keep me", encoding="utf-8")
    dist = tmp_path / "dist"

    def fake_run(*args: str, **kwargs: object):
        (dist / "AudioAtlas.app").mkdir(parents=True)
        return type("Result", (), {"stdout": "", "stderr": ""})()

    monkeypatch.setattr(build.sys, "platform", "darwin")
    monkeypatch.setattr(build.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(build, "_run", fake_run)
    monkeypatch.setattr(build, "_audit_bundle", lambda app: None)

    assert build.main(["--dist", str(dist), "--work", str(work)]) == 0
    assert sentinel.read_text(encoding="utf-8") == "keep me"
