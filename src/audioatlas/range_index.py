"""Chronological navigation over existing evidence ranges; no new detector."""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from typing import Any

import numpy as np

from audioatlas.analysis.bundle import AnalysisBundle
from audioatlas.references import REFERENCES
from audioatlas.time_support import timeline_support


@dataclass(frozen=True)
class RangeSource:
    key: str
    family: str
    label: str
    graph: str
    reference: str
    support: str


SOURCES = (
    RangeSource(
        "peak_timeline.near_clipping_time_ranges",
        "peaks",
        "Near-clipping samples",
        "peak_timeline",
        "sample_peak",
        "Start-labeled sample-peak frames; final frame truncated.",
    ),
    RangeSource(
        "spectral_shape.centroid_elevated_time_ranges",
        "spectral_shape",
        "Centroid elevated",
        "spectral_shape",
        "centroid",
        "Centered spectral frames.",
    ),
    RangeSource(
        "spectral_shape.centroid_reduced_time_ranges",
        "spectral_shape",
        "Centroid reduced",
        "spectral_shape",
        "centroid",
        "Centered spectral frames.",
    ),
    RangeSource(
        "spectral_shape.centroid_large_shift_time_ranges",
        "spectral_shape",
        "Centroid shift",
        "spectral_shape",
        "centroid",
        "Adjacent centered spectral frames, including the previous frame.",
    ),
    RangeSource(
        "stereo_correlation.correlation_below_0_time_ranges",
        "stereo",
        "Correlation below 0",
        "stereo_correlation",
        "stereo",
        "Start-labeled correlation frames; right-zero padding.",
    ),
    RangeSource(
        "stereo_correlation.correlation_below_0_3_time_ranges",
        "stereo",
        "Correlation below 0.3",
        "stereo_correlation",
        "stereo",
        "Start-labeled correlation frames; right-zero padding.",
    ),
    RangeSource(
        "mid_side_energy.side_to_mid_ratio_above_minus_6_time_ranges",
        "mid_side",
        "Side/mid above −6 dB",
        "mid_side_energy",
        "mid_side",
        "Start-labeled mid/side frames; right-zero padding.",
    ),
    RangeSource(
        "onset_density.high_onset_density_time_ranges",
        "onset",
        "Onset activity elevated",
        "onset_density",
        "onset",
        "Shifted mel-flux frames plus smoothing; not an instantaneous event.",
    ),
)


@dataclass(frozen=True)
class RangeOrigin:
    path: str
    source: RangeSource
    original: dict[str, Any]
    # Envelope of contributing integration footprints, not a new evidence range.
    footprint_seconds: tuple[float, float] | None = None
    context: str = ""


@dataclass(frozen=True)
class RangeRow:
    start: float
    end: float
    origins: tuple[RangeOrigin, ...]
    overlaps: int


@dataclass(frozen=True)
class RangeIndex:
    rows: tuple[RangeRow, ...]
    exclusions: tuple[tuple[str, str], ...]
    original_count: int


def index_enabled(summary: dict, override: bool | None = None) -> bool:
    """Detailed first; an explicit writer override is for presentation review."""
    if override is not None:
        return override
    graphs = summary.get("graphs")
    execution = summary.get("analysis_execution")
    return (
        isinstance(graphs, dict)
        and graphs.get("profile") == "full"
        and (
            execution is None
            or isinstance(execution, dict)
            and execution.get("mode", "full") == "full"
        )
    )


def build_range_index(
    summary: dict, findings: dict | None = None, bundle: AnalysisBundle | None = None
) -> RangeIndex:
    """Extract allowlisted original ranges without mutating or recomputing them."""
    groups: dict[tuple[float, float], list[RangeOrigin]] = {}
    excluded = []
    cache = bundle.computed_results if bundle is not None else {}
    supports = {}

    def add(source, values, prefix):
        if not isinstance(values, list):
            return
        for i, value in enumerate(values):
            path = f"{prefix}[{i}]"
            if not isinstance(value, dict):
                excluded.append((path, "malformed range"))
                continue
            start, end = value.get("start"), value.get("end")
            if (
                any(
                    isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                    for v in (start, end)
                )
                or start < 0
                or end <= start
            ):
                excluded.append((path, "nonfinite, negative, reversed, or zero-duration range"))
                continue
            footprint = None
            context = "Legacy label interval; detailed frame support unavailable in this rendering."
            if source.family in cache:
                result = cache[source.family]
                if source.family not in supports:
                    supports[source.family] = timeline_support(
                        source.family,
                        result,
                        bundle.config,
                        sample_rate=bundle.audio.sr,
                        samples=len(bundle.audio.y),
                    )
                support = supports[source.family]
                times = result.times_seconds
                first = int(np.searchsorted(times, start - 1e-9))
                last = int(np.searchsorted(times, end - 1e-9))
                if "large_shift" in source.key:
                    first = max(0, first - 1)
                if last > first:
                    footprint = (
                        float(support.source_start[first] / support.sample_rate),
                        float(support.source_stop[last - 1] / support.sample_rate),
                    )
                frame = (
                    f"{support.frame_samples / support.sample_rate:.3f} s frames"
                    if support.frame_samples
                    else "lagged frames with moving-window smoothing"
                )
                context = f"{frame}; {support.anchor.replace('_', ' ')}. {support.note}"
                if support.dependency != "local":
                    context += " Wider dependency: " + support.dependency.replace("_", " ") + "."
            groups.setdefault((float(start), float(end)), []).append(
                RangeOrigin(path, source, dict(value), footprint, context)
            )

    for source in SOURCES:
        block, key = source.key.split(".")
        value = summary.get(block)
        if isinstance(value, dict):
            add(source, value.get(key), source.key)
    canonical = summary.get("band_power_timeline")
    band_key = "band_power_timeline" if isinstance(canonical, dict) else "band_energy_timeline"
    block = summary.get(band_key, {})
    bands = block.get("bands", {}) if isinstance(block, dict) else {}
    for name, band in sorted(bands.items()) if isinstance(bands, dict) else []:
        if not isinstance(band, dict):
            continue
        for kind in ("elevated", "reduced"):
            key = f"{band_key}.bands.{name}.{kind}_time_ranges"
            source = RangeSource(
                key,
                "band_power",
                f"{name.replace('_', ' ').title()} band {kind}",
                "band_energy_timeline",
                "band_power",
                "Centered spectral frames; whole-view relative reference.",
            )
            add(source, band.get(kind + "_time_ranges"), key)
    if isinstance(findings, dict):
        name = next(
            (
                k
                for k in ("all_findings", "findings_shown", "findings")
                if isinstance(findings.get(k), list)
            ),
            None,
        )
        for i, finding in enumerate(findings.get(name, []) if name else []):
            if not isinstance(finding, dict):
                continue
            key = f"findings.{name}[{i}]"
            graphs = finding.get("associated_graphs", [])
            graph = (
                next((g for g in graphs if isinstance(g, str)), "")
                if isinstance(graphs, list)
                else ""
            )
            title = str(finding.get("title", "Existing finding"))
            source = RangeSource(
                key + ".time_ranges",
                "finding",
                "Finding: " + title,
                graph,
                "",
                "Original finding labels; constituent measurements may have different support.",
            )
            add(source, finding.get("time_ranges"), source.key)
            items = finding.get("evidence_items", [])
            for j, item in enumerate(items if isinstance(items, list) else []):
                if not isinstance(item, dict):
                    continue
                path = f"{key}.evidence_items[{j}].time_ranges"
                source = RangeSource(
                    path,
                    "finding",
                    "Finding evidence: " + str(item.get("label", title)),
                    graph,
                    "",
                    "Original finding evidence labels; see the associated measurement for support.",
                )
                add(source, item.get("time_ranges"), path)
    keys = sorted(groups)
    starts = sorted(s for s, _ in keys)
    ends = sorted(e for _, e in keys)
    rows = tuple(
        RangeRow(
            s,
            e,
            tuple(sorted(groups[s, e], key=lambda o: o.path)),
            bisect_left(starts, e) - bisect_right(ends, s) - 1,
        )
        for s, e in keys
    )
    return RangeIndex(rows, tuple(excluded), sum(len(r.origins) for r in rows))


def reference_text(source: RangeSource) -> str:
    if source.reference not in REFERENCES:
        return "Existing finding evidence; no new interpretation or severity is assigned."
    r = REFERENCES[source.reference]
    return f"{r.channel_basis.replace('_', ' ')}; {r.unit}; {r.normalization}. {r.does_not_mean}"
