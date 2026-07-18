"""Platform-neutral lifecycle controller for native AudioAtlas desktop shells."""

from __future__ import annotations

import errno
import logging
import threading
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from audioatlas.app_core import (
    AppInputInfo,
    analyze_for_app,
    friendly_error_message,
    inspect_app_input,
    preflight_app_output,
)
from audioatlas.desktop_runtime import configure_desktop_logger
from audioatlas.errors import AnalysisCancelled, AudioAtlasError
from audioatlas.run_contract import (
    AnalysisProgress,
    AnalysisRunResult,
    CancellationToken,
    DesktopBusyError,
    DesktopRunPhase,
    DesktopRunState,
)

StateCallback = Callable[[DesktopRunState], None]

_OUTPUT_LOCATION_ERRNOS = {
    errno.EACCES,
    errno.EPERM,
    errno.EROFS,
    errno.ENOSPC,
}

_PROGRESS_PHASES = {
    "loading": DesktopRunPhase.LOADING,
    "measuring": DesktopRunPhase.MEASURING,
    "rendering": DesktopRunPhase.RENDERING,
    "publishing": DesktopRunPhase.PUBLISHING,
}


class DesktopRunController:
    """Own one desktop analysis worker and its complete interaction lifecycle.

    State callbacks originate on the managed worker. Native adapters must
    marshal them to their UI thread before touching controls.
    """

    def __init__(
        self,
        state_callback: StateCallback | None = None,
        *,
        logger: logging.Logger | None = None,
        inspector: Callable[[str | Path], AppInputInfo] | None = None,
        output_preflight: Callable[..., Path] | None = None,
        analyzer: Callable[..., AnalysisRunResult] | None = None,
    ) -> None:
        self._callback = state_callback
        self._logger = logger or configure_desktop_logger()
        self._inspector = inspector or inspect_app_input
        self._output_preflight = output_preflight or preflight_app_output
        self._analyzer = analyzer or analyze_for_app
        self._lock = threading.RLock()
        self._state = DesktopRunState()
        self._worker: threading.Thread | None = None
        self._token: CancellationToken | None = None
        self._confirmation_event = threading.Event()
        self._confirmation: bool | None = None
        self._output_event = threading.Event()
        self._output_parent: Path | None = None
        self._output_answered = False
        self._input_info: AppInputInfo | None = None

    @property
    def state(self) -> DesktopRunState:
        with self._lock:
            return self._state

    @property
    def input_info(self) -> AppInputInfo | None:
        """Most recently inspected metadata for a pending confirmation dialog."""

        with self._lock:
            return self._input_info

    def start(
        self, source: str | Path, output_parent: str | Path | None = None
    ) -> None:
        """Start one managed non-daemon run and return without blocking."""

        source_path = Path(source).expanduser()
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                raise DesktopBusyError("AudioAtlas is already analyzing a track.")
            self._token = CancellationToken()
            self._confirmation_event = threading.Event()
            self._confirmation = None
            self._output_event = threading.Event()
            self._output_parent = None
            self._output_answered = False
            self._input_info = None
            self._state = DesktopRunState(
                phase=DesktopRunPhase.INSPECTING,
                message=f"Inspecting {source_path.name}…",
                source=source_path,
                previous_result=self._state.previous_result,
            )
            self._worker = threading.Thread(
                target=self._run,
                args=(source_path, None if output_parent is None else Path(output_parent)),
                daemon=False,
                name="AudioAtlas analysis",
            )
            self._worker.start()

    def respond_to_large_file(self, accepted: bool) -> bool:
        """Resolve the current large-file prompt exactly once."""

        with self._lock:
            if (
                self._state.phase is not DesktopRunPhase.AWAITING_CONFIRMATION
                or self._confirmation is not None
            ):
                return False
            self._confirmation = bool(accepted)
            self._confirmation_event.set()
            return True

    def provide_output_parent(self, path_or_none: str | Path | None) -> bool:
        """Resolve the current write-location prompt; ``None`` cancels it."""

        with self._lock:
            if (
                self._state.phase is not DesktopRunPhase.AWAITING_OUTPUT_LOCATION
                or self._output_answered
            ):
                return False
            self._output_parent = None if path_or_none is None else Path(path_or_none)
            self._output_answered = True
            self._output_event.set()
            return True

    def cancel(self) -> bool:
        with self._lock:
            token = self._token
            if token is None or not self._state.is_active:
                return False
            token.cancel()
            self._confirmation_event.set()
            self._output_event.set()
            return True

    def request_shutdown(self) -> bool:
        """Request cooperative cleanup before a native shell terminates."""

        return self.cancel()

    def wait(self, timeout: float | None = None) -> bool:
        """Wait for cleanup; return false if the worker remains active."""

        with self._lock:
            worker = self._worker
        if worker is None:
            return True
        worker.join(timeout)
        return not worker.is_alive()

    def _run(self, source: Path, output_parent: Path | None) -> None:
        token = self._require_token()
        try:
            self._publish(
                DesktopRunPhase.INSPECTING,
                f"Inspecting {source.name}…",
            )
            self._logger.info("Input inspection started")
            info = self._inspector(source)
            with self._lock:
                self._input_info = info
            token.raise_if_cancelled()

            if info.needs_large_file_confirmation:
                self._publish(
                    DesktopRunPhase.AWAITING_CONFIRMATION,
                    "Waiting for confirmation…",
                )
                self._logger.info("Waiting for large-file confirmation")
                self._wait_for_confirmation(token)

            while True:
                try:
                    preflighted_output_dir = self._output_preflight(
                        source,
                        output_parent=output_parent,
                    )
                    break
                except OSError as error:
                    if not isinstance(error, PermissionError) and (
                        error.errno not in _OUTPUT_LOCATION_ERRNOS
                    ):
                        raise
                    token.raise_if_cancelled()
                    self._publish(
                        DesktopRunPhase.AWAITING_OUTPUT_LOCATION,
                        "AudioAtlas could not write beside this file. Choose another report location.",
                    )
                    self._logger.info("Waiting for an alternate output location")
                    output_parent = self._wait_for_output_parent(token)

            token.raise_if_cancelled()
            self._publish(
                DesktopRunPhase.INITIALIZING,
                "Starting the local analysis engine…",
            )
            self._logger.info("Scientific engine initialization started")
            result = self._analyzer(
                source,
                output_parent=output_parent,
                _preflighted_output_dir=preflighted_output_dir,
                progress_callback=self._on_progress,
                cancellation_token=token,
            )

            self._logger.info("Report publication completed")
            self._publish(
                DesktopRunPhase.SUCCEEDED,
                "Report ready — opening in your browser.",
                previous_result=result,
            )
        except AnalysisCancelled as error:
            self._logger.info("Analysis canceled")
            self._publish(
                DesktopRunPhase.CANCELLED,
                friendly_error_message(error),
                error=friendly_error_message(error),
            )
        except Exception as error:
            expected = isinstance(error, AudioAtlasError)
            if expected:
                self._logger.info("Analysis stopped: %s", type(error).__name__)
            else:
                self._logger.exception("Unexpected analysis failure")
            message = friendly_error_message(error)
            self._publish(
                DesktopRunPhase.FAILED,
                message,
                error=message,
                show_log=not expected,
            )
        finally:
            with self._lock:
                self._token = None

    def _wait_for_confirmation(self, token: CancellationToken) -> None:
        while not self._confirmation_event.wait(0.05):
            token.raise_if_cancelled()
        token.raise_if_cancelled()
        with self._lock:
            accepted = self._confirmation is True
        if not accepted:
            raise AnalysisCancelled(
                "Analysis canceled before loading. The previous report was unchanged."
            )
        self._logger.info("Large-file analysis confirmed")

    def _wait_for_output_parent(self, token: CancellationToken) -> Path:
        while not self._output_event.wait(0.05):
            token.raise_if_cancelled()
        token.raise_if_cancelled()
        with self._lock:
            parent = self._output_parent
            answered = self._output_answered
            self._output_event = threading.Event()
            self._output_answered = False
            self._output_parent = None
        if not answered or parent is None:
            raise AnalysisCancelled(
                "Analysis canceled while choosing a report location."
            )
        return parent

    def _on_progress(self, progress: AnalysisProgress) -> None:
        phase = _PROGRESS_PHASES.get(progress.stage)
        if phase is None:
            return
        self._logger.info("Analysis phase: %s", progress.stage)
        self._publish(phase, progress.message, progress=progress)

    def _publish(
        self,
        phase: DesktopRunPhase,
        message: str,
        *,
        progress: AnalysisProgress | None = None,
        previous_result: AnalysisRunResult | None = None,
        error: str | None = None,
        show_log: bool = False,
    ) -> None:
        with self._lock:
            old = self._state
            result = previous_result if previous_result is not None else old.previous_result
            token = self._token
            state = replace(
                old,
                phase=phase,
                message=message,
                progress=progress,
                cancellation_requested=bool(token and token.is_cancelled),
                previous_result=result,
                error=error,
                show_log=show_log,
            )
            self._state = state
            callback = self._callback
        if callback is not None:
            try:
                callback(state)
            except Exception:
                self._logger.exception("Desktop state callback failed")

    def _require_token(self) -> CancellationToken:
        with self._lock:
            if self._token is None:  # pragma: no cover - internal invariant
                raise RuntimeError("Desktop worker started without a cancellation token")
            return self._token
