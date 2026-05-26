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


def load_audio(path: str | Path, *, max_duration_seconds: float | None = None) -> AudioData:
    """Load audio without auto-normalizing level.

    Args:
        path: WAV/FLAC/OGG/etc. path supported by libsndfile. MP3 support depends on
            local libsndfile/ffmpeg availability and is intentionally not guaranteed
            in the v0.1 framework.
        max_duration_seconds: Optional truncation for development or quick testing.

    Returns:
        AudioData with internal shape (n_samples, n_channels).
    """

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)

    info = sf.info(str(p))
    frames = -1
    if max_duration_seconds is not None:
        if max_duration_seconds <= 0:
            raise ValueError("max_duration_seconds must be positive")
        frames = int(round(max_duration_seconds * info.samplerate))

    y, sr = sf.read(str(p), frames=frames, dtype="float32", always_2d=True)
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
    )
    return AudioData(y=y, sr=int(sr), metadata=metadata)
