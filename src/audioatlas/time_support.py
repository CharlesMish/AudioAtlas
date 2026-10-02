"""Internal sample-exact integration footprints; never retime public results.

Half-open sample intervals are relative to the analyzed slice. A footprint is
not necessarily the complete dependency: filtering and global normalization
are declared separately. Bounds enclose windowed samples, including zero-weight
window endpoints; they do not imply uniform weighting or temporal resolution.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from audioatlas.config import AnalysisConfig


@dataclass(frozen=True)
class TimelineSupport:
    anchor: str
    sample_rate: int
    frame_samples: int | None
    hop_samples: float
    nominal_start: NDArray[np.int64]
    nominal_stop: NDArray[np.int64]
    source_start: NDArray[np.int64]
    source_stop: NDArray[np.int64]
    padding: str
    dependency: str
    note: str
    time_origin: str = "analyzed_slice_start"

    def intervals_seconds(self) -> NDArray[np.float64]:
        """Decoded-sample integration footprint, not filter/reference context."""
        return np.column_stack((self.source_start, self.source_stop)) / self.sample_rate

    def dependency_intervals_seconds(self) -> NDArray[np.float64]:
        """Local/causal raw support; global references cannot be bounded here."""
        if self.dependency == "analysis_wide_reference":
            raise ValueError("global reference dependency: use the entire analyzed slice")
        intervals = self.intervals_seconds()
        if self.dependency == "causal_filter_prefix":
            intervals[:, 0] = 0
        return intervals


def timeline_support(
    family: str,
    result: object,
    config: AnalysisConfig,
    *,
    sample_rate: int,
    samples: int,
) -> TimelineSupport:
    """Describe an existing result without computing or changing measurements.

    CQT support is frequency-dependent and is deliberately not approximated by
    an FFT frame. Onset support includes lag/centering and moving-average context.
    LUFS bounds follow installed pyloudnorm's integer endpoint arithmetic,
    including a possibly truncated final rounded block and causal filter history.
    """
    if sample_rate <= 0 or samples < 0:
        raise ValueError("positive sample rate and nonnegative sample count required")
    config.validate()
    count = len(result.times_seconds)
    index = np.arange(count, dtype=np.int64)
    hop = config.hop_length
    n = config.n_fft
    dependency = "local"
    note = "Footprint encloses contributing samples; weighting is family-specific."
    if family in {"rms", "crest", "spectral_shape", "band_power", "spectrogram"}:
        n = result.frame_length if family in {"rms", "crest"} else result.n_fft
        hop = result.hop_length
        start = index * hop - n // 2
        stop = start + n
        anchor, padding = "center_sample", "zero_both_edges"
        if family in {"band_power", "spectrogram"}:
            dependency = "analysis_wide_reference"
            note += " Relative values also depend on the maximum over the entire analyzed view."
    elif family in {"peaks", "stereo", "mid_side", "lr_balance"}:
        n, hop = result.frame_length, result.hop_length
        start = index * hop
        stop = start + n
        anchor = "frame_center" if family == "lr_balance" else "start"
        padding = {"peaks": "truncate_right", "lr_balance": "none_complete_only"}.get(
            family, "zero_right"
        )
    elif family == "short_term":
        window = float(result.window_seconds)
        overlap = (
            1 - config.short_term_lufs_hop_seconds / window
            if (0 < config.short_term_lufs_hop_seconds < window)
            else 0.75
        )
        step = 1 - max(0.0, min(0.99, overlap))
        # Match multiplication order and int truncation in pyloudnorm.
        start = np.array([int(window * (int(j) * step) * sample_rate) for j in index])
        stop = np.array([int(window * (int(j) * step + 1) * sample_rate) for j in index])
        n, hop = int(window * sample_rate), window * step * sample_rate
        anchor, padding = "window_end_clipped_to_duration", "truncate_right_fixed_denominator"
        dependency = "causal_filter_prefix"
        note = "Integration of K-weighted samples; causal IIR state includes earlier slice samples."
    elif family == "onset":
        hop = result.hop_length
        width = result.smoothing_window_frames
        shift = n // (2 * hop)
        # np.convolve(raw, ones(width), 'same'): asymmetric by one for even widths.
        first = np.maximum(index - width // 2, 1 + shift)
        last = np.minimum(index + (width - 1) // 2, count - 1)
        start = (first - shift - 1) * hop - n // 2
        stop = (last - shift) * hop - n // 2 + n
        empty = first > last
        start[empty] = 0
        stop[empty] = 0
        anchor, padding = "shifted_flux_label", "zero_stft_flux_and_smoothing_edges"
        dependency = "analysis_wide_reference"
        note = "Lag-1 mel flux plus moving mean; global log-mel top-dB clipping also depends on the view."
        n = None
    else:
        raise ValueError(f"No scalar integration-support contract for {family!r}")
    start = np.asarray(start, dtype=np.int64)
    stop = np.asarray(stop, dtype=np.int64)
    return TimelineSupport(
        anchor,
        sample_rate,
        n,
        float(hop),
        start,
        stop,
        np.clip(start, 0, samples),
        np.clip(stop, 0, samples),
        padding,
        dependency,
        note,
    )
