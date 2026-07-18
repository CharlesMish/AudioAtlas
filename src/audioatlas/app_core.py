"""Platform-neutral behavior for the friend-facing desktop application."""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from audioatlas.run_contract import AnalysisProgress, AnalysisRunResult, CancellationToken

from audioatlas.errors import (
    AnalysisCancelled,
    AudioAtlasError,
    AudioLoadError,
    OutputBusyError,
    OutputOwnershipError,
    SourceChangedError,
)
from audioatlas.output import (
    OUTPUT_MARKER_FILENAME,
    output_transaction,
    read_output_manifest,
    staged_output_directory,
)

SUPPORTED_AUDIO_EXTENSIONS = frozenset(
    {".wav", ".wave", ".flac", ".ogg", ".aif", ".aiff", ".mp3"}
)
LARGE_FILE_DURATION_SECONDS = 30 * 60
LARGE_FILE_DECODED_BYTES = 512 * 1024 * 1024
_MAX_REPORT_COMPONENT_BYTES = 240


class AppInputError(ValueError):
    """An input that the desktop app cannot submit for analysis."""


@dataclass(frozen=True)
class AppInputInfo:
    """Cheap audio metadata used before committing to a desktop run."""

    source: Path
    duration_seconds: float
    samplerate: int
    channels: int
    frames: int
    estimated_decoded_bytes: int

    @property
    def needs_large_file_confirmation(self) -> bool:
        return (
            self.duration_seconds > LARGE_FILE_DURATION_SECONDS
            or self.estimated_decoded_bytes > LARGE_FILE_DECODED_BYTES
        )


AppPreparationStage = Literal["inspecting", "confirming", "initializing"]


@dataclass(frozen=True)
class AppPreparationProgress:
    """A lightweight desktop update emitted before the analysis stack loads."""

    stage: AppPreparationStage
    message: str


class LargeFileDecision:
    """One-shot bridge between a worker and a platform confirmation dialog."""

    def __init__(self) -> None:
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._accepted: bool | None = None

    def resolve(self, accepted: bool) -> bool:
        """Record the first answer and wake the waiting worker."""

        with self._lock:
            if self._accepted is not None:
                return False
            self._accepted = accepted
            self._event.set()
            return True

    def wait(self, cancellation_token: CancellationToken) -> bool:
        """Wait cooperatively so Cancel and Quit cannot strand the worker."""

        while not self._event.wait(0.05):
            cancellation_token.raise_if_cancelled()
        cancellation_token.raise_if_cancelled()
        with self._lock:
            return self._accepted is True


def default_report_directory(input_path: str | Path) -> Path:
    """Return the deterministic friend-visible report folder for an audio file."""

    source = Path(input_path).expanduser()
    return source.parent / _report_component(source.stem)


def safe_report_directory(
    input_path: str | Path,
    *,
    output_parent: str | Path | None = None,
) -> Path:
    """Choose a reusable owned report folder without adopting user data."""

    source = Path(input_path).expanduser()
    parent = source.parent if output_parent is None else Path(output_parent).expanduser()
    labels = [source.stem]
    if source.name != source.stem:
        labels.append(source.name)
    for label in labels:
        candidate = parent / _report_component(label)
        if _candidate_matches_source(candidate, source.name):
            return candidate
    for number in range(2, 10_000):
        candidate = parent / _report_component(f"{source.name} ({number})")
        if _candidate_matches_source(candidate, source.name):
            return candidate
    raise AppInputError("AudioAtlas could not choose a safe report-folder name.")


def validate_app_input(input_path: str | Path) -> Path:
    """Validate the narrow one-track desktop input contract."""

    source = Path(input_path).expanduser()
    if not source.is_file():
        raise AppInputError("Choose one audio file to analyze.")
    if source.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        supported = ", ".join(sorted(extension.removeprefix(".").upper() for extension in SUPPORTED_AUDIO_EXTENSIONS))
        raise AppInputError(f"That file type is not supported. Choose {supported} audio.")
    return source


def inspect_app_input(input_path: str | Path) -> AppInputInfo:
    """Inspect duration and decoded-memory size without loading audio samples."""

    import soundfile as sf

    source = validate_app_input(input_path)
    try:
        info = sf.info(str(source))
    except (OSError, sf.SoundFileError) as exc:
        raise AudioLoadError(source, f"audio metadata could not be decoded ({exc})") from exc
    if info.frames <= 0 or info.samplerate <= 0 or info.channels <= 0:
        raise AudioLoadError(source, "the file contains no decodable audio frames")
    return AppInputInfo(
        source=source,
        duration_seconds=float(info.frames / info.samplerate),
        samplerate=int(info.samplerate),
        channels=int(info.channels),
        frames=int(info.frames),
        estimated_decoded_bytes=int(info.frames * info.channels * 4),
    )


def prepare_and_analyze_for_app(
    input_path: str | Path,
    *,
    output_parent: str | Path | None = None,
    input_info: AppInputInfo | None = None,
    large_file_confirmed: bool = False,
    preparation_callback: Callable[[AppPreparationProgress], None] | None = None,
    inspection_callback: Callable[[AppInputInfo], None] | None = None,
    confirmation_callback: Callable[[AppInputInfo, LargeFileDecision], None] | None = None,
    progress_callback: Callable[[AnalysisProgress], None] | None = None,
    cancellation_token: CancellationToken,
) -> AnalysisRunResult:
    """Inspect, confirm, initialize, and analyze entirely on a managed worker."""

    source = Path(input_path).expanduser()
    if input_info is None:
        _emit_preparation(
            preparation_callback,
            "inspecting",
            f"Inspecting {source.name}…",
        )
        input_info = inspect_app_input(source)
    if inspection_callback is not None:
        inspection_callback(input_info)
    cancellation_token.raise_if_cancelled()

    if input_info.needs_large_file_confirmation and not large_file_confirmed:
        if confirmation_callback is None:
            raise AppInputError("Confirm this unusually large analysis before continuing.")
        decision = LargeFileDecision()
        _emit_preparation(
            preparation_callback,
            "confirming",
            "Waiting for confirmation…",
        )
        confirmation_callback(input_info, decision)
        if not decision.wait(cancellation_token):
            raise AnalysisCancelled(
                "Analysis canceled before loading. The previous report was unchanged."
            )

    cancellation_token.raise_if_cancelled()
    _emit_preparation(
        preparation_callback,
        "initializing",
        "Starting the local analysis engine…",
    )
    return analyze_for_app(
        source,
        output_parent=output_parent,
        progress_callback=progress_callback,
        cancellation_token=cancellation_token,
    )


def analyze_for_app(
    input_path: str | Path,
    *,
    output_parent: str | Path | None = None,
    _preflighted_output_dir: str | Path | None = None,
    progress_callback: Callable[[AnalysisProgress], None] | None = None,
    cancellation_token: CancellationToken | None = None,
) -> AnalysisRunResult:
    """Run the desktop app's fixed, low-decision analysis configuration."""

    from audioatlas.graphs.selection import GraphSelection

    source = validate_app_input(input_path)
    out_dir = (
        safe_report_directory(source, output_parent=output_parent)
        if _preflighted_output_dir is None
        else Path(_preflighted_output_dir).expanduser()
    )
    return _analyze_file(
        source,
        out_dir,
        theme_name="default",
        presentation_mode="studio",
        selection=GraphSelection(profile="standard"),
        include_local_paths=False,
        progress_callback=progress_callback,
        cancellation_token=cancellation_token,
    )


def preflight_app_output(
    input_path: str | Path,
    *,
    output_parent: str | Path | None = None,
) -> Path:
    """Prove a desktop report destination is owned, unlocked, and writable.

    This lightweight check happens before scientific initialization. The real
    analysis reacquires the same transaction, so a later race still fails safe
    without repeating decoding or measurements.
    """

    source = validate_app_input(input_path)
    out_dir = safe_report_directory(source, output_parent=output_parent)
    with output_transaction(out_dir), staged_output_directory(out_dir):
        pass
    return out_dir


def _analyze_file(*args: object, **kwargs: object) -> AnalysisRunResult:
    """Import the scientific stack only after the app has displayed its UI."""

    from audioatlas.pipeline import analyze_file

    return analyze_file(*args, **kwargs)


def _emit_preparation(
    callback: Callable[[AppPreparationProgress], None] | None,
    stage: AppPreparationStage,
    message: str,
) -> None:
    if callback is not None:
        callback(AppPreparationProgress(stage=stage, message=message))


def friendly_error_message(error: BaseException) -> str:
    """Turn expected local failures into concise, actionable UI text."""

    if isinstance(error, AppInputError):
        return str(error)
    if isinstance(error, AnalysisCancelled):
        return "Analysis canceled. The previous report was unchanged."
    if isinstance(error, OutputBusyError):
        return "Another AudioAtlas run is updating this report. Wait for it to finish."
    if isinstance(error, OutputOwnershipError):
        return "AudioAtlas would not overwrite that folder. Choose another report location."
    if isinstance(error, SourceChangedError):
        return str(error)
    if isinstance(error, AudioLoadError):
        return str(error)
    if isinstance(error, PermissionError):
        return "AudioAtlas could not write beside this file. Choose another report location."
    if isinstance(error, OSError):
        return "The filesystem refused the report update. The previous report was unchanged."
    if isinstance(error, AudioAtlasError):
        return str(error)
    return "AudioAtlas could not create this report. The previous report was left unchanged."


def _candidate_matches_source(candidate: Path, source_filename: str) -> bool:
    if candidate.is_symlink():
        return False
    if not candidate.exists():
        return True
    if not candidate.is_dir():
        return False
    try:
        entries = list(candidate.iterdir())
    except OSError:
        return False
    if not entries:
        return True
    manifest = read_output_manifest(candidate / OUTPUT_MARKER_FILENAME)
    if manifest is None or manifest.get("kind") != "single-track-report":
        return False
    summary_path = candidate / "summary.json"
    if summary_path.is_symlink() or not summary_path.is_file():
        return False
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    metadata = summary.get("metadata") if isinstance(summary, dict) else None
    return isinstance(metadata, dict) and metadata.get("filename") == source_filename


def _report_component(label: str) -> str:
    prefix = "AudioAtlas Report – "
    label = _portable_report_label(label)
    raw = f"{prefix}{label}"
    if len(raw.encode("utf-8")) <= _MAX_REPORT_COMPONENT_BYTES:
        return raw
    digest = hashlib.sha256(label.encode("utf-8")).hexdigest()[:8]
    suffix = f" – {digest}"
    budget = _MAX_REPORT_COMPONENT_BYTES - len((prefix + suffix).encode("utf-8"))
    kept: list[str] = []
    used = 0
    for character in label:
        encoded = character.encode("utf-8")
        if used + len(encoded) > budget:
            break
        kept.append(character)
        used += len(encoded)
    return f"{prefix}{''.join(kept).rstrip()}{suffix}"


def _portable_report_label(label: str) -> str:
    """Return a component valid on NTFS, APFS, and common archive formats."""

    invalid = '<>:"/\\|?*'
    translated = "".join("_" if character in invalid or ord(character) < 32 else character for character in label)
    # Win32 silently trims these suffixes, which otherwise breaks deterministic
    # collision checks. The prefix means reserved device basenames are harmless.
    return translated.rstrip(" .") or "track"
