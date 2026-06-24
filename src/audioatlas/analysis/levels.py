"""Level, loudness, clipping, and RMS timeline analysis."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import librosa
import numpy as np
from numpy.typing import NDArray
from scipy import signal

from audioatlas.config import AnalysisConfig
from audioatlas.utils import ensure_2d_audio, linear_to_dbfs, mask_to_time_ranges, to_mono

try:  # optional at import time; pyproject installs it for normal use
    import pyloudnorm as pyln
except Exception:  # pragma: no cover - depends on local environment
    pyln = None  # type: ignore[assignment]


@dataclass(frozen=True)
class ScalarLevelsResult:
    """Global level and loudness metrics.

    All dBFS-style fields are clamped to ``config.db_floor`` so silent or
    near-silent input does not produce -240 dB outliers next to envelope
    plots that clamp at -100 dB.

    Notes:
        - ``sample_peak_dbfs`` is based on decoded samples.
        - ``true_peak_dbtp`` is an approximation using polyphase oversampling.
          When ``true_peak_oversample`` is 1, it falls back to sample peak.
          It returns ``None`` only when the configured true-peak path cannot
          produce a value, such as audio too short for the upsampler.
        - ``integrated_lufs`` is ``None`` if pyloudnorm is unavailable or the
          file is too short (BS.1770 requires >= ~400 ms of audio).
        - ``plr_db`` is true_peak - integrated_lufs when both exist.
        - Each global scalar that has a meaningful per-channel breakdown has
          a matching ``*_per_channel`` field: ``peak_dbfs_per_channel``,
          ``rms_dbfs_per_channel``, ``true_peak_dbtp_per_channel`` (and its
          linear counterpart), and ``dc_offset_per_channel``. The per-channel
          arrays are always in input channel order. Per-channel true-peak is
          ``None`` exactly when global true-peak is ``None``.

    LRA (Loudness Range) is intentionally not exposed in v0.1. See
    ``docs/AGENT_TASKS.md`` for the planned task and constraints.
    """

    duration_seconds: float
    sample_rate: int
    channels: int
    sample_peak_linear: float
    sample_peak_dbfs: float
    true_peak_linear: float | None
    true_peak_dbtp: float | None
    rms_linear: float
    rms_dbfs: float
    crest_factor_db: float | None
    integrated_lufs: float | None
    plr_db: float | None
    clipped_samples: int
    clipped_percent: float
    near_clipping_samples: int
    near_clipping_percent: float
    dc_offset_per_channel: list[float]
    peak_dbfs_per_channel: list[float]
    rms_dbfs_per_channel: list[float]
    true_peak_linear_per_channel: list[float] | None
    true_peak_dbtp_per_channel: list[float] | None
    warnings: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class RmsEnvelopeResult:
    """RMS envelope over time."""

    times_seconds: NDArray[np.float64]
    rms_linear: NDArray[np.float64]
    rms_dbfs: NDArray[np.float64]
    frame_length: int
    hop_length: int

    def to_summary_dict(self) -> dict[str, object]:
        return {
            "frame_length": self.frame_length,
            "hop_length": self.hop_length,
            "frames": int(len(self.times_seconds)),
            "rms_dbfs_min": float(np.min(self.rms_dbfs)) if len(self.rms_dbfs) else None,
            "rms_dbfs_max": float(np.max(self.rms_dbfs)) if len(self.rms_dbfs) else None,
            "rms_dbfs_mean": float(np.mean(self.rms_dbfs)) if len(self.rms_dbfs) else None,
        }


@dataclass(frozen=True)
class CrestFactorTimelineResult:
    """Per-frame crest factor: sample peak to RMS ratio in dB."""

    times_seconds: NDArray[np.float64]
    crest_factor_db: NDArray[np.float64]
    frame_length: int
    hop_length: int
    warnings: list[str]

    def to_summary_dict(self) -> dict[str, object]:
        finite = self.crest_factor_db[np.isfinite(self.crest_factor_db)]
        if len(finite) == 0:
            return {
                "frame_length": self.frame_length,
                "hop_length": self.hop_length,
                "frames": int(len(self.times_seconds)),
                "crest_factor_db_min": None,
                "crest_factor_db_median": None,
                "crest_factor_db_max": None,
                "warnings": self.warnings,
            }
        return {
            "frame_length": self.frame_length,
            "hop_length": self.hop_length,
            "frames": int(len(self.times_seconds)),
            "crest_factor_db_min": float(np.min(finite)),
            "crest_factor_db_median": float(np.median(finite)),
            "crest_factor_db_max": float(np.max(finite)),
            "warnings": self.warnings,
        }


@dataclass(frozen=True)
class PeakTimelineResult:
    """Frame-wise clipping and near-clipping counts."""

    times_seconds: NDArray[np.float64]
    clipped_counts: NDArray[np.int64]
    near_clipping_counts: NDArray[np.int64]
    frame_length: int
    hop_length: int
    clipping_threshold: float
    near_clipping_threshold: float
    near_clipping_time_ranges: list[dict[str, float]]

    def to_summary_dict(self) -> dict[str, object]:
        return {
            "frame_length": self.frame_length,
            "hop_length": self.hop_length,
            "frames": int(len(self.times_seconds)),
            "clipping_threshold": self.clipping_threshold,
            "near_clipping_threshold": self.near_clipping_threshold,
            "times_seconds": [float(v) for v in self.times_seconds],
            "clipped_counts": [int(v) for v in self.clipped_counts],
            "near_clipping_counts": [int(v) for v in self.near_clipping_counts],
            "clipped_samples_in_frames": int(np.sum(self.clipped_counts)),
            "near_clipping_samples_in_frames": int(np.sum(self.near_clipping_counts)),
            "frames_with_near_clipping": int(np.count_nonzero(self.near_clipping_counts)),
            "near_clipping_time_ranges": self.near_clipping_time_ranges,
        }


def compute_scalar_levels(
    y: NDArray[np.floating], sr: int, config: AnalysisConfig | None = None
) -> ScalarLevelsResult:
    """Compute global level/loudness metrics.

    Args:
        y: Audio array with shape (n_samples, n_channels), float, preserving
            original level.
        sr: Sample rate.
        config: Analysis settings.

    Returns:
        ScalarLevelsResult with global and per-channel metrics. All dBFS
        fields are clamped to ``config.db_floor``.
    """

    cfg = config or AnalysisConfig()
    cfg.validate()
    audio = ensure_2d_audio(y)
    if sr <= 0:
        raise ValueError("sr must be positive")
    if audio.shape[0] == 0:
        raise ValueError("audio has zero samples")

    warnings: list[str] = []
    floor = cfg.db_floor
    abs_audio = np.abs(audio.astype(np.float64, copy=False))

    sample_peak_linear = float(np.max(abs_audio))
    sample_peak_dbfs = float(linear_to_dbfs(sample_peak_linear, floor_db=floor))

    per_channel_peak = np.max(abs_audio, axis=0)
    peak_dbfs_per_channel = [
        float(v) for v in linear_to_dbfs(per_channel_peak, floor_db=floor)
    ]

    rms_linear = float(np.sqrt(np.mean(np.square(audio.astype(np.float64, copy=False)))))
    rms_dbfs = float(linear_to_dbfs(rms_linear, floor_db=floor))
    per_channel_rms = np.sqrt(
        np.mean(np.square(audio.astype(np.float64, copy=False)), axis=0)
    )
    rms_dbfs_per_channel = [
        float(v) for v in linear_to_dbfs(per_channel_rms, floor_db=floor)
    ]

    crest_factor_db = None
    if rms_linear > 0 and sample_peak_linear > 0:
        crest_factor_db = float(20.0 * np.log10(sample_peak_linear / rms_linear))

    clipped_mask = abs_audio >= cfg.clipping_threshold
    near_clip_mask = abs_audio >= cfg.near_clipping_threshold
    clipped_samples = int(np.count_nonzero(clipped_mask))
    near_clipping_samples = int(np.count_nonzero(near_clip_mask))
    total_values = int(audio.size)

    true_peak_linear: float | None = None
    true_peak_dbtp: float | None = None
    true_peak_linear_per_channel: list[float] | None = None
    true_peak_dbtp_per_channel: list[float] | None = None
    if cfg.true_peak_oversample > 1 and audio.shape[0] > 8:
        upsampled = signal.resample_poly(audio, up=cfg.true_peak_oversample, down=1, axis=0)
        upsampled_abs = np.abs(upsampled)
        true_peak_linear = float(np.max(upsampled_abs))
        true_peak_dbtp = float(linear_to_dbfs(true_peak_linear, floor_db=floor))
        per_ch_tp_linear = np.max(upsampled_abs, axis=0)
        true_peak_linear_per_channel = [float(v) for v in per_ch_tp_linear]
        true_peak_dbtp_per_channel = [
            float(v) for v in linear_to_dbfs(per_ch_tp_linear, floor_db=floor)
        ]
    elif cfg.true_peak_oversample == 1:
        # No oversampling requested: true-peak collapses to sample peak.
        true_peak_linear = sample_peak_linear
        true_peak_dbtp = sample_peak_dbfs
        true_peak_linear_per_channel = [float(v) for v in per_channel_peak]
        true_peak_dbtp_per_channel = list(peak_dbfs_per_channel)

    integrated_lufs: float | None = None
    if pyln is None:
        warnings.append("pyloudnorm is not installed; integrated_lufs is None")
    elif audio.shape[0] < int(0.4 * sr):
        warnings.append(
            "audio is shorter than about 400 ms; integrated LUFS is unreliable per BS.1770"
        )
    else:
        try:
            meter = pyln.Meter(sr)
            data_for_meter = audio[:, 0] if audio.shape[1] == 1 else audio
            loudness = meter.integrated_loudness(data_for_meter)
            if np.isfinite(loudness):
                integrated_lufs = float(loudness)
        except Exception as exc:  # pragma: no cover - depends on pyloudnorm details
            warnings.append(f"integrated LUFS failed: {exc}")

    plr_db: float | None = None
    if true_peak_dbtp is not None and integrated_lufs is not None:
        plr_db = float(true_peak_dbtp - integrated_lufs)

    dc_offset = np.mean(audio.astype(np.float64, copy=False), axis=0)

    return ScalarLevelsResult(
        duration_seconds=float(audio.shape[0] / sr),
        sample_rate=int(sr),
        channels=int(audio.shape[1]),
        sample_peak_linear=sample_peak_linear,
        sample_peak_dbfs=sample_peak_dbfs,
        true_peak_linear=true_peak_linear,
        true_peak_dbtp=true_peak_dbtp,
        rms_linear=rms_linear,
        rms_dbfs=rms_dbfs,
        crest_factor_db=crest_factor_db,
        integrated_lufs=integrated_lufs,
        plr_db=plr_db,
        clipped_samples=clipped_samples,
        clipped_percent=float(100.0 * clipped_samples / total_values),
        near_clipping_samples=near_clipping_samples,
        near_clipping_percent=float(100.0 * near_clipping_samples / total_values),
        dc_offset_per_channel=[float(v) for v in dc_offset],
        peak_dbfs_per_channel=peak_dbfs_per_channel,
        rms_dbfs_per_channel=rms_dbfs_per_channel,
        true_peak_linear_per_channel=true_peak_linear_per_channel,
        true_peak_dbtp_per_channel=true_peak_dbtp_per_channel,
        warnings=warnings,
    )


def compute_crest_factor_timeline(
    y: NDArray[np.floating], sr: int, config: AnalysisConfig | None = None
) -> CrestFactorTimelineResult:
    """Compute per-frame crest factor from sample peak and RMS.

    Each frame uses all channels: peak is the maximum absolute sample in the
    window and RMS is computed across every sample in the window. Silent frames
    produce ``NaN`` in the timeline.
    """

    cfg = config or AnalysisConfig()
    cfg.validate()
    audio = ensure_2d_audio(y).astype(np.float64, copy=False)
    if sr <= 0:
        raise ValueError("sr must be positive")
    if audio.shape[0] == 0:
        raise ValueError("audio has zero samples")

    warnings: list[str] = []
    frame_length = cfg.rms_frame_length
    hop_length = cfg.hop_length
    pad = frame_length // 2
    padded = np.pad(audio, ((pad, pad), (0, 0)), mode="constant")
    n_frames = len(
        librosa.feature.rms(
            y=to_mono(audio),
            frame_length=frame_length,
            hop_length=hop_length,
            center=True,
        )[0]
    )
    crest_db = np.full(n_frames, np.nan, dtype=np.float64)
    for i in range(n_frames):
        start = i * hop_length
        end = start + frame_length
        frame = padded[start:end]
        peak = float(np.max(np.abs(frame)))
        rms = float(np.sqrt(np.mean(frame**2)))
        if rms > 0.0 and peak > 0.0:
            crest_db[i] = 20.0 * np.log10(peak / rms)

    if not np.any(np.isfinite(crest_db)):
        warnings.append("no measurable crest factor; timeline is empty or all NaN")

    times = librosa.frames_to_time(
        np.arange(n_frames), sr=sr, hop_length=hop_length
    ).astype(np.float64)
    return CrestFactorTimelineResult(
        times_seconds=times,
        crest_factor_db=crest_db,
        frame_length=frame_length,
        hop_length=hop_length,
        warnings=warnings,
    )


def compute_peak_timeline(
    y: NDArray[np.floating], sr: int, config: AnalysisConfig | None = None
) -> PeakTimelineResult:
    """Compute frame-wise clipping and near-clipping sample counts."""

    cfg = config or AnalysisConfig()
    cfg.validate()
    audio = ensure_2d_audio(y)
    if sr <= 0:
        raise ValueError("sr must be positive")
    if audio.shape[0] == 0:
        raise ValueError("audio has zero samples")

    abs_audio = np.abs(audio.astype(np.float64, copy=False))
    starts = np.arange(0, audio.shape[0], cfg.hop_length, dtype=np.int64)
    clipped_counts = np.zeros(len(starts), dtype=np.int64)
    near_counts = np.zeros(len(starts), dtype=np.int64)
    for i, start in enumerate(starts):
        end = min(start + cfg.n_fft, audio.shape[0])
        frame = abs_audio[start:end]
        clipped_counts[i] = np.count_nonzero(frame >= cfg.clipping_threshold)
        near_counts[i] = np.count_nonzero(frame >= cfg.near_clipping_threshold)

    times = (starts.astype(np.float64) / sr).astype(np.float64)
    time_ranges = mask_to_time_ranges(near_counts > 0, times)
    return PeakTimelineResult(
        times_seconds=times,
        clipped_counts=clipped_counts,
        near_clipping_counts=near_counts,
        frame_length=cfg.n_fft,
        hop_length=cfg.hop_length,
        clipping_threshold=cfg.clipping_threshold,
        near_clipping_threshold=cfg.near_clipping_threshold,
        near_clipping_time_ranges=time_ranges,
    )


def compute_rms_envelope(
    y: NDArray[np.floating], sr: int, config: AnalysisConfig | None = None
) -> RmsEnvelopeResult:
    """Compute a mono RMS timeline from the original-level audio.

    Args:
        y: Audio array with shape (n_samples, n_channels).
        sr: Sample rate.
        config: Analysis settings.

    Returns:
        RmsEnvelopeResult with times and RMS values. ``rms_dbfs`` is clamped
        to ``config.db_floor``.
    """

    cfg = config or AnalysisConfig()
    cfg.validate()
    mono = to_mono(y)
    rms = librosa.feature.rms(
        y=mono,
        frame_length=cfg.rms_frame_length,
        hop_length=cfg.hop_length,
        center=True,
    )[0].astype(np.float64)
    times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=cfg.hop_length)
    rms_db = np.asarray(linear_to_dbfs(rms, floor_db=cfg.db_floor), dtype=np.float64)
    return RmsEnvelopeResult(
        times_seconds=times.astype(np.float64),
        rms_linear=rms,
        rms_dbfs=rms_db,
        frame_length=cfg.rms_frame_length,
        hop_length=cfg.hop_length,
    )
