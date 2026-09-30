"""Bucket overlap metadata over existing labels; never generates evidence ranges."""

from __future__ import annotations

import math
from dataclasses import dataclass

from audioatlas.range_index import RangeIndex

FAMILIES = (
    ("level", "Level / peak"),
    ("spectral_shape", "Spectral shape"),
    ("spectral_bands", "Spectral bands"),
    ("stereo", "Stereo"),
    ("activity", "Activity / onset"),
    ("findings", "Findings"),
)


def family_key(source) -> str:
    return {
        "peaks": "level",
        "spectral_shape": "spectral_shape",
        "band_power": "spectral_bands",
        "stereo": "stereo",
        "mid_side": "stereo",
        "onset": "activity",
        "finding": "findings",
    }[source.family]


def family_rows(index: RangeIndex, row_ids: tuple[int, ...], family: str) -> tuple[int, ...]:
    return tuple(
        i for i in row_ids if any(family_key(o.source) == family for o in index.rows[i].origins)
    )


@dataclass(frozen=True)
class NavigationBucket:
    start: int
    end: float
    active: tuple[int, ...]
    starting: tuple[int, ...]
    continuing: tuple[int, ...]


def active_buckets(index: RangeIndex, duration: float, step: int) -> tuple[NavigationBucket, ...]:
    """Positive label overlap only. IDs point to canonical rows, not clipped copies.

    Include buckets with no starting ranges, including empty buckets. Footprints
    are deliberately not consulted: label presence is not physical simultaneity.
    """
    if not math.isfinite(duration) or duration < 0 or not isinstance(step, int) or step <= 0:
        raise ValueError("finite nonnegative duration and positive integer step required")
    end = max(duration, max((r.end for r in index.rows), default=0))
    buckets = []
    for start in range(0, math.ceil(end), step):
        stop = min(start + step, end)
        active = tuple(i for i, r in enumerate(index.rows) if r.start < stop and r.end > start)
        starting = tuple(i for i in active if index.rows[i].start >= start)
        continuing = tuple(i for i in active if index.rows[i].start < start)
        buckets.append(NavigationBucket(start, stop, active, starting, continuing))
    return tuple(buckets)
