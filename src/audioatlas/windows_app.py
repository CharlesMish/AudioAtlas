"""Tkinter adapter for the platform-neutral AudioAtlas desktop controller."""

from __future__ import annotations

import argparse
import queue
import subprocess
import sys
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from audioatlas.desktop_runtime import (
    configure_desktop_logger,
    configure_scientific_cache_environment,
    log_path,
)
from audioatlas.run_contract import DesktopRunPhase, DesktopRunState

if TYPE_CHECKING:
    from audioatlas.desktop_controller import DesktopRunController


@dataclass(frozen=True)
class WindowsViewState:
    """Presentation-only values derived from one controller snapshot."""

    status: str
    busy: bool
    choose_label: str
    cancel_enabled: bool
    show_report_controls: bool
    show_log: bool
    progress_completed: int | None = None
    progress_total: int | None = None


def view_state_for(state: DesktopRunState) -> WindowsViewState:
    """Map the shared lifecycle contract to Tk widget state."""

    result_available = state.previous_result is not None
    completed = state.progress.completed if state.progress else None
    total = state.progress.total if state.progress else None
    return WindowsViewState(
        status=state.message,
        busy=state.is_active,
        choose_label="Analyze Another" if result_available else "Choose Audio File",
        cancel_enabled=state.is_active and not state.cancellation_requested,
        show_report_controls=result_available,
        show_log=state.show_log,
        progress_completed=completed,
        progress_total=total,
    )


def open_local_file(path: Path) -> bool:
    """Ask the default Windows application to open a local file."""

    return bool(webbrowser.open(path.resolve().as_uri()))


def reveal_in_explorer(path: Path) -> bool:
    """Reveal a local file without invoking a command shell."""

    if sys.platform != "win32":
        return False
    try:
        subprocess.Popen(  # noqa: S603 - fixed Windows system executable
            ["explorer.exe", "/select,", str(path.resolve())],
            close_fds=True,
        )
    except OSError:
        return False
    return True


class WindowsDesktopApp:
    """Small Tk shell that delegates every run transition to the controller."""

    POLL_MILLISECONDS = 40

    def __init__(
        self,
        root: Any,
        *,
        controller_factory: Callable[..., DesktopRunController] | None = None,
    ) -> None:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk

        from audioatlas.desktop_controller import DesktopRunController

        self._tk = tk
        self._filedialog = filedialog
        self._messagebox = messagebox
        self._ttk = ttk
        self.root = root
        self.logger = configure_desktop_logger("audioatlas.windows_app")
        self.state_queue: queue.SimpleQueue[DesktopRunState] = queue.SimpleQueue()
        factory = controller_factory or DesktopRunController
        self.controller = factory(
            state_callback=self.state_queue.put,
            logger=self.logger,
        )
        self.last_result = None
        self.closing = False
        self.dialog_phase: DesktopRunPhase | None = None
        self._build_window()
        self.root.after(self.POLL_MILLISECONDS, self._drain_states)

    def _build_window(self) -> None:
        ttk = self._ttk
        self.root.title("AudioAtlas")
        self.root.geometry("620x430")
        self.root.minsize(560, 390)
        self.root.protocol("WM_DELETE_WINDOW", self.request_close)

        frame = ttk.Frame(self.root, padding=28)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text="AudioAtlas", font=("Segoe UI", 26, "bold")).grid(
            row=0, column=0, pady=(4, 8)
        )
        ttk.Label(
            frame,
            text="Choose one track to make a local listening map.",
            font=("Segoe UI", 11),
        ).grid(row=1, column=0, pady=(0, 22))

        self.source_text = self._tk.StringVar(value="No track selected")
        ttk.Label(frame, textvariable=self.source_text).grid(row=2, column=0, pady=(0, 8))
        self.status_text = self._tk.StringVar(
            value="WAV, FLAC, OGG, AIFF, or decoder-supported MP3"
        )
        ttk.Label(
            frame,
            textvariable=self.status_text,
            anchor="center",
            justify="center",
            wraplength=520,
        ).grid(row=3, column=0, sticky="ew", pady=(0, 12))

        self.progress = ttk.Progressbar(frame, mode="indeterminate", length=430)
        self.progress.grid(row=4, column=0, pady=(0, 18))
        self.progress.grid_remove()

        primary = ttk.Frame(frame)
        primary.grid(row=5, column=0, pady=(0, 14))
        self.choose_button = ttk.Button(
            primary, text="Choose Audio File", command=self.choose_audio, width=22
        )
        self.choose_button.grid(row=0, column=0, padx=5)
        self.cancel_button = ttk.Button(
            primary, text="Cancel", command=self.cancel, width=12, state="disabled"
        )
        self.cancel_button.grid(row=0, column=1, padx=5)

        reports = ttk.Frame(frame)
        reports.grid(row=6, column=0, pady=(0, 12))
        self.open_button = ttk.Button(
            reports, text="Open Report", command=self.open_report, width=17
        )
        self.open_button.grid(row=0, column=0, padx=4)
        self.reveal_button = ttk.Button(
            reports,
            text="Show Report in Explorer",
            command=self.reveal_report,
            width=25,
        )
        self.reveal_button.grid(row=0, column=1, padx=4)
        self.open_button.state(["disabled"])
        self.reveal_button.state(["disabled"])

        self.log_button = ttk.Button(
            frame,
            text="Open Troubleshooting Log",
            command=self.open_log,
            width=28,
        )
        self.log_button.grid(row=7, column=0, pady=(0, 16))
        self.log_button.grid_remove()

        ttk.Label(
            frame,
            text="Runs entirely on this PC. Audio never leaves your computer.",
            foreground="#666666",
        ).grid(row=8, column=0, pady=(8, 0))

    def choose_audio(self) -> None:
        if self.controller.state.is_active:
            return
        from audioatlas.app_core import SUPPORTED_AUDIO_EXTENSIONS

        patterns = " ".join(f"*{suffix}" for suffix in sorted(SUPPORTED_AUDIO_EXTENSIONS))
        selected = self._filedialog.askopenfilename(
            parent=self.root,
            title="Choose an audio file",
            filetypes=(("Audio files", patterns), ("All files", "*.*")),
        )
        if selected:
            self.start(Path(selected))

    def start(self, source: Path) -> None:
        from audioatlas.run_contract import DesktopBusyError

        try:
            self.controller.start(source)
        except DesktopBusyError:
            return
        self.source_text.set(source.name)
        self.status_text.set(f"Inspecting {source.name}…")
        self._set_busy(True)

    def cancel(self) -> None:
        state = self.controller.state
        if not state.is_active:
            return
        self.controller.cancel()
        self.cancel_button.state(["disabled"])
        message = (
            "Finishing the report safely before stopping…"
            if state.phase is DesktopRunPhase.PUBLISHING
            else "Canceling safely…"
        )
        self.status_text.set(message)

    def request_close(self) -> None:
        if not self.controller.state.is_active:
            self.root.destroy()
            return
        self.closing = True
        self.controller.request_shutdown()
        self.choose_button.state(["disabled"])
        self.cancel_button.state(["disabled"])
        self.status_text.set("Canceling safely before closing…")

    def _drain_states(self) -> None:
        latest: DesktopRunState | None = None
        while True:
            try:
                latest = self.state_queue.get_nowait()
            except queue.Empty:
                break
        if latest is not None:
            self._apply_state(latest)
        if self.closing and self.controller.wait(0):
            self.root.destroy()
            return
        try:
            self.root.after(self.POLL_MILLISECONDS, self._drain_states)
        except self._tk.TclError:
            return

    def _apply_state(self, state: DesktopRunState) -> None:
        view = view_state_for(state)
        self.status_text.set(view.status)
        self.choose_button.configure(text=view.choose_label)
        self._set_busy(view.busy)

        if view.show_report_controls:
            self.last_result = state.previous_result
            self.open_button.state(["!disabled"])
            self.reveal_button.state(["!disabled"])
        if view.show_log:
            self.log_button.grid()

        if view.progress_total:
            self.progress.stop()
            self.progress.configure(mode="determinate", maximum=view.progress_total)
            self.progress["value"] = view.progress_completed or 0

        if state.phase is DesktopRunPhase.AWAITING_CONFIRMATION:
            self._confirm_large_file()
        elif state.phase is DesktopRunPhase.AWAITING_OUTPUT_LOCATION:
            self._choose_output_parent()
        else:
            self.dialog_phase = None

        if (
            state.phase is DesktopRunPhase.SUCCEEDED
            and state.previous_result is not None
            and not self.closing
        ):
            opened = open_local_file(state.previous_result.html_report_path)
            self.logger.info("Browser-open request %s", "succeeded" if opened else "failed")
            if not opened:
                self.status_text.set(
                    "Report ready. Use Show Report in Explorer to open it."
                )
        if self.closing and not state.is_active:
            self.root.destroy()

    def _confirm_large_file(self) -> None:
        if self.dialog_phase is DesktopRunPhase.AWAITING_CONFIRMATION:
            return
        self.dialog_phase = DesktopRunPhase.AWAITING_CONFIRMATION
        info = self.controller.input_info
        if info is None or self.closing:
            self.controller.respond_to_large_file(False)
            return
        minutes = info.duration_seconds / 60
        decoded_gib = info.estimated_decoded_bytes / 1024**3
        accepted = self._messagebox.askyesno(
            "Unusually large analysis",
            f"{info.source.name} is about {minutes:.0f} minutes and may use at least "
            f"{decoded_gib:.1f} GiB while AudioAtlas works. Analyze anyway?",
            parent=self.root,
        )
        self.controller.respond_to_large_file(accepted)

    def _choose_output_parent(self) -> None:
        if self.dialog_phase is DesktopRunPhase.AWAITING_OUTPUT_LOCATION:
            return
        self.dialog_phase = DesktopRunPhase.AWAITING_OUTPUT_LOCATION
        if self.closing:
            self.controller.provide_output_parent(None)
            return
        selected = self._filedialog.askdirectory(
            parent=self.root,
            title="Choose a report location",
            mustexist=False,
        )
        self.controller.provide_output_parent(Path(selected) if selected else None)

    def _set_busy(self, busy: bool) -> None:
        if busy:
            self.choose_button.state(["disabled"])
            self.cancel_button.state(["!disabled"])
            self.progress.grid()
            if self.progress.cget("mode") != "determinate":
                self.progress.configure(mode="indeterminate")
                self.progress.start(12)
        else:
            self.choose_button.state(["!disabled"])
            self.cancel_button.state(["disabled"])
            self.progress.stop()
            self.progress.configure(mode="indeterminate")
            self.progress.grid_remove()

    def open_report(self) -> None:
        if self.last_result is None:
            return
        if not open_local_file(self.last_result.html_report_path):
            self.status_text.set("Windows could not open the report. Show it in Explorer instead.")

    def reveal_report(self) -> None:
        if self.last_result is None:
            return
        if not reveal_in_explorer(self.last_result.html_report_path):
            self.status_text.set("Windows could not reveal the report in Explorer.")

    def open_log(self) -> None:
        path = log_path()
        if path.is_file() and not open_local_file(path):
            self.status_text.set("Windows could not open the troubleshooting log.")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--smoke-analyze", type=Path)
    parser.add_argument("--output-parent", type=Path)
    parser.add_argument("--ui-smoke", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
    configure_scientific_cache_environment()

    if args.smoke_analyze is not None:
        if args.output_parent is None:
            raise SystemExit("--output-parent is required with --smoke-analyze")
        from audioatlas.desktop_smoke import run_frozen_smoke

        try:
            run_frozen_smoke(
                [
                    "--smoke-analyze",
                    str(args.smoke_analyze),
                    "--output-parent",
                    str(args.output_parent),
                ]
            )
        except Exception:
            configure_desktop_logger("audioatlas.windows_app").exception(
                "Frozen smoke analysis failed"
            )
            raise SystemExit(2) from None
        return

    if sys.platform != "win32":
        raise SystemExit("The AudioAtlas Windows app requires 64-bit Windows.")

    import tkinter as tk

    root = tk.Tk()
    WindowsDesktopApp(root)
    if args.ui_smoke:
        root.withdraw()
        root.update_idletasks()
        print("AudioAtlas Windows UI ready", flush=True)
        root.after(10, root.destroy)
    root.mainloop()


if __name__ == "__main__":
    main()
