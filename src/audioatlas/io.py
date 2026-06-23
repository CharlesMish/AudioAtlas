"""Audio loading and metadata.

Internal convention throughout AudioAtlas:
    y.shape == (n_samples, n_channels)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import soundfile as sf
from numpy.typing import NDArray

from audioatlas.utils import ensure_2d_audio


@dataclass(frozen=True)
class AudioMetadata:
    """Basic file metadata from libsndfile/soundfile."""

    path: str
    filename: str
    samplerate: int
    channels: int
    frames: int
    duration_seconds: float
    format: str
    subtype: str
    endian: str | None
    source_start_seconds: float | None = None
    source_end_seconds: float | None = None
    source_duration_seconds: float | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AudioData:
    """Loaded audio plus metadata.

    Attributes:
        y: float32 audio with shape (n_samples, n_channels). Levels are preserved;
           no normalization is applied by this loader.
        sr: sample rate in Hz.
        metadata: file metadata.
    """

    y: NDArray[np.float32]
    sr: int
    metadata: AudioMetadata


def load_audio(
    path: str | Path,
    *,
    max_duration_seconds: float | None = None,
    start_seconds: float | None = None,
    end_seconds: float | None = None,
) -> AudioData:
    """Load audio without auto-normalizing level.

    Args:
        path: WAV/FLAC/OGG/etc. path supported by libsndfile. MP3 support depends on
            local libsndfile/ffmpeg availability and is intentionally not guaranteed
            in the v0.1 framework.
        max_duration_seconds: Optional truncation for development or quick testing,
            applied after ``start_seconds``.
        start_seconds: Optional source offset where analysis should begin.
        end_seconds: Optional source end time. If omitted, analysis continues to
            the end of the file or until ``max_duration_seconds`` is reached.

    Returns:
        AudioData with internal shape (n_samples, n_channels).
    """

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)

    info = sf.info(str(p))
    source_duration = float(info.frames / info.samplerate) if info.samplerate else 0.0

    if start_seconds is not None and start_seconds < 0:
        raise ValueError("start_seconds must be non-negative")
    if end_seconds is not None and end_seconds <= 0:
        raise ValueError("end_seconds must be positive")
    if max_duration_seconds is not None and max_duration_seconds <= 0:
        raise ValueError("max_duration_seconds must be positive")

    start_frame = 0
    if start_seconds is not None:
        start_frame = int(round(start_seconds * info.samplerate))
        if start_frame >= info.frames:
            raise ValueError(
                f"start_seconds ({start_seconds:g}) is beyond the file duration "
                f"({source_duration:.3f} seconds)"
            )

    stop_frame = info.frames
    if end_seconds is not None:
        end_frame = int(round(end_seconds * info.samplerate))
        if end_frame <= start_frame:
            raise ValueError("end_seconds must be greater than start_seconds")
        stop_frame = min(stop_frame, end_frame)
    if max_duration_seconds is not None:
        max_end_frame = start_frame + int(round(max_duration_seconds * info.samplerate))
        stop_frame = min(stop_frame, max_end_frame)

    frames = max(0, stop_frame - start_frame)
    if frames <= 0:
        raise ValueError("Selected audio section is empty")

    y, sr = sf.read(
        str(p),
        start=start_frame,
        frames=frames,
        dtype="float32",
        always_2d=True,
    )
    y = ensure_2d_audio(y)
    metadata = AudioMetadata(
        path=str(p),
        filename=p.name,
        samplerate=int(sr),
        channels=int(y.shape[1]),
        frames=int(y.shape[0]),
        duration_seconds=float(y.shape[0] / sr),
        format=info.format,
        subtype=info.subtype,
        endian=getattr(info, "endian", None),
        source_start_seconds=float(start_frame / sr),
        source_end_seconds=float((start_frame + y.shape[0]) / sr),
        source_duration_seconds=source_duration,
    )
    return AudioData(y=y, sr=int(sr), metadata=metadata)