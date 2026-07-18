"""Lightweight contracts shared by analysis engines and desktop adapters.

This module deliberately imports no scientific stack, decoder, or native GUI
framework.  Desktop applications can therefore create their first window and
controller without paying AudioAtlas's analysis-engine startup cost.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from audioatlas.errors import AnalysisCancelled


@dataclass(frozen=True)
class AnalysisRunResult:
    """Paths and in-memory payloads produced by one successful analysis."""

    out_dir: Path
    summary_path: Path
    findings_path: Path
    report_path: Path
    html_report_path: Path
    plot_paths: list[Path]
    summary: dict[str, Any]
    findings: dict[str, Any]


AnalysisProgressStage = Literal[
    "loading",
    "measuring",
    "rendering",
    "publishing",
    "complete",
]


@dataclass(frozen=True)
class AnalysisProgress:
    """A coarse, presentation-neutral update from one analysis run."""

    stage: AnalysisProgressStage
    message: str
    completed: int | None = None
    total: int | None = None


class CancellationToken:
    """Thread-safe cooperative cancellation shared with UI callers."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled:
            raise AnalysisCancelled(
                "Analysis canceled. The previous report was unchanged."
            )


class DesktopRunPhase(StrEnum):
    """Stable phases understood by every native desktop adapter."""

    IDLE = "idle"
    INSPECTING = "inspecting"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    INITIALIZING = "initializing"
    LOADING = "loading"
    MEASURING = "measuring"
    RENDERING = "rendering"
    PUBLISHING = "publishing"
    AWAITING_OUTPUT_LOCATION = "awaiting_output_location"
    SUCCEEDED = "succeeded"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(frozen=True)
class DesktopRunState:
    """Immutable snapshot of a desktop controller's user-visible state."""

    phase: DesktopRunPhase = DesktopRunPhase.IDLE
    message: str = ""
    source: Path | None = None
    progress: AnalysisProgress | None = None
    cancellation_requested: bool = False
    previous_result: AnalysisRunResult | None = None
    error: str | None = None
    show_log: bool = False

    @property
    def is_active(self) -> bool:
        return self.phase not in {
            DesktopRunPhase.IDLE,
            DesktopRunPhase.SUCCEEDED,
            DesktopRunPhase.CANCELLED,
            DesktopRunPhase.FAILED,
        }


class DesktopBusyError(RuntimeError):
    """Raised when a second run is submitted to a busy controller."""
