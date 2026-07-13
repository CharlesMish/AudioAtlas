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

from audioatlas.errors import AudioLoadError
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
    path_kind: str = "basename"
    local_paths_included: bool = False

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
    include_local_paths: bool = False,
) -> AudioData:
    """Load audio without auto-normalizing level.

    Args:
        path: WAV/FLAC/OGG/etc. path supported by libsndfile. MP3 support depends on
            the local decoder build and is not guaranteed on every platform.
        max_duration_seconds: Optional truncation for development or quick testing,
            applied after ``start_seconds``.
        start_seconds: Optional source offset where analysis should begin.
        end_seconds: Optional source end time. If omitted, analysis continues to
            the end of the file or until ``max_duration_seconds`` is reached.
        include_local_paths: Store the resolved machine-local path in metadata.
            Disabled by default so report JSON can be shared without disclosing
            usernames or local directory layouts.

    Returns:
        AudioData with internal shape (n_samples, n_channels).
    """

    p = Path(path).expanduser()
    if not p.exists():
        raise AudioLoadError(p, "file does not exist")
    if not p.is_file():
        raise AudioLoadError(p, "path is not a regular file")

    try:
        info = sf.info(str(p))
    except (OSError, sf.SoundFileError) as exc:
        raise AudioLoadError(p, f"audio metadata could not be decoded ({exc})") from exc
    source_duration = float(info.frames / info.samplerate) if info.samplerate else 0.0
    if info.frames <= 0 or info.samplerate <= 0:
        raise AudioLoadError(p, "the file contains no decodable audio frames")

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

    try:
        y, sr = sf.read(
            str(p),
            start=start_frame,
            frames=frames,
            dtype="float32",
            always_2d=True,
        )
    except (OSError, sf.SoundFileError) as exc:
        raise AudioLoadError(p, f"audio samples could not be decoded ({exc})") from exc
    y = ensure_2d_audio(y)
    if y.shape[0] == 0:
        raise AudioLoadError(p, "the selected range contains no decodable audio frames")
    metadata_path = str(p.resolve()) if include_local_paths else p.name
    metadata = AudioMetadata(
        path=metadata_path,
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
        path_kind="absolute" if include_local_paths else "basename",
        local_paths_included=include_local_paths,
    )
    return AudioData(y=y, sr=int(sr), metadata=metadata)