"""Native macOS adapter for the platform-neutral AudioAtlas controller."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from audioatlas.desktop_runtime import (
    configure_desktop_logger,
    configure_scientific_cache_environment,
    log_path,
)

# Choose writable caches before any path can import the scientific engine.
configure_scientific_cache_environment()
_log_path = log_path()
_logger = configure_desktop_logger("audioatlas.macos_app")


def main() -> None:
    if sys.platform != "darwin":
        raise SystemExit("The AudioAtlas desktop app currently supports macOS only.")

    if "--smoke-analyze" in sys.argv:
        from audioatlas.desktop_smoke import run_frozen_smoke

        run_frozen_smoke(sys.argv[1:])
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
    """Compatibility wrapper for existing packaging and rehearsal scripts."""

    from audioatlas.desktop_smoke import run_frozen_smoke

    run_frozen_smoke(argv)


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
    from Foundation import NSURL, NSObject  # type: ignore[import-not-found]
    from PyObjCTools import AppHelper  # type: ignore[import-not-found]

    from audioatlas.app_core import SUPPORTED_AUDIO_EXTENSIONS
    from audioatlas.desktop_controller import DesktopRunController
    from audioatlas.run_contract import (
        DesktopBusyError,
        DesktopRunPhase,
        DesktopRunState,
    )

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
            self.last_result = None
            self.pending_termination = False
            self.close_after_worker = False
            self.pending_large_alert: Any | None = None
            self.output_prompt_open = False
            self.controller = DesktopRunController(
                state_callback=lambda state: AppHelper.callAfter(
                    self._applyControllerState_, state
                ),
                logger=_logger,
            )

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

        @property
        def busy(self) -> bool:
            return self.controller.state.is_active

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
            self.log_button.setHidden_(True)
            try:
                self.controller.start(source)
            except DesktopBusyError:
                return
            self.status.setStringValue_(f"Inspecting {source.name}…")
            self._setBusy_(True)

        def cancelAnalysis_(self, sender: Any) -> None:
            self._requestCancellation_()

        @objc.python_method
        def _requestCancellation_(self) -> None:
            state = self.controller.state
            if not state.is_active:
                return
            self.controller.cancel()
            if self.pending_large_alert is not None:
                try:
                    self.window.endSheet_(self.pending_large_alert.window())
                except Exception:
                    _logger.exception("Could not close the large-file confirmation sheet")
                self.pending_large_alert = None
            self.cancel_button.setEnabled_(False)
            if state.phase is DesktopRunPhase.PUBLISHING:
                self.status.setStringValue_(
                    "Finishing the report safely before stopping…"
                )
            else:
                self.status.setStringValue_("Canceling safely…")

        @objc.python_method
        def _applyControllerState_(self, state: DesktopRunState) -> None:
            self.status.setStringValue_(state.message)
            if state.is_active:
                self._setBusy_(True)

            if state.phase is DesktopRunPhase.AWAITING_CONFIRMATION:
                self._showLargeConfirmation_()
                return
            if state.phase is DesktopRunPhase.AWAITING_OUTPUT_LOCATION:
                self._requestFallback_()
                return
            if state.phase is DesktopRunPhase.RENDERING and state.progress:
                progress = state.progress
                if progress.total:
                    self.progress.stopAnimation_(None)
                    self.progress.setIndeterminate_(False)
                    self.progress.setMinValue_(0)
                    self.progress.setMaxValue_(progress.total)
                    self.progress.setDoubleValue_(progress.completed or 0)
                return
            if state.phase is DesktopRunPhase.SUCCEEDED:
                self._showSuccess_(state)
            elif state.phase in {DesktopRunPhase.CANCELLED, DesktopRunPhase.FAILED}:
                self._showFailure_(state)

        @objc.python_method
        def _showLargeConfirmation_(self) -> None:
            if self.pending_large_alert is not None:
                return
            info = self.controller.input_info
            if info is None or not self.busy:
                self.controller.respond_to_large_file(False)
                return
            alert = NSAlert.alloc().init()
            self.pending_large_alert = alert
            alert.setMessageText_("This is an unusually large analysis.")
            minutes = info.duration_seconds / 60
            decoded_gib = info.estimated_decoded_bytes / 1024**3
            alert.setInformativeText_(
                f"{info.source.name} is about {minutes:.0f} minutes and may use at "
                f"least {decoded_gib:.1f} GiB while AudioAtlas works. You can cancel safely."
            )
            alert.addButtonWithTitle_("Analyze Anyway")
            alert.addButtonWithTitle_("Cancel")

            def completed(response: int) -> None:
                accepted = response == NSAlertFirstButtonReturn
                self.pending_large_alert = None
                self.controller.respond_to_large_file(accepted)

            alert.beginSheetModalForWindow_completionHandler_(self.window, completed)

        @objc.python_method
        def _requestFallback_(self) -> None:
            if self.output_prompt_open:
                return
            if self.pending_termination or self.close_after_worker:
                self.controller.provide_output_parent(None)
                return
            self.output_prompt_open = True
            panel = NSOpenPanel.openPanel()
            panel.setCanChooseFiles_(False)
            panel.setCanChooseDirectories_(True)
            panel.setCanCreateDirectories_(True)
            panel.setAllowsMultipleSelection_(False)
            panel.setPrompt_("Choose Report Location")
            selected = None
            if panel.runModal() == 1:
                selected = Path(str(panel.URL().path()))
            self.output_prompt_open = False
            self.controller.provide_output_parent(selected)

        @objc.python_method
        def _showFailure_(self, state: DesktopRunState) -> None:
            self._setBusy_(False)
            self.choose_button.setTitle_("Choose Another File")
            self.log_button.setHidden_(not state.show_log)
            self._finishPendingTermination_()

        @objc.python_method
        def _showSuccess_(self, state: DesktopRunState) -> None:
            result = state.previous_result
            if result is None:
                return
            self.last_result = result
            self._setBusy_(False)
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
            if self.pending_termination:
                NSApplication.sharedApplication().replyToApplicationShouldTerminate_(True)
                return
            if self.close_after_worker:
                self.close_after_worker = False
                self.window.performClose_(None)

        @objc.python_method
        def _setBusy_(self, busy: bool) -> None:
            self.choose_button.setEnabled_(not busy)
            self.choose_button.setHidden_(busy)
            self.cancel_button.setHidden_(not busy)
            self.cancel_button.setEnabled_(busy)
            self.progress.setHidden_(not busy)
            if busy:
                if self.controller.state.phase is not DesktopRunPhase.RENDERING:
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
