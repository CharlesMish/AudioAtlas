"""Domain exceptions exposed by AudioAtlas user workflows."""

from __future__ import annotations

import re
from contextlib import suppress
from pathlib import Path, PurePosixPath, PureWindowsPath


class AudioAtlasError(Exception):
    """Base class for expected AudioAtlas user-facing failures."""


class AudioLoadError(AudioAtlasError):
    """Raised when an input cannot be inspected or decoded as audio."""

    def __init__(self, path: str | Path, reason: str) -> None:
        self.path = Path(path)
        self.reason = _safe_reason(self.path, reason)
        super().__init__(f"Could not read audio file '{self.path.name}': {self.reason}")


class SourceChangedError(AudioAtlasError):
    """Raised when an input changes while AudioAtlas is decoding it."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        super().__init__(
            f"Audio file '{self.path.name}' changed while it was being read. "
            "Wait for it to finish copying or exporting, then try again."
        )


class AnalysisCancelled(AudioAtlasError):
    """Raised when a cooperative analysis cancellation is observed."""


class OutputBusyError(AudioAtlasError):
    """Raised when another process owns the destination transaction."""


class OutputOwnershipError(AudioAtlasError):
    """Raised when a destination cannot be proven safe to update."""


def _safe_reason(path: Path, value: str) -> str:
    """Collapse decoder text and remove machine-local path disclosure."""

    text = " ".join(str(value).split()).strip()
    candidates = {str(path), str(path.expanduser())}
    with suppress(OSError):
        candidates.add(str(path.expanduser().resolve()))
    # Longest first prevents replacing a relative suffix before the full path.
    for candidate in sorted((item for item in candidates if item), key=len, reverse=True):
        text = text.replace(candidate, path.name)
    # Some Windows decoders rewrite separators, drive casing, or path prefixes
    # before returning an error. Redact any quoted path whose final component is
    # the selected filename rather than relying only on byte-for-byte equality.
    for quote, value in re.findall(r"(['\"])(.*?)\1", text):
        windows_name = PureWindowsPath(value).name
        posix_name = PurePosixPath(value).name
        if path.name.casefold() in {windows_name.casefold(), posix_name.casefold()}:
            text = text.replace(f"{quote}{value}{quote}", f"{quote}{path.name}{quote}")
    return text or "the decoder did not provide a reason"


class RevisionDiffError(AudioAtlasError):
    """Raised when two reports cannot be compared under the requested guardrails."""


class ProjectError(AudioAtlasError):
    """Raised when a local song-project operation cannot complete safely."""
