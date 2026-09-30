"""Internal support-aware lanes built only from already-computed measurements.

No resampling, interpolation, unit conversion, event detection, ranking, findings,
or implicit restoration of optional computations occurs here.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from audioatlas.analysis.bundle import AnalysisBundle
from audioatlas.references import REFERENCES, MeasurementReference
from audioatlas.time_support import TimelineSupport, timeline_support


@dataclass(frozen=True)
class EvidenceLane:
    key: str
    family: str
    label: str
    values: NDArray[np.float64]
    times_seconds: NDArray[np.float64]
    valid: NDArray[np.bool_]
    undefined_reasons: NDArray[np.str_]
    reference: MeasurementReference
    support: TimelineSupport
    source_measurement: str
    notes: tuple[str, ...]

    def overlapping_indices(self, start: float, end: float) -> NDArray[np.int64]:
        """Indices whose local integration footprint overlaps [start,end).

        Full dependency context is retained on support; this query does not
        turn integration-footprint overlap into evidence of a shared cause.
        """
        if not np.isfinite(start) or not np.isfinite(end) or end <= start:
            raise ValueError("finite increasing interval required")
        # Supports are monotonic. Sparse lookup avoids a frames-by-grid matrix.
        left = np.searchsorted(
            self.support.source_stop, start * self.support.sample_rate, side="right"
        )
        right = np.searchsorted(
            self.support.source_start, end * self.support.sample_rate, side="left"
        )
        indices = np.arange(left, right, dtype=np.int64)
        return indices[self.valid[indices]]


# key, label, result attribute, reference identity
_SCALARS = {
    "rms": ("rms", "Mono RMS", "rms_dbfs", "mono_rms"),
    "peaks": ("sample_peak", "Sample peak", "frame_peak_dbfs", "sample_peak"),
    "crest": ("crest", "Crest factor", "crest_factor_db", "crest"),
    "short_term": ("short_term_lufs", "Short-term LUFS", "lufs", "short_term"),
    "stereo": ("correlation", "Stereo correlation", "correlation", "stereo"),
    "mid_side": ("side_mid_ratio", "Side/mid ratio", "side_to_mid_ratio_db", "mid_side"),
    "lr_balance": ("lr_balance", "L/R RMS balance", "balance_db", "lr_balance"),
    "spectral_shape": ("centroid", "Spectral centroid", "spectral_centroid_hz", "centroid"),
    "onset": ("onset_activity", "Smoothed onset activity", "smoothed_onset_density", "onset"),
}


def evidence_lanes(bundle: AnalysisBundle) -> tuple[EvidenceLane, ...]:
    """Snapshot lanes for completed results. Omitted families stay omitted.

    Arrays are detached read-only copies so consumers cannot mutate measurements.
    Existing finite floor/convention values stay finite and are explicitly noted;
    undefined values retain masks/reasons and are never replaced with zero.
    """
    lanes = []
    for family, result in bundle.computed_results.items():
        if family not in _SCALARS and family != "band_power":
            continue
        support = timeline_support(
            family, result, bundle.config, sample_rate=bundle.audio.sr, samples=len(bundle.audio.y)
        )
        fields = (
            [
                (
                    f"band_power.{name}",
                    f"Relative band power: {name}",
                    result.band_mean_power_db_by_band[name],
                    "band_power",
                    f"band_mean_power_db_by_band.{name}",
                )
                for name in result.band_names
            ]
            if family == "band_power"
            else [
                (key, label, getattr(result, field), ref, field)
                for key, label, field, ref in [_SCALARS[family]]
            ]
        )
        for key, label, original, ref, field in fields:
            values = np.array(original, dtype=np.float64, copy=True)
            times = np.array(result.times_seconds, dtype=np.float64, copy=True)
            valid = np.isfinite(values)
            if hasattr(result, "valid_frames"):
                valid &= result.valid_frames
            reasons = np.where(valid, "defined", "measurement_undefined").astype("U48")
            if family == "lr_balance":
                reasons = result.frame_status.astype("U48", copy=True)
            elif family == "spectral_shape":
                reasons[~valid] = "mono_downmix_below_analysis_floor"
            elif family == "band_power":
                reasons[~valid] = "band_unavailable_or_below_analysis_floor"
            notes = list(getattr(result, "warnings", []))
            if family in {"rms", "peaks", "mid_side", "band_power"}:
                notes.append(
                    "Existing numerical/display floors are retained; floor values are censored."
                )
            if family == "lr_balance":
                notes.append(result.status)
            for array in (values, times, valid, reasons):
                array.flags.writeable = False
            lanes.append(
                EvidenceLane(
                    key,
                    family,
                    label,
                    values,
                    times,
                    valid,
                    reasons,
                    REFERENCES[ref],
                    support,
                    f"{family}.{field}",
                    tuple(notes),
                )
            )
    return tuple(lanes)


@dataclass(frozen=True)
class EvidenceCell:
    start_seconds: float
    end_seconds: float
    # References to original lane samples; no averaged or synthesized values.
    indices_by_lane: dict[str, NDArray[np.int64]]


def aligned_cells(
    lanes: tuple[EvidenceLane, ...],
    *,
    duration_seconds: float,
    step_seconds: float = 1.0,
) -> Iterator[EvidenceCell]:
    """Yield cells with sparse original-frame references; not a fused timeline."""
    if not np.isfinite(duration_seconds) or duration_seconds < 0:
        raise ValueError("duration must be finite and nonnegative")
    if not np.isfinite(step_seconds) or step_seconds <= 0:
        raise ValueError("step must be finite and positive")
    for i in range(int(np.ceil(duration_seconds / step_seconds))):
        start, end = i * step_seconds, min((i + 1) * step_seconds, duration_seconds)
        matches = {}
        for lane in lanes:
            indices = lane.overlapping_indices(start, end)
            if len(indices):
                matches[lane.key] = indices
        yield EvidenceCell(start, end, matches)
