from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


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
    assert callable(delegate._prepareAndAnalyze_)
    assert callable(delegate._showLargeConfirmation_)


def test_cocoa_submission_starts_worker_before_metadata_inspection() -> None:
    source = (ROOT / "src" / "audioatlas" / "macos_app.py").read_text(encoding="utf-8")
    submit = source[source.index("def submitFile_") : source.index("def cancelAnalysis_")]

    assert "inspect_app_input" not in submit
    assert "_startWorker_" in submit
    assert 'daemon=False' in source
    assert "Starting the local analysis engine…" in source or "_showPreparationProgress_" in source


def test_bundle_contract_is_arm64_macos_14_and_has_no_openmp_pool() -> None:
    spec = (ROOT / "packaging" / "macos" / "AudioAtlas.spec").read_text(encoding="utf-8")
    hook = (ROOT / "packaging" / "macos" / "audioatlas_runtime_hook.py").read_text(
        encoding="utf-8"
    )
    build = (ROOT / "scripts" / "build_macos_app.py").read_text(encoding="utf-8")

    assert '"LSMinimumSystemVersion": "14.0"' in spec
    assert '"CFBundleVersion": bundle_build_version' in spec
    assert '"numba.np.ufunc.omppool"' in spec
    assert hook.index('NUMBA_THREADING_LAYER", "workqueue') < hook.index("import numba")
    assert 'dependency.startswith(("/System/", "/usr/lib/"))' in build
    assert 'requires macOS {minimum_version}' in build
