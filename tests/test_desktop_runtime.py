from __future__ import annotations

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
