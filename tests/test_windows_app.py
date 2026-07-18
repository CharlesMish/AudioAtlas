from __future__ import annotations

import queue
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from audioatlas.run_contract import (
    AnalysisProgress,
    AnalysisRunResult,
    DesktopRunPhase,
    DesktopRunState,
)
from audioatlas.windows_app import (
    WindowsDesktopApp,
    main,
    open_local_file,
    reveal_in_explorer,
    view_state_for,
)


def _result(tmp_path: Path) -> AnalysisRunResult:
    return AnalysisRunResult(
        out_dir=tmp_path,
        summary_path=tmp_path / "summary.json",
        findings_path=tmp_path / "findings.json",
        report_path=tmp_path / "report.md",
        html_report_path=tmp_path / "report.html",
        plot_paths=[],
        summary={},
        findings={},
    )


def test_windows_view_state_preserves_report_controls_during_new_run(tmp_path: Path) -> None:
    state = DesktopRunState(
        phase=DesktopRunPhase.RENDERING,
        message="Rendering plots",
        previous_result=_result(tmp_path),
        progress=AnalysisProgress("rendering", "Rendering plots", 2, 5),
    )

    view = view_state_for(state)

    assert view.busy
    assert view.cancel_enabled
    assert view.choose_label == "Analyze Another"
    assert view.show_report_controls
    assert (view.progress_completed, view.progress_total) == (2, 5)


def test_windows_view_state_offers_log_only_for_unexpected_failure() -> None:
    state = DesktopRunState(
        phase=DesktopRunPhase.FAILED,
        message="AudioAtlas could not create this report.",
        show_log=True,
    )

    view = view_state_for(state)

    assert not view.busy
    assert not view.cancel_enabled
    assert view.show_log


def test_windows_adapter_import_is_lightweight() -> None:
    code = """
import sys
import audioatlas.windows_app
heavy = {'numpy', 'scipy', 'matplotlib', 'numba', 'librosa', 'soundfile', 'tkinter', 'AppKit'}
print(','.join(sorted(name for name in heavy if name in sys.modules)))
"""
    completed = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == ""


def test_windows_main_refuses_native_ui_on_other_platforms(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("audioatlas.windows_app.sys.platform", "darwin")

    with pytest.raises(SystemExit, match="requires 64-bit Windows"):
        main([])


def test_open_local_file_returns_browser_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = tmp_path / "report.html"
    report.touch()
    opened = []
    monkeypatch.setattr(
        "audioatlas.windows_app.webbrowser.open",
        lambda uri: opened.append(uri) or False,
    )

    assert not open_local_file(report)
    assert opened == [report.resolve().as_uri()]


def test_reveal_refuses_non_windows_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("audioatlas.windows_app.sys.platform", "linux")

    assert not reveal_in_explorer(Path("report.html"))


def test_worker_state_queue_is_drained_on_ui_poll() -> None:
    applied = []
    scheduled = []
    app = WindowsDesktopApp.__new__(WindowsDesktopApp)
    app.state_queue = queue.SimpleQueue()
    app.state_queue.put(DesktopRunState(phase=DesktopRunPhase.INSPECTING, message="first"))
    latest = DesktopRunState(phase=DesktopRunPhase.INITIALIZING, message="latest")
    app.state_queue.put(latest)
    app._apply_state = applied.append
    app.closing = False
    app.controller = SimpleNamespace(wait=lambda timeout: False)
    app.root = SimpleNamespace(after=lambda delay, callback: scheduled.append((delay, callback)))

    app._drain_states()

    assert applied == [latest]
    assert scheduled[0][0] == WindowsDesktopApp.POLL_MILLISECONDS


def test_close_requests_shutdown_and_defers_destroy() -> None:
    calls = []

    class Widget:
        def state(self, values: list[str]) -> None:
            calls.append(tuple(values))

    app = WindowsDesktopApp.__new__(WindowsDesktopApp)
    app.controller = SimpleNamespace(
        state=DesktopRunState(phase=DesktopRunPhase.LOADING),
        request_shutdown=lambda: calls.append("shutdown"),
    )
    app.root = SimpleNamespace(destroy=lambda: calls.append("destroy"))
    app.choose_button = Widget()
    app.cancel_button = Widget()
    app.status_text = SimpleNamespace(set=lambda value: calls.append(value))
    app.closing = False

    app.request_close()

    assert app.closing
    assert "shutdown" in calls
    assert "destroy" not in calls
    assert "Canceling safely before closing…" in calls


def test_large_file_dialog_resolves_controller_on_main_thread(tmp_path: Path) -> None:
    answers = []
    source = tmp_path / "large.wav"
    app = WindowsDesktopApp.__new__(WindowsDesktopApp)
    app.dialog_phase = None
    app.closing = False
    app.root = object()
    app.controller = SimpleNamespace(
        input_info=SimpleNamespace(
            source=source,
            duration_seconds=31 * 60,
            estimated_decoded_bytes=1024**3,
        ),
        respond_to_large_file=answers.append,
    )
    app._messagebox = SimpleNamespace(askyesno=lambda *args, **kwargs: True)

    app._confirm_large_file()

    assert answers == [True]
    assert app.dialog_phase is DesktopRunPhase.AWAITING_CONFIRMATION


def test_reveal_reports_platform_process_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("audioatlas.windows_app.sys.platform", "win32")
    monkeypatch.setattr(
        "audioatlas.windows_app.subprocess.Popen",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("Explorer unavailable")),
    )

    assert not reveal_in_explorer(Path("report.html"))
