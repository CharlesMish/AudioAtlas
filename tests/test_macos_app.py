from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _build_script():
    spec = importlib.util.spec_from_file_location(
        "build_macos_app",
        ROOT / "scripts" / "build_macos_app.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
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


@pytest.mark.skipif(sys.platform != "darwin", reason="native Cocoa contract")
def test_cocoa_main_menu_has_standard_about_and_quit_items():
    AppKit = pytest.importorskip("AppKit")

    from audioatlas.macos_app import _make_main_menu

    app = AppKit.NSApplication.sharedApplication()
    menu = _make_main_menu(app)
    app_menu = menu.itemAtIndex_(0).submenu()
    items = {
        item.title(): item
        for item in app_menu.itemArray()
        if not item.isSeparatorItem()
    }

    assert list(items) == [
        "About AudioAtlas",
        "Services",
        "Hide AudioAtlas",
        "Hide Others",
        "Show All",
        "Quit AudioAtlas",
    ]
    assert str(items["About AudioAtlas"].action()) == "orderFrontStandardAboutPanel:"
    assert str(items["Quit AudioAtlas"].action()) == "terminate:"
    assert items["Quit AudioAtlas"].keyEquivalent() == "q"
    assert items["Quit AudioAtlas"].target() is app


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
    assert '"LSApplicationCategoryType": PACKAGING_CONTRACT["application_category"]' in spec
    assert '"NSHumanReadableCopyright": PACKAGING_CONTRACT["copyright"]' in spec
    assert 'icon=str(root / "packaging" / "macos"' in spec
    assert (ROOT / "packaging" / "macos" / "AudioAtlas.icns").is_file()
    assert '"CFBundleVersion": bundle_build_version' in spec
    assert '"numba.np.ufunc.omppool"' in spec
    assert hook.index('NUMBA_THREADING_LAYER", "workqueue') < hook.index("import numba")
    assert "MACH_O_MAGICS" in build
    assert "_resolve_dependency(" in build
    assert "def _verify_code_signature" in build
    assert 'requires macOS {minimum_version}' in build
    assert "PYINSTALLER_TIMEOUT_SECONDS = 900" in build
    assert "shutil.rmtree" not in build
    assert "disable_windowed_traceback=True" in spec


def test_macos_startup_failure_is_logged_without_exposing_private_details(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import audioatlas.macos_app as macos_app

    private_detail = "/Users/private-user/Music/secret.wav"
    records = []
    shown = []
    previous_hook = sys.excepthook
    logger = SimpleNamespace(
        error=lambda message, *, exc_info: records.append((message, exc_info)),
        exception=lambda message: records.append((message, True)),
    )

    def fail_during_application_construction() -> None:
        assert sys.excepthook is not previous_hook
        raise RuntimeError(f"application construction failed at {private_detail}")

    monkeypatch.setattr(macos_app.sys, "platform", "darwin")
    monkeypatch.setattr(macos_app, "_logger", logger)
    monkeypatch.setattr(macos_app, "_run_native_gui", fail_during_application_construction)
    monkeypatch.setattr(macos_app, "_show_generic_error", lambda: shown.append(True))

    with pytest.raises(SystemExit) as exc_info:
        macos_app.main()

    assert exc_info.value.code == 1
    assert sys.excepthook is previous_hook
    assert shown == [True]
    assert private_detail in str(records[0][1][1])
    output = capsys.readouterr()
    assert output.out == output.err == ""


def test_macos_callback_failure_uses_controlled_excepthook(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import audioatlas.macos_app as macos_app

    records = []
    shown = []
    logger = SimpleNamespace(
        error=lambda message, *, exc_info: records.append((message, exc_info)),
        exception=lambda message: records.append((message, True)),
    )

    def dispatch_callback_failure() -> None:
        error = RuntimeError("callback at /Users/private-user/song.wav")
        sys.excepthook(type(error), error, error.__traceback__)

    monkeypatch.setattr(macos_app.sys, "platform", "darwin")
    monkeypatch.setattr(macos_app, "_logger", logger)
    monkeypatch.setattr(macos_app, "_run_native_gui", dispatch_callback_failure)
    monkeypatch.setattr(macos_app, "_show_generic_error", lambda: shown.append(True))

    macos_app.main()

    assert len(records) == 1
    assert shown == [True]
    output = capsys.readouterr()
    assert "Traceback" not in output.out + output.err
    assert "private-user" not in output.out + output.err


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
    monkeypatch.setattr(build, "_audit_bundle", lambda app: ())
    monkeypatch.setattr(build, "_verify_code_signature", lambda app: None)

    assert build.main(["--dist", str(dist), "--work", str(work)]) == 0
    assert sentinel.read_text(encoding="utf-8") == "keep me"
