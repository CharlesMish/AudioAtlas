"""Tonal analysis (chroma).

Descriptive pitch-class energy only — AudioAtlas does not attempt key
detection. See ``docs/ALPHA_LIMITATIONS.md`` for the no-verdict boundary.
"""

from __future__ import annotations

import warnings as py_warnings
from dataclasses import dataclass

import librosa
import numpy as np
from numpy.typing import NDArray

from audioatlas.config import AnalysisConfig
from audioatlas.utils import EPS, to_mono

PITCH_CLASSES: tuple[str, ...] = (
    "C",
    "C#",
    "D",
    "D#",
    "E",
    "F",
    "F#",
    "G",
    "G#",
    "A",
    "A#",
    "B",
)

__all__ = ["ChromaCqtResult", "PITCH_CLASSES", "compute_chroma_cqt"]


@dataclass(frozen=True)
class ChromaCqtResult:
    """12-bin chromagram over time from a constant-Q transform."""

    chroma: NDArray[np.float64]
    times_seconds: NDArray[np.float64]
    pitch_classes: tuple[str, ...]
    sample_rate: int
    hop_length: int
    warnings: list[str]

    def to_summary_dict(self) -> dict[str, object]:
        if self.chroma.shape[1] == 0:
            return {
                "frames": 0,
                "hop_length": self.hop_length,
                "pitch_classes": list(self.pitch_classes),
                "mean_chroma": [0.0] * len(self.pitch_classes),
                "dominant_pitch_class": None,
                "warnings": self.warnings,
            }
        mean_chroma = self.chroma.mean(axis=1).astype(np.float64)
        dominant_idx = int(np.argmax(mean_chroma))
        dominant = self.pitch_classes[dominant_idx]
        if float(np.max(mean_chroma)) <= EPS:
            dominant = None
        return {
            "frames": int(self.chroma.shape[1]),
            "hop_length": self.hop_length,
            "pitch_classes": list(self.pitch_classes),
            "mean_chroma": [float(v) for v in mean_chroma],
            "dominant_pitch_class": dominant,
            "warnings": self.warnings,
        }


def compute_chroma_cqt(
    y: NDArray[np.floating], sr: int, config: AnalysisConfig | None = None
) -> ChromaCqtResult:
    """Compute a 12-bin chromagram over time using ``librosa.feature.chroma_cqt``.

    The result describes pitch-class energy within this track. It is not key
    detection and values are not calibrated across unrelated songs.
    """

    cfg = config or AnalysisConfig()
    cfg.validate()
    if sr <= 0:
        raise ValueError("sr must be positive")
    mono = to_mono(y).astype(np.float64)
    if len(mono) == 0:
        raise ValueError("audio has zero samples")

    with py_warnings.catch_warnings(record=True) as caught:
        py_warnings.simplefilter("always")
        chroma = librosa.feature.chroma_cqt(
            y=mono,
            sr=sr,
            hop_length=cfg.hop_length,
        ).astype(np.float64)

    warnings: list[str] = []
    for caught_warning in caught:
        message = str(caught_warning.message)
        if _is_expected_short_input_warning(message):
            note = (
                "short input reached an internal FFT window larger than one intermediate "
                "signal; chroma output was still produced with reduced short-file context"
            )
            if note not in warnings:
                warnings.append(note)
        elif _is_expected_empty_tuning_warning(message):
            # The zero-energy caveat below is the stable, user-facing version
            # of this library warning.
            continue
        else:
            # Preserve unexpected library warnings instead of hiding them globally.
            py_warnings.warn(
                caught_warning.message,
                caught_warning.category,
                stacklevel=2,
            )
    if float(np.max(chroma)) <= EPS:
        warnings.append("no measurable chroma energy; chromagram is reported as zero")

    times = librosa.frames_to_time(
        np.arange(chroma.shape[1]), sr=sr, hop_length=cfg.hop_length
    ).astype(np.float64)
    return ChromaCqtResult(
        chroma=chroma,
        times_seconds=times,
        pitch_classes=PITCH_CLASSES,
        sample_rate=int(sr),
        hop_length=cfg.hop_length,
        warnings=warnings,
    )


def _is_expected_short_input_warning(message: str) -> bool:
    return (
        message.startswith("n_fft=")
        and " is too large for input signal of length=" in message
    )


def _is_expected_empty_tuning_warning(message: str) -> bool:
    return message == "Trying to estimate tuning from empty frequency set."
