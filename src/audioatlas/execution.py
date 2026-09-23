"""Computation breadth, orthogonal to graph selection and measurement fidelity."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from audioatlas.graphs.registry import GraphSpec

ANALYSIS_MODES = ("full", "compact")

# Preserve the full pipeline's measurement order and canonical summary names.
SUMMARY_BLOCKS = {
    "levels": "levels",
    "rms": "rms_envelope",
    "crest": "crest_factor_timeline",
    "short_term": "short_term_lufs",
    "peaks": "peak_timeline",
    "average_spectrum": "average_spectrum",
    "spectral_shape": "spectral_shape",
    "band_power": "band_power_timeline",
    "onset": "onset_density",
    "chroma": "chroma_cqt",
    "stereo": "stereo_correlation",
    "mid_side": "mid_side_energy",
}
ANALYSIS_FAMILIES = (*SUMMARY_BLOCKS, "spectrogram")
# Current findings consume levels, peak ranges, stereo, and mid/side. RMS and
# spectral shape additionally retain core report/section/catalog measurements.
FINDING_RESULTS = frozenset({"levels", "peaks", "stereo", "mid_side"})
CORE_RESULTS = FINDING_RESULTS | {"rms", "spectral_shape"}


def validate_analysis_mode(mode: str) -> None:
    if mode not in ANALYSIS_MODES:
        raise ValueError(f"Unknown analysis mode {mode!r}. Choose full or compact.")


def default_graph_profile(mode: str) -> str:
    validate_analysis_mode(mode)
    return "compact" if mode == "compact" else "standard"


@dataclass(frozen=True)
class AnalysisPlan:
    mode: str
    required: tuple[str, ...]

    def coverage(self, computed: Sequence[str]) -> dict[str, object]:
        names = set(computed)
        if not set(self.required) <= names:
            raise ValueError("Analysis plan did not complete its required measurements")
        blocks = [key for name, key in SUMMARY_BLOCKS.items() if name in names]
        if "band_power" in names:
            blocks.append("band_energy_timeline")
        return {
            "format_version": 1,
            "mode": self.mode,
            "computed": [name for name in ANALYSIS_FAMILIES if name in names],
            "skipped": [name for name in ANALYSIS_FAMILIES if name not in names],
            "summary_blocks": blocks,
            "findings_coverage": "complete",
        }


def plan_analysis(mode: str, graphs: Sequence[GraphSpec]) -> AnalysisPlan:
    validate_analysis_mode(mode)
    required = set(SUMMARY_BLOCKS) if mode == "full" else set(CORE_RESULTS)
    required.update(
        "band_power" if name == "band_energy" else name
        for graph in graphs for name in graph.requires
    )
    unknown = required.difference(ANALYSIS_FAMILIES)
    if unknown:
        raise ValueError(f"Unknown analysis dependencies: {sorted(unknown)}")
    return AnalysisPlan(mode, tuple(name for name in ANALYSIS_FAMILIES if name in required))
