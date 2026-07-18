from __future__ import annotations

import errno
import logging
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from audioatlas.app_core import AppInputInfo
from audioatlas.desktop_controller import DesktopRunController
from audioatlas.errors import AudioLoadError
from audioatlas.run_contract import (
    AnalysisProgress,
    AnalysisRunResult,
    DesktopBusyError,
    DesktopRunPhase,
)


def _logger() -> logging.Logger:
    logger = logging.getLogger(f"audioatlas-test-{id(object())}")
    logger.addHandler(logging.NullHandler())
    return logger


def _info(source: Path, *, large: bool = False) -> AppInputInfo:
    seconds = 31 * 60 if large else 2
    frames = 48_000 * seconds
    return AppInputInfo(
        source=source,
        duration_seconds=seconds,
        samplerate=48_000,
        channels=2,
        frames=frames,
        estimated_decoded_bytes=frames * 2 * 4,
    )


def _result(root: Path, name: str = "report") -> AnalysisRunResult:
    out = root / name
    return AnalysisRunResult(
        out_dir=out,
        summary_path=out / "summary.json",
        findings_path=out / "findings.json",
        report_path=out / "report.md",
        html_report_path=out / "report.html",
        plot_paths=[],
        summary={},
        findings={},
    )


def test_controller_runs_complete_lifecycle_on_managed_worker(tmp_path: Path) -> None:
    source = tmp_path / "song.wav"
    source.touch()
    states = []
    callback_threads = []
    caller_thread = threading.get_ident()

    def analyze(path: Path, **kwargs: object) -> AnalysisRunResult:
        callback = kwargs["progress_callback"]
        assert callable(callback)
        callback(AnalysisProgress("loading", "Loading audio"))
        callback(AnalysisProgress("measuring", "Measuring track"))
        callback(AnalysisProgress("rendering", "Rendering plots", 1, 2))
        callback(AnalysisProgress("publishing", "Publishing report"))
        return _result(tmp_path)

    controller = DesktopRunController(
        lambda state: (states.append(state), callback_threads.append(threading.get_ident())),
        logger=_logger(),
        inspector=lambda path: _info(source),
        analyzer=analyze,
    )
    controller.start(source)

    assert controller.wait(2)
    assert [state.phase for state in states] == [
        DesktopRunPhase.INSPECTING,
        DesktopRunPhase.INITIALIZING,
        DesktopRunPhase.LOADING,
        DesktopRunPhase.MEASURING,
        DesktopRunPhase.RENDERING,
        DesktopRunPhase.PUBLISHING,
        DesktopRunPhase.SUCCEEDED,
    ]
    assert controller.state.previous_result == _result(tmp_path)
    assert all(thread_id != caller_thread for thread_id in callback_threads)


def test_controller_rejects_second_start_and_invalid_responses(tmp_path: Path) -> None:
    source = tmp_path / "song.wav"
    source.touch()
    entered = threading.Event()
    release = threading.Event()

    def inspect(path: Path) -> AppInputInfo:
        entered.set()
        release.wait(2)
        return _info(source)

    controller = DesktopRunController(
        logger=_logger(), inspector=inspect, analyzer=lambda *args, **kwargs: _result(tmp_path)
    )
    assert not controller.respond_to_large_file(True)
    assert not controller.provide_output_parent(tmp_path)
    controller.start(source)
    assert entered.wait(1)
    with pytest.raises(DesktopBusyError):
        controller.start(source)
    release.set()
    assert controller.wait(2)


@pytest.mark.parametrize("accepted", [True, False])
def test_controller_large_file_confirmation_starts_at_most_once(
    tmp_path: Path, accepted: bool
) -> None:
    source = tmp_path / "large.wav"
    source.touch()
    states = []
    calls = []
    waiting = threading.Event()

    def state_changed(state: object) -> None:
        states.append(state)
        if state.phase is DesktopRunPhase.AWAITING_CONFIRMATION:
            waiting.set()

    def analyze(*args: object, **kwargs: object) -> AnalysisRunResult:
        calls.append(args)
        return _result(tmp_path)

    controller = DesktopRunController(
        state_changed,
        logger=_logger(),
        inspector=lambda path: _info(source, large=True),
        analyzer=analyze,
    )
    controller.start(source)
    assert waiting.wait(1)
    assert controller.respond_to_large_file(accepted)
    assert not controller.respond_to_large_file(not accepted)
    assert controller.wait(2)
    assert len(calls) == int(accepted)
    expected = DesktopRunPhase.SUCCEEDED if accepted else DesktopRunPhase.CANCELLED
    assert controller.state.phase is expected


def test_controller_cancel_wakes_confirmation_and_shutdown_is_idempotent(
    tmp_path: Path,
) -> None:
    source = tmp_path / "large.wav"
    source.touch()
    waiting = threading.Event()
    controller = DesktopRunController(
        lambda state: waiting.set()
        if state.phase is DesktopRunPhase.AWAITING_CONFIRMATION
        else None,
        logger=_logger(),
        inspector=lambda path: _info(source, large=True),
        analyzer=lambda *args, **kwargs: pytest.fail("analysis should not start"),
    )
    controller.start(source)
    assert waiting.wait(1)
    assert controller.request_shutdown()
    assert controller.wait(2)
    assert controller.state.phase is DesktopRunPhase.CANCELLED
    assert not controller.cancel()


def test_controller_retries_permission_with_selected_parent_without_reinspection(
    tmp_path: Path,
) -> None:
    source = tmp_path / "song.wav"
    source.touch()
    inspections = []
    preflight_parents = []
    analysis_destinations = []
    waiting = threading.Event()

    def inspect(path: Path) -> AppInputInfo:
        inspections.append(path)
        return _info(source)

    def preflight(path: Path, **kwargs: object) -> Path:
        preflight_parents.append(kwargs["output_parent"])
        if len(preflight_parents) == 1:
            raise OSError(errno.EROFS, "read-only filesystem")
        return tmp_path / "report"

    def analyze(path: Path, **kwargs: object) -> AnalysisRunResult:
        analysis_destinations.append(
            (kwargs["output_parent"], kwargs["_preflighted_output_dir"])
        )
        return _result(tmp_path)

    controller = DesktopRunController(
        lambda state: waiting.set()
        if state.phase is DesktopRunPhase.AWAITING_OUTPUT_LOCATION
        else None,
        logger=_logger(),
        inspector=inspect,
        output_preflight=preflight,
        analyzer=analyze,
    )
    controller.start(source)
    assert waiting.wait(1)
    alternate = tmp_path / "reports"
    assert controller.provide_output_parent(alternate)
    assert controller.wait(2)
    assert inspections == [source]
    assert preflight_parents == [None, alternate]
    assert analysis_destinations == [(alternate, tmp_path / "report")]
    assert controller.state.previous_result == _result(tmp_path)
    assert controller.state.phase is DesktopRunPhase.SUCCEEDED


@pytest.mark.parametrize(
    "error_number",
    [errno.EACCES, errno.EPERM, errno.EROFS, errno.ENOSPC],
)
def test_controller_offers_fallback_for_output_location_errors(
    tmp_path: Path, error_number: int
) -> None:
    source = tmp_path / "song.wav"
    source.touch()
    waiting = threading.Event()
    attempts = 0

    def preflight(path: Path, **kwargs: object) -> Path:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError(error_number, "location unavailable")
        return tmp_path / "report"

    controller = DesktopRunController(
        lambda state: waiting.set()
        if state.phase is DesktopRunPhase.AWAITING_OUTPUT_LOCATION
        else None,
        logger=_logger(),
        inspector=lambda path: _info(source),
        output_preflight=preflight,
        analyzer=lambda *args, **kwargs: _result(tmp_path),
    )
    controller.start(source)
    assert waiting.wait(1)
    assert controller.provide_output_parent(tmp_path / "reports")
    assert controller.wait(2)
    assert attempts == 2
    assert controller.state.phase is DesktopRunPhase.SUCCEEDED


def test_controller_does_not_retry_analysis_after_late_permission_failure(
    tmp_path: Path,
) -> None:
    source = tmp_path / "song.wav"
    source.touch()
    calls = 0

    def analyze(*args: object, **kwargs: object) -> AnalysisRunResult:
        nonlocal calls
        calls += 1
        raise PermissionError(errno.EACCES, "late writer failure")

    controller = DesktopRunController(
        logger=_logger(),
        inspector=lambda path: _info(source),
        output_preflight=lambda *args, **kwargs: tmp_path / "report",
        analyzer=analyze,
    )
    controller.start(source)
    assert controller.wait(2)
    assert calls == 1
    assert controller.state.phase is DesktopRunPhase.FAILED


def test_controller_preserves_previous_success_across_later_failure(tmp_path: Path) -> None:
    source = tmp_path / "song.wav"
    source.touch()
    first = _result(tmp_path, "first")
    outcomes: list[object] = [first, AudioLoadError(source, "bad metadata")]

    def analyze(*args: object, **kwargs: object) -> AnalysisRunResult:
        outcome = outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    controller = DesktopRunController(
        logger=_logger(), inspector=lambda path: _info(source), analyzer=analyze
    )
    controller.start(source)
    assert controller.wait(2)
    controller.start(source)
    assert controller.wait(2)
    assert controller.state.phase is DesktopRunPhase.FAILED
    assert controller.state.previous_result is first
    assert not controller.state.show_log


def test_controller_hides_unexpected_error_details_and_offers_log(tmp_path: Path) -> None:
    source = tmp_path / "song.wav"
    source.touch()
    controller = DesktopRunController(
        logger=_logger(),
        inspector=lambda path: _info(source),
        analyzer=lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("secret at C:\\Users\\name\\song.wav")
        ),
    )
    controller.start(source)
    assert controller.wait(2)
    assert controller.state.phase is DesktopRunPhase.FAILED
    assert controller.state.show_log
    assert "Users" not in controller.state.message


def test_controller_and_run_contract_have_lightweight_import_boundary() -> None:
    code = """
import sys
import audioatlas.run_contract
import audioatlas.desktop_controller
heavy = {'numpy', 'scipy', 'matplotlib', 'numba', 'librosa', 'soundfile', 'AppKit'}
print(','.join(sorted(name for name in heavy if name in sys.modules)))
"""
    completed = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == ""


def test_pipeline_reexports_lightweight_analysis_contract() -> None:
    from audioatlas.pipeline import CancellationToken as PipelineToken
    from audioatlas.run_contract import CancellationToken

    assert PipelineToken is CancellationToken
