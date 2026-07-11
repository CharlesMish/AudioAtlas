"""Domain exceptions exposed by AudioAtlas user workflows."""

from __future__ import annotations

from contextlib import suppress
from pathlib import Path


class AudioAtlasError(Exception):
    """Base class for expected AudioAtlas user-facing failures."""


class AudioLoadError(AudioAtlasError):
    """Raised when an input cannot be inspected or decoded as audio."""

    def __init__(self, path: str | Path, reason: str) -> None:
        self.path = Path(path)
        self.reason = _safe_reason(self.path, reason)
        super().__init__(f"Could not read audio file '{self.path.name}': {self.reason}")


def _safe_reason(path: Path, value: str) -> str:
    """Collapse decoder text and remove machine-local path disclosure."""

    text = " ".join(str(value).split()).strip()
    candidates = {str(path), str(path.expanduser())}
    with suppress(OSError):
        candidates.add(str(path.expanduser().resolve()))
    # Longest first prevents replacing a relative suffix before the full path.
    for candidate in sorted((item for item in candidates if item), key=len, reverse=True):
        text = text.replace(candidate, path.name)
    return text or "the decoder did not provide a reason"


class RevisionDiffError(AudioAtlasError):
    """Raised when two reports cannot be compared under the requested guardrails."""
