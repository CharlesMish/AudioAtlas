"""Registry of AudioAtlas report graphs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from audioatlas.analysis.bundle import _COMPUTE, AnalysisBundle
from audioatlas.config import AnalysisConfig
from audioatlas.graphs import adapters

RenderAdapter = Callable[[AnalysisBundle, Path, AnalysisConfig], Path]

RELATIVE_DB_NOTE = (
    "Relative dB values use this track's strongest measured content as 0 dB. "
    "They show shape within this song and are not calibrated dBFS."
)


class CostTier(StrEnum):
    """Coarse graph-rendering cost category for future selection work."""

    FREE = "free"
    CHEAP = "cheap"
    MEDIUM = "medium"
    EXPENSIVE = "expensive"


@dataclass(frozen=True)
class GraphSpec:
    key: str
    display_name: str
    filename: str
    order: int
    requires: tuple[str, ...]
    render: RenderAdapter
    cost_tier: CostTier
    enabled_by_default: bool
    profiles: frozenset[str]
    report_note: str | None = None
    html_caption: str | None = None
    wide: bool = False
    batch_safe: bool = True
    summary_key: str | None = None


_STANDARD_PROFILES = frozenset({"minimal", "standard", "full"})
_DEFAULT_PROFILES = frozenset({"standard", "full"})

GRAPHS: tuple[GraphSpec, ...] = (
    GraphSpec(
        key="waveform_rms",
        display_name="Waveform + RMS Envelope",
        filename="waveform_rms.png",
        order=1,
        requires=("rms",),
        render=adapters.render_waveform_rms,
        cost_tier=CostTier.CHEAP,
        enabled_by_default=True,
        profiles=frozenset({"minimal", "standard", "full"}),
        html_caption="What this shows: raw samples with the RMS envelope overlaid.",
        summary_key="rms_envelope",
    ),
    GraphSpec(
        key="rms_timeline",
        display_name="Frame RMS Timeline",
        filename="rms_timeline.png",
        order=2,
        requires=("rms",),
        render=adapters.render_rms_timeline,
        cost_tier=CostTier.FREE,
        enabled_by_default=True,
        profiles=frozenset({"minimal", "standard", "full"}),
        html_caption="What this shows: frame-by-frame RMS energy over time.",
        summary_key="rms_envelope",
    ),
    GraphSpec(
        key="crest_factor_timeline",
        display_name="Frame Crest Factor Timeline",
        filename="crest_factor_timeline.png",
        order=3,
        requires=("crest",),
        render=adapters.render_crest_factor_timeline,
        cost_tier=CostTier.FREE,
        enabled_by_default=True,
        profiles=_DEFAULT_PROFILES,
        html_caption=(
            "What this shows: per-frame peak-to-RMS contrast in dB. Higher values mean "
            "more transient-like frames within this track; this is not punch or quality."
        ),
        summary_key="crest_factor_timeline",
    ),
    GraphSpec(
        key="log_spectrogram",
        display_name="Log-Frequency Spectrogram",
        filename="log_spectrogram.png",
        order=4,
        requires=("spectrogram",),
        render=adapters.render_log_spectrogram,
        cost_tier=CostTier.MEDIUM,
        enabled_by_default=True,
        profiles=frozenset({"minimal", "standard", "full"}),
        html_caption=(
            "What this shows: frequency content over time on a log-frequency axis. "
            + RELATIVE_DB_NOTE
        ),
        wide=True,
    ),
    GraphSpec(
        key="average_spectrum",
        display_name="Welch Average Spectrum",
        filename="average_spectrum.png",
        order=5,
        requires=("average_spectrum",),
        render=adapters.render_average_spectrum,
        cost_tier=CostTier.MEDIUM,
        enabled_by_default=True,
        profiles=_DEFAULT_PROFILES,
        report_note=RELATIVE_DB_NOTE,
        html_caption=(
            "What this shows: the track's long-term Welch average spectrum. "
            + RELATIVE_DB_NOTE
        ),
        wide=True,
        summary_key="average_spectrum",
    ),
    GraphSpec(
        key="sample_histogram",
        display_name="Sample Histogram",
        filename="sample_histogram.png",
        order=6,
        requires=(),
        render=adapters.render_sample_histogram,
        cost_tier=CostTier.CHEAP,
        enabled_by_default=True,
        profiles=frozenset({"minimal", "standard", "full"}),
        html_caption=(
            "What this shows: sample-value distribution with clipping and near-clipping thresholds."
        ),
        summary_key="levels",
    ),
    GraphSpec(
        key="stereo_correlation",
        display_name="Stereo Correlation Timeline",
        filename="stereo_correlation.png",
        order=7,
        requires=("stereo",),
        render=adapters.render_stereo_correlation,
        cost_tier=CostTier.FREE,
        enabled_by_default=True,
        profiles=_DEFAULT_PROFILES,
        html_caption="What this shows: the measured left/right channel relationship over time.",
        summary_key="stereo_correlation",
    ),
    GraphSpec(
        key="mid_side_energy",
        display_name="Mid/Side Energy Timeline",
        filename="mid_side_energy.png",
        order=8,
        requires=("mid_side",),
        render=adapters.render_mid_side_energy,
        cost_tier=CostTier.FREE,
        enabled_by_default=True,
        profiles=_DEFAULT_PROFILES,
        html_caption=(
            "What this shows: mid and side RMS energy over time with the side-to-mid ratio."
        ),
        summary_key="mid_side_energy",
    ),
    GraphSpec(
        key="spectral_shape",
        display_name="Spectral Shape Timeline",
        filename="spectral_shape.png",
        order=9,
        requires=("spectral_shape",),
        render=adapters.render_spectral_shape,
        cost_tier=CostTier.MEDIUM,
        enabled_by_default=True,
        profiles=_DEFAULT_PROFILES,
        html_caption=(
            "What this shows: spectral centroid, rolloff, and bandwidth movement over time."
        ),
        summary_key="spectral_shape",
    ),
    GraphSpec(
        key="band_energy_timeline",
        display_name="Relative Mean Band Power Timeline",
        filename="band_energy_timeline.png",
        order=10,
        requires=("band_power",),
        render=adapters.render_band_power_timeline,
        cost_tier=CostTier.MEDIUM,
        enabled_by_default=True,
        profiles=_DEFAULT_PROFILES,
        report_note=(
            "Each band is the mean STFT power per included FFT bin, then normalized "
            "within this track. It is not total energy integrated across differently "
            "sized bands. "
            + RELATIVE_DB_NOTE
        ),
        html_caption=(
            "What this shows: relative mean spectral power per FFT bin in broad "
            "frequency bands over time. It is not integrated band energy. "
            + RELATIVE_DB_NOTE
        ),
        wide=True,
        summary_key="band_power_timeline",
    ),
    GraphSpec(
        key="onset_density",
        display_name="Onset / Transient Density Timeline",
        filename="onset_density.png",
        order=11,
        requires=("onset",),
        render=adapters.render_onset_density,
        cost_tier=CostTier.MEDIUM,
        enabled_by_default=True,
        profiles=_DEFAULT_PROFILES,
        html_caption=(
            "What this shows: attack/activity movement within this track, not punch or quality."
        ),
        wide=True,
        summary_key="onset_density",
    ),
    GraphSpec(
        key="chroma_cqt",
        display_name="Chroma CQT (Pitch-Class Energy)",
        filename="chroma_cqt.png",
        order=12,
        requires=("chroma",),
        render=adapters.render_chroma_cqt,
        cost_tier=CostTier.MEDIUM,
        enabled_by_default=True,
        profiles=_DEFAULT_PROFILES,
        html_caption=(
            "What this shows: pitch-class energy over time within this track. "
            "This is not key detection and values are not calibrated across unrelated songs."
        ),
        wide=True,
        summary_key="chroma_cqt",
    ),
    GraphSpec(
        key="short_term_lufs",
        display_name="Short-term LUFS Timeline",
        filename="short_term_lufs.png",
        order=13,
        requires=("short_term",),
        render=adapters.render_short_term_lufs,
        cost_tier=CostTier.MEDIUM,
        enabled_by_default=True,
        profiles=_DEFAULT_PROFILES,
        report_note=(
            "Short-term LUFS uses 3 s K-weighted blocks (distinct from the RMS timeline). "
            "The dashed reference line (when present) is the track integrated LUFS."
        ),
        html_caption=(
            "What this shows: K-weighted short-term loudness in 3 s windows over time. "
            "This is distinct from the RMS timeline and from integrated LUFS."
        ),
        wide=True,
        summary_key="short_term_lufs",
    ),
    GraphSpec(
        key="peak_timeline",
        display_name="Sample-Peak Timeline",
        filename="peak_timeline.png",
        order=14,
        requires=("peaks",),
        render=adapters.render_peak_timeline,
        cost_tier=CostTier.FREE,
        enabled_by_default=True,
        profiles=_DEFAULT_PROFILES,
        report_note=(
            "Per-frame sample-peak level over time (sample peak, not true peak). "
            "Clipping and near-clipping markers flag threshold crossings; they do not "
            "prove audible distortion."
        ),
        html_caption=(
            "What this shows: per-frame sample peak level over time. "
            "Clipping and near-clipping markers identify threshold crossings; "
            "they do not prove audible distortion."
        ),
        summary_key="peak_timeline",
    ),
    GraphSpec(
        key="peak_vs_rms",
        display_name="Peak vs RMS Levels",
        filename="peak_vs_rms.png",
        order=15,
        requires=("peaks", "rms"),
        render=adapters.render_peak_vs_rms,
        cost_tier=CostTier.FREE,
        enabled_by_default=False,
        profiles=frozenset({"full"}),
        report_note=(
            "Sample-peak and RMS levels on one dBFS axis. A levels-and-contrast view, "
            "not a judgment about dynamics or compression."
        ),
        html_caption=(
            "What this shows: sample-peak and RMS level movement on the same "
            "dBFS axis. This is a levels and contrast view, not a dynamics judgment."
        ),
        summary_key="peak_timeline",
    ),
    GraphSpec(
        key="rms_histogram",
        display_name="RMS Level Distribution",
        filename="rms_histogram.png",
        order=16,
        requires=("rms",),
        render=adapters.render_rms_histogram,
        cost_tier=CostTier.FREE,
        enabled_by_default=False,
        profiles=frozenset({"full"}),
        report_note=(
            "How often each per-frame RMS level occurs across this track. "
            "A distribution, not a loudness target."
        ),
        html_caption=(
            "What this shows: distribution of per-frame RMS levels. "
            "This is a distribution, not a loudness target."
        ),
        summary_key="rms_envelope",
    ),
    GraphSpec(
        key="stereo_correlation_histogram",
        display_name="Stereo Correlation Distribution",
        filename="stereo_correlation_histogram.png",
        order=17,
        requires=("stereo",),
        render=adapters.render_stereo_correlation_histogram,
        cost_tier=CostTier.FREE,
        enabled_by_default=False,
        profiles=frozenset({"full"}),
        report_note=(
            "Distribution of per-frame left/right correlation; undefined low-energy "
            "frames are excluded. A distribution, not a mono-compatibility verdict."
        ),
        html_caption=(
            "What this shows: distribution of defined left/right correlation frames; "
            "undefined low-energy frames are excluded. This is a distribution, "
            "not a mono-compatibility verdict."
        ),
        summary_key="stereo_correlation",
    ),
)


def all_graphs() -> tuple[GraphSpec, ...]:
    """Return all registered graphs in render order."""

    return tuple(sorted(GRAPHS, key=lambda graph: graph.order))


def graph_by_key(key: str) -> GraphSpec:
    """Return a graph by stable key."""

    for graph in GRAPHS:
        if graph.key == key:
            return graph
    raise KeyError(key)


def graph_by_filename(filename: str) -> GraphSpec:
    """Return a graph by output filename."""

    for graph in GRAPHS:
        if graph.filename == filename:
            return graph
    raise KeyError(filename)


def validate_registry() -> None:
    """Validate registry integrity for tests and startup checks."""

    keys = [graph.key for graph in GRAPHS]
    filenames = [graph.filename for graph in GRAPHS]
    orders = [graph.order for graph in GRAPHS]
    if len(GRAPHS) != 17:
        raise ValueError(f"Expected 17 graphs, found {len(GRAPHS)}")
    if len(set(keys)) != len(keys):
        raise ValueError("Graph keys must be unique")
    if len(set(filenames)) != len(filenames):
        raise ValueError("Graph filenames must be unique")
    if len(set(orders)) != len(orders):
        raise ValueError("Graph orders must be unique")

    for graph in GRAPHS:
        unknown_requires = [name for name in graph.requires if name not in _COMPUTE]
        if unknown_requires:
            raise ValueError(f"{graph.key} requires unknown analyses: {unknown_requires}")
        if not callable(graph.render):
            raise ValueError(f"{graph.key} render adapter is not callable")
        if not graph.profiles <= _STANDARD_PROFILES:
            raise ValueError(f"{graph.key} has unknown profiles: {sorted(graph.profiles)}")
        if graph.enabled_by_default != ("standard" in graph.profiles):
            raise ValueError(f"{graph.key} default enablement does not match standard profile")


validate_registry()
