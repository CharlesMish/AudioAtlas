"""Native macOS shell for one-drop AudioAtlas reports.

AppKit is imported only when this entry point runs, keeping the normal package
portable across every CLI platform.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from audioatlas.app_core import (
        AppInputInfo,
        AppPreparationProgress,
        LargeFileDecision,
    )
    from audioatlas.pipeline import AnalysisProgress, AnalysisRunResult

# Set persistent, user-writable scientific caches before importing the analysis
# stack. This removes repeated first-report initialization without hiding work.
_cache_root = Path.home() / "Library" / "Caches" / "AudioAtlas"
os.environ.setdefault("MPLCONFIGDIR", str(_cache_root / "matplotlib"))
os.environ.setdefault("NUMBA_CACHE_DIR", str(_cache_root / "numba"))
try:
    Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
    Path(os.environ["NUMBA_CACHE_DIR"]).mkdir(parents=True, exist_ok=True)
except OSError:
    # Matplotlib and Numba retain their own temporary-cache fallback for an
    # unusually restricted account; report generation remains available.
    pass

_log_path = Path.home() / "Library" / "Logs" / "AudioAtlas" / "app.log"
_logger = logging.getLogger("audioatlas.macos_app")
try:
    _log_path.parent.mkdir(parents=True, exist_ok=True)
    _handler = RotatingFileHandler(_log_path, maxBytes=1_048_576, backupCount=2)
    _handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)
except OSError:
    _logger.addHandler(logging.NullHandler())


def main() -> None:
    if sys.platform != "darwin":
        raise SystemExit("The AudioAtlas desktop app currently supports macOS only.")

    if "--smoke-analyze" in sys.argv:
        _run_frozen_smoke(sys.argv[1:])
        return

    from AppKit import (  # type: ignore[import-not-found]
        NSApplication,
        NSApplicationActivationPolicyRegular,
    )
    from PyObjCTools import AppHelper  # type: ignore[import-not-found]

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    delegate = _make_app_delegate()
    app.setDelegate_(delegate)
    AppHelper.runEventLoop()


def _run_frozen_smoke(argv: list[str]) -> None:
    """Exercise the real frozen engine without opening the interactive window."""

    from audioatlas.app_core import analyze_for_app

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--smoke-analyze", type=Path, required=True)
    parser.add_argument("--output-parent", type=Path, required=True)
    args = parser.parse_args(argv)
    result = analyze_for_app(args.smoke_analyze, output_parent=args.output_parent)
    if not result.html_report_path.is_file():
        raise SystemExit("Frozen smoke did not produce report.html")


def _make_app_delegate() -> Any:
    import objc  # type: ignore[import-not-found]
    from AppKit import (  # type: ignore[import-not-found]
        NSAlert,
        NSAlertFirstButtonReturn,
        NSApplication,
        NSApplicationDelegateReplySuccess,
        NSBackingStoreBuffered,
        NSButton,
        NSColor,
        NSDragOperationCopy,
        NSFont,
        NSMakeRect,
        NSOpenPanel,
        NSPasteboardTypeFileURL,
        NSPasteboardURLReadingFileURLsOnlyKey,
        NSProgressIndicator,
        NSTerminateLater,
        NSTerminateNow,
        NSTextField,
        NSView,
        NSWindow,
        NSWindowStyleMaskClosable,
        NSWindowStyleMaskMiniaturizable,
        NSWindowStyleMaskTitled,
        NSWorkspace,
    )
    from Foundation import (  # type: ignore[import-not-found]
        NSURL,
        NSObject,
    )
    from PyObjCTools import AppHelper  # type: ignore[import-not-found]

    from audioatlas.app_core import (
        SUPPORTED_AUDIO_EXTENSIONS,
        friendly_error_message,
        prepare_and_analyze_for_app,
    )
    from audioatlas.errors import AnalysisCancelled, AudioAtlasError
    from audioatlas.pipeline import CancellationToken

    class DropView(NSView):
        def initWithFrame_(self, frame: Any) -> Any:
            self = objc.super(DropView, self).initWithFrame_(frame)
            if self is not None:
                self.registerForDraggedTypes_([NSPasteboardTypeFileURL])
                self.on_file = None
            return self

        def draggingEntered_(self, sender: Any) -> int:
            return NSDragOperationCopy

        def performDragOperation_(self, sender: Any) -> bool:
            urls = sender.draggingPasteboard().readObjectsForClasses_options_(
                [NSURL], {NSPasteboardURLReadingFileURLsOnlyKey: True}
            )
            if not urls or len(urls) != 1 or self.on_file is None:
                return False
            self.on_file(Path(str(urls[0].path())))
            return True

    class AppDelegate(NSObject):
        def applicationDidFinishLaunching_(self, notification: Any) -> None:
            self.source_path: Path | None = None
            self.input_info: AppInputInfo | None = None
            self.last_result: AnalysisRunResult | None = None
            self.busy = False
            self.cancellation_token: CancellationToken | None = None
            self.worker: threading.Thread | None = None
            self.pending_termination = False
            self.close_after_worker = False
            self.publishing = False
            self.large_file_confirmed = False
            self.pending_large_decision: LargeFileDecision | None = None
            self.pending_large_alert: Any | None = None

            style = (
                NSWindowStyleMaskTitled
                | NSWindowStyleMaskClosable
                | NSWindowStyleMaskMiniaturizable
            )
            self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                NSMakeRect(0, 0, 560, 390), style, NSBackingStoreBuffered, False
            )
            self.window.setTitle_("AudioAtlas")
            self.window.setDelegate_(self)
            self.window.center()

            content = DropView.alloc().initWithFrame_(NSMakeRect(0, 0, 560, 390))
            content.on_file = self.submitFile_
            self.window.setContentView_(content)

            title = _label("AudioAtlas", NSMakeRect(36, 310, 488, 42), 30, bold=True)
            title.setAlignment_(1)
            content.addSubview_(title)

            subtitle = _label(
                "Drop one track here to make a local listening map.",
                NSMakeRect(36, 274, 488, 26),
                15,
            )
            subtitle.setAlignment_(1)
            content.addSubview_(subtitle)

            self.status = _label(
                "WAV, FLAC, OGG, AIFF, or decoder-supported MP3",
                NSMakeRect(50, 211, 460, 48),
                13,
            )
            self.status.setAlignment_(1)
            self.status.setLineBreakMode_(0)
            content.addSubview_(self.status)

            self.progress = NSProgressIndicator.alloc().initWithFrame_(
                NSMakeRect(90, 181, 380, 12)
            )
            self.progress.setIndeterminate_(True)
            self.progress.setDisplayedWhenStopped_(False)
            content.addSubview_(self.progress)

            self.choose_button = _button(
                "Choose Audio File", NSMakeRect(188, 126, 184, 38), self, "chooseAudio:"
            )
            self.choose_button.setKeyEquivalent_("\r")
            content.addSubview_(self.choose_button)

            self.cancel_button = _button(
                "Cancel", NSMakeRect(238, 126, 84, 38), self, "cancelAnalysis:"
            )
            self.cancel_button.setHidden_(True)
            content.addSubview_(self.cancel_button)

            self.reveal_button = _button(
                "Show Report in Finder", NSMakeRect(188, 78, 184, 32), self, "revealReport:"
            )
            self.reveal_button.setHidden_(True)
            content.addSubview_(self.reveal_button)

            self.log_button = _button(
                "Open Troubleshooting Log",
                NSMakeRect(188, 42, 184, 28),
                self,
                "openLog:",
            )
            self.log_button.setHidden_(True)
            content.addSubview_(self.log_button)

            privacy = _label(
                "Runs entirely on this Mac. Audio never leaves your computer.",
                NSMakeRect(36, 14, 488, 22),
                11,
            )
            privacy.setAlignment_(1)
            privacy.setTextColor_(NSColor.secondaryLabelColor())
            content.addSubview_(privacy)

            self.window.makeKeyAndOrderFront_(None)
            self.window.orderFrontRegardless()

        def applicationShouldTerminateAfterLastWindowClosed_(self, app: Any) -> bool:
            return True

        def applicationShouldTerminate_(self, app: Any) -> int:
            if not self.busy:
                return NSTerminateNow
            self.pending_termination = True
            self._requestCancellation_()
            return NSTerminateLater

        def windowShouldClose_(self, window: Any) -> bool:
            if not self.busy:
                return True
            self.close_after_worker = True
            self._requestCancellation_()
            return False

        def application_openFiles_(self, app: Any, filenames: list[str]) -> None:
            if len(filenames) == 1 and not self.busy:
                self.submitFile_(Path(filenames[0]))
            else:
                self.status.setStringValue_("Choose or drop one audio file at a time.")
            app.replyToOpenOrPrint_(NSApplicationDelegateReplySuccess)

        def chooseAudio_(self, sender: Any) -> None:
            if self.busy:
                return
            panel = NSOpenPanel.openPanel()
            panel.setCanChooseFiles_(True)
            panel.setCanChooseDirectories_(False)
            panel.setAllowsMultipleSelection_(False)
            panel.setAllowedFileTypes_(
                sorted(extension.removeprefix(".") for extension in SUPPORTED_AUDIO_EXTENSIONS)
            )
            if panel.runModal() == 1:
                self.submitFile_(Path(str(panel.URL().path())))

        def submitFile_(self, source: Path) -> None:
            if self.busy:
                return
            self.source_path = source
            self.input_info = None
            self.large_file_confirmed = False
            self.log_button.setHidden_(True)
            self._setBusy_(True)
            self.status.setStringValue_(f"Inspecting {source.name}…")
            self._startWorker_(source, None, None, False)

        def cancelAnalysis_(self, sender: Any) -> None:
            self._requestCancellation_()

        @objc.python_method
        def _requestCancellation_(self) -> None:
            if not self.busy or self.cancellation_token is None:
                return
            self.cancellation_token.cancel()
            if self.pending_large_decision is not None:
                self.pending_large_decision.resolve(False)
            if self.pending_large_alert is not None:
                try:
                    self.window.endSheet_(self.pending_large_alert.window())
                except Exception:
                    _logger.exception("Could not close the large-file confirmation sheet")
            self.cancel_button.setEnabled_(False)
            if self.publishing:
                self.status.setStringValue_("Finishing the report safely before stopping…")
            else:
                self.status.setStringValue_("Canceling safely…")

        @objc.python_method
        def _startWorker_(
            self,
            source: Path,
            output_parent: Path | None,
            input_info: AppInputInfo | None,
            large_file_confirmed: bool,
        ) -> None:
            self.cancellation_token = CancellationToken()
            self.worker = threading.Thread(
                target=self._prepareAndAnalyze_,
                args=(
                    source,
                    output_parent,
                    input_info,
                    large_file_confirmed,
                    self.cancellation_token,
                ),
                daemon=False,
                name="AudioAtlas analysis",
            )
            self.worker.start()

        @objc.python_method
        def _prepareAndAnalyze_(
            self,
            source: Path,
            output_parent: Path | None,
            input_info: AppInputInfo | None,
            large_file_confirmed: bool,
            cancellation_token: CancellationToken,
        ) -> None:
            try:
                result = prepare_and_analyze_for_app(
                    source,
                    output_parent=output_parent,
                    input_info=input_info,
                    large_file_confirmed=large_file_confirmed,
                    preparation_callback=lambda update: AppHelper.callAfter(
                        self._showPreparationProgress_, update
                    ),
                    inspection_callback=self._rememberInputInfo_,
                    confirmation_callback=lambda info, decision: AppHelper.callAfter(
                        self._showLargeConfirmation_, info, decision
                    ),
                    progress_callback=lambda update: AppHelper.callAfter(
                        self._showProgress_, update
                    ),
                    cancellation_token=cancellation_token,
                )
            except PermissionError as error:
                AppHelper.callAfter(self._requestFallback_, error)
            except Exception as error:
                if isinstance(error, AudioAtlasError):
                    _logger.info("Analysis stopped: %s", error)
                else:
                    _logger.exception("Unexpected analysis failure")
                AppHelper.callAfter(self._showFailure_, error)
            else:
                AppHelper.callAfter(self._showSuccess_, result)

        @objc.python_method
        def _rememberInputInfo_(self, input_info: AppInputInfo) -> None:
            self.input_info = input_info

        @objc.python_method
        def _showPreparationProgress_(self, update: AppPreparationProgress) -> None:
            _logger.info("Preparation phase: %s", update.stage)
            self.status.setStringValue_(update.message)

        @objc.python_method
        def _showLargeConfirmation_(
            self,
            input_info: AppInputInfo,
            decision: LargeFileDecision,
        ) -> None:
            if self.cancellation_token is None or self.cancellation_token.is_cancelled:
                decision.resolve(False)
                return
            self.input_info = input_info
            self.pending_large_decision = decision
            alert = NSAlert.alloc().init()
            self.pending_large_alert = alert
            alert.setMessageText_("This is an unusually large analysis.")
            minutes = input_info.duration_seconds / 60
            decoded_gib = input_info.estimated_decoded_bytes / 1024**3
            alert.setInformativeText_(
                f"{input_info.source.name} is about {minutes:.0f} minutes and may use at "
                f"least {decoded_gib:.1f} GiB while AudioAtlas works. You can cancel safely."
            )
            alert.addButtonWithTitle_("Analyze Anyway")
            alert.addButtonWithTitle_("Cancel")

            def completed(response: int) -> None:
                accepted = response == NSAlertFirstButtonReturn
                if accepted:
                    self.large_file_confirmed = True
                    _logger.info("Large-file analysis confirmed")
                else:
                    _logger.info("Large-file analysis declined")
                decision.resolve(accepted)
                if self.pending_large_decision is decision:
                    self.pending_large_decision = None
                    self.pending_large_alert = None

            alert.beginSheetModalForWindow_completionHandler_(self.window, completed)

        @objc.python_method
        def _showProgress_(self, update: AnalysisProgress) -> None:
            self.publishing = update.stage == "publishing"
            self.status.setStringValue_(update.message)
            if update.stage == "rendering" and update.total:
                self.progress.stopAnimation_(None)
                self.progress.setIndeterminate_(False)
                self.progress.setMinValue_(0)
                self.progress.setMaxValue_(update.total)
                self.progress.setDoubleValue_(update.completed or 0)

        @objc.python_method
        def _requestFallback_(self, error: PermissionError) -> None:
            if self.pending_termination or self.close_after_worker:
                self._setBusy_(False)
                self._finishPendingTermination_()
                return
            self._setBusy_(False)
            self.status.setStringValue_(friendly_error_message(error))
            panel = NSOpenPanel.openPanel()
            panel.setCanChooseFiles_(False)
            panel.setCanChooseDirectories_(True)
            panel.setCanCreateDirectories_(True)
            panel.setAllowsMultipleSelection_(False)
            panel.setPrompt_("Choose Report Location")
            if panel.runModal() == 1 and self.source_path is not None:
                self._setBusy_(True)
                self._startWorker_(
                    self.source_path,
                    Path(str(panel.URL().path())),
                    self.input_info,
                    self.large_file_confirmed,
                )
            else:
                self._finishPendingTermination_()

        @objc.python_method
        def _showFailure_(self, error: BaseException) -> None:
            self._setBusy_(False)
            self.status.setStringValue_(friendly_error_message(error))
            self.choose_button.setTitle_("Choose Another File")
            if not isinstance(error, (AnalysisCancelled, AudioAtlasError)):
                self.log_button.setHidden_(False)
            self._finishPendingTermination_()

        @objc.python_method
        def _showSuccess_(self, result: AnalysisRunResult) -> None:
            self.last_result = result
            self._setBusy_(False)
            self.status.setStringValue_("Report ready — opening in your browser.")
            self.choose_button.setTitle_("Analyze Another")
            self.reveal_button.setHidden_(False)
            if not self.pending_termination and not self.close_after_worker:
                opened = NSWorkspace.sharedWorkspace().openURL_(
                    NSURL.fileURLWithPath_(str(result.html_report_path))
                )
                if not opened:
                    _logger.info("Browser-open request was refused")
                    self.status.setStringValue_(
                        "Report ready. Open it with Show Report in Finder."
                    )
                else:
                    _logger.info("Browser-open request succeeded")
            self._finishPendingTermination_()

        def revealReport_(self, sender: Any) -> None:
            if self.last_result is None:
                return
            url = NSURL.fileURLWithPath_(str(self.last_result.html_report_path))
            NSWorkspace.sharedWorkspace().activateFileViewerSelectingURLs_([url])

        def openLog_(self, sender: Any) -> None:
            if _log_path.is_file():
                NSWorkspace.sharedWorkspace().openURL_(
                    NSURL.fileURLWithPath_(str(_log_path))
                )

        @objc.python_method
        def _finishPendingTermination_(self) -> None:
            self.worker = None
            self.cancellation_token = None
            self.publishing = False
            self.pending_large_decision = None
            self.pending_large_alert = None
            if self.pending_termination:
                NSApplication.sharedApplication().replyToApplicationShouldTerminate_(True)
                return
            if self.close_after_worker:
                self.close_after_worker = False
                self.window.performClose_(None)

        @objc.python_method
        def _setBusy_(self, busy: bool) -> None:
            self.busy = busy
            self.choose_button.setEnabled_(not busy)
            self.choose_button.setHidden_(busy)
            self.cancel_button.setHidden_(not busy)
            self.cancel_button.setEnabled_(busy)
            self.progress.setHidden_(not busy)
            if busy:
                self.progress.setIndeterminate_(True)
                self.progress.startAnimation_(None)
            else:
                self.progress.stopAnimation_(None)

    def _label(text: str, frame: Any, size: float, *, bold: bool = False) -> Any:
        field = NSTextField.alloc().initWithFrame_(frame)
        field.setStringValue_(text)
        field.setEditable_(False)
        field.setBezeled_(False)
        field.setDrawsBackground_(False)
        field.setSelectable_(False)
        font = NSFont.boldSystemFontOfSize_(size) if bold else NSFont.systemFontOfSize_(size)
        field.setFont_(font)
        return field

    def _button(text: str, frame: Any, target: Any, action: str) -> Any:
        button = NSButton.alloc().initWithFrame_(frame)
        button.setTitle_(text)
        button.setBezelStyle_(1)
        button.setTarget_(target)
        button.setAction_(action)
        return button

    return AppDelegate.alloc().init()


if __name__ == "__main__":
    main()
