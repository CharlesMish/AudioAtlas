from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import audioatlas.desktop_runtime as runtime
from audioatlas.app_core import _portable_report_label


def test_runtime_paths_use_platformdirs(monkeypatch, tmp_path: Path) -> None:
    cache = tmp_path / "cache" / "AudioAtlas"
    logs = tmp_path / "logs" / "AudioAtlas"
    monkeypatch.setattr(runtime, "user_cache_path", lambda *args, **kwargs: cache)
    monkeypatch.setattr(runtime, "user_log_path", lambda *args, **kwargs: logs)

    assert runtime.cache_directory() == cache
    assert runtime.log_path() == logs / "app.log"


def test_scientific_cache_environment_is_per_user_and_created(
    monkeypatch, tmp_path: Path
) -> None:
    cache = tmp_path / "user cache" / "AudioAtlas"
    monkeypatch.setattr(runtime, "user_cache_path", lambda *args, **kwargs: cache)
    monkeypatch.delenv("MPLCONFIGDIR", raising=False)
    monkeypatch.delenv("NUMBA_CACHE_DIR", raising=False)

    runtime.configure_scientific_cache_environment()

    assert (cache / "matplotlib").is_dir()
    assert (cache / "numba").is_dir()


def test_report_labels_are_portable_to_win32() -> None:
    assert _portable_report_label("mix: final?.wav. ") == "mix_ final_.wav"
    assert _portable_report_label("CON") == "CON"
    assert _portable_report_label("... ") == "track"


def test_shared_desktop_modules_have_no_native_ui_or_hardcoded_macos_paths() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "audioatlas"
    for name in ("run_contract.py", "desktop_controller.py", "desktop_runtime.py"):
        source = (root / name).read_text(encoding="utf-8")
        assert "AppKit" not in source
        assert "Library/Caches" not in source
        assert "Library/Logs" not in source


def test_desktop_exception_boundary_logs_full_details_and_shows_only_generic_error(
    monkeypatch, tmp_path: Path
) -> None:
    log = tmp_path / "app.log"
    monkeypatch.setattr(runtime, "log_path", lambda: log)
    logger = runtime.configure_desktop_logger(f"audioatlas.test.{id(log)}")
    shown = []
    boundary = runtime.DesktopExceptionBoundary(logger, lambda: shown.append(True))
    private_path = tmp_path / "Users" / "private-user" / "song.wav"

    try:
        raise RuntimeError(f"decoder failed at {private_path}")
    except RuntimeError as exc:
        boundary(type(exc), exc, exc.__traceback__)

    for handler in logger.handlers:
        handler.flush()
    contents = log.read_text(encoding="utf-8")
    rotating_handlers = [
        handler for handler in logger.handlers if isinstance(handler, RotatingFileHandler)
    ]
    assert len(rotating_handlers) == 1
    assert rotating_handlers[0].maxBytes == 1_048_576
    assert rotating_handlers[0].backupCount == 2
    assert "Traceback (most recent call last)" in contents
    assert "RuntimeError" in contents
    assert str(private_path) in contents
    assert shown == [True]


def test_generic_gui_error_text_contains_no_local_or_traceback_details() -> None:
    visible = f"{runtime.GENERIC_GUI_ERROR_TITLE}\n{runtime.GENERIC_GUI_ERROR_MESSAGE}"

    assert "Traceback" not in visible
    assert Path.home().name not in visible
    assert str(Path.home()) not in visible
    assert ":\\" not in visible


def test_desktop_exception_boundary_contains_native_presenter_failure() -> None:
    records = []

    class Logger:
        def error(self, message: str, *, exc_info: object) -> None:
            records.append((message, exc_info))

        def exception(self, message: str) -> None:
            records.append((message, True))

    def fail_to_show() -> None:
        raise RuntimeError("native dialog failed")

    boundary = runtime.DesktopExceptionBoundary(Logger(), fail_to_show)  # type: ignore[arg-type]
    error = RuntimeError("startup failed")

    boundary(type(error), error, error.__traceback__)

    assert [record[0] for record in records] == [
        "Unhandled desktop GUI exception",
        "Could not display the generic desktop error message",
    ]


def test_installed_desktop_excepthook_is_scoped() -> None:
    previous = sys.excepthook
    logger = logging.getLogger("audioatlas.test.excepthook")
    boundary = runtime.DesktopExceptionBoundary(logger, lambda: None)

    with runtime.installed_desktop_excepthook(boundary):
        assert sys.excepthook is boundary

    assert sys.excepthook is previous
