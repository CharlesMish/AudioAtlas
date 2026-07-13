"""Render adapters connecting graph records to visualization functions."""

from __future__ import annotations

from pathlib import Path

from audioatlas.analysis.bundle import AnalysisBundle
from audioatlas.analysis.dynamics import OnsetDensityResult
from audioatlas.analysis.levels import (
    CrestFactorTimelineResult,
    PeakTimelineResult,
    RmsEnvelopeResult,
)
from audioatlas.analysis.loudness import ShortTermLufsResult
from audioatlas.analysis.spectral import (
    AverageSpectrumResult,
    BandPowerTimelineResult,
    SpectralShapeResult,
    SpectrogramResult,
)
from audioatlas.analysis.stereo import MidSideEnergyResult, StereoCorrelationResult
from audioatlas.analysis.tonal import ChromaCqtResult
from audioatlas.config import AnalysisConfig
from audioatlas.visualize.band_energy import plot_band_power_timeline
from audioatlas.visualize.chroma import plot_chroma_cqt
from audioatlas.visualize.histogram import plot_sample_histogram
from audioatlas.visualize.loudness import plot_short_term_lufs
from audioatlas.visualize.onset import plot_onset_density
from audioatlas.visualize.spectral_shape import plot_spectral_shape
from audioatlas.visualize.spectrogram import plot_log_spectrogram
from audioatlas.visualize.spectrum import plot_average_spectrum
from audioatlas.visualize.stereo import (
    plot_mid_side_energy,
    plot_stereo_correlation,
    plot_stereo_correlation_histogram,
)
from audioatlas.visualize.waveform import (
    plot_crest_factor_timeline,
    plot_peak_timeline,
    plot_peak_vs_rms,
    plot_rms_histogram,
    plot_rms_timeline,
    plot_waveform_rms,
)


def render_waveform_rms(
    bundle: AnalysisBundle, out_path: Path, config: AnalysisConfig
) -> Path:
    return plot_waveform_rms(
        bundle.audio.y,
        bundle.audio.sr,
        bundle.get("rms"),  # type: ignore[arg-type]
        out_path,
        config,
    )


def render_rms_timeline(
    bundle: AnalysisBundle, out_path: Path, config: AnalysisConfig
) -> Path:
    rms = bundle.get("rms")
    assert isinstance(rms, RmsEnvelopeResult)
    return plot_rms_timeline(rms, out_path, config)


def render_crest_factor_timeline(
    bundle: AnalysisBundle, out_path: Path, config: AnalysisConfig
) -> Path:
    del config
    crest = bundle.get("crest")
    assert isinstance(crest, CrestFactorTimelineResult)
    return plot_crest_factor_timeline(crest, out_path)


def render_log_spectrogram(
    bundle: AnalysisBundle, out_path: Path, config: AnalysisConfig
) -> Path:
    del config
    spec = bundle.get("spectrogram")
    assert isinstance(spec, SpectrogramResult)
    return plot_log_spectrogram(spec, out_path)


def render_average_spectrum(
    bundle: AnalysisBundle, out_path: Path, config: AnalysisConfig
) -> Path:
    spectrum = bundle.get("average_spectrum")
    assert isinstance(spectrum, AverageSpectrumResult)
    return plot_average_spectrum(spectrum, out_path, config)


def render_sample_histogram(
    bundle: AnalysisBundle, out_path: Path, config: AnalysisConfig
) -> Path:
    return plot_sample_histogram(bundle.audio.y, out_path, config)


def render_stereo_correlation(
    bundle: AnalysisBundle, out_path: Path, config: AnalysisConfig
) -> Path:
    del config
    stereo = bundle.get("stereo")
    assert isinstance(stereo, StereoCorrelationResult)
    return plot_stereo_correlation(stereo, out_path)


def render_mid_side_energy(
    bundle: AnalysisBundle, out_path: Path, config: AnalysisConfig
) -> Path:
    mid_side = bundle.get("mid_side")
    assert isinstance(mid_side, MidSideEnergyResult)
    return plot_mid_side_energy(mid_side, out_path, config)


def render_spectral_shape(
    bundle: AnalysisBundle, out_path: Path, config: AnalysisConfig
) -> Path:
    del config
    spectral_shape = bundle.get("spectral_shape")
    assert isinstance(spectral_shape, SpectralShapeResult)
    return plot_spectral_shape(spectral_shape, out_path)


def render_band_power_timeline(
    bundle: AnalysisBundle, out_path: Path, config: AnalysisConfig
) -> Path:
    del config
    band_power = bundle.get("band_power")
    assert isinstance(band_power, BandPowerTimelineResult)
    return plot_band_power_timeline(band_power, out_path)


def render_band_energy_timeline(
    bundle: AnalysisBundle, out_path: Path, config: AnalysisConfig
) -> Path:
    """Deprecated adapter alias for the stable graph key and filename."""

    return render_band_power_timeline(bundle, out_path, config)


def render_onset_density(
    bundle: AnalysisBundle, out_path: Path, config: AnalysisConfig
) -> Path:
    del config
    onset = bundle.get("onset")
    assert isinstance(onset, OnsetDensityResult)
    return plot_onset_density(onset, out_path)


def render_chroma_cqt(
    bundle: AnalysisBundle, out_path: Path, config: AnalysisConfig
) -> Path:
    del config
    chroma = bundle.get("chroma")
    assert isinstance(chroma, ChromaCqtResult)
    return plot_chroma_cqt(chroma, out_path)


def render_short_term_lufs(
    bundle: AnalysisBundle, out_path: Path, config: AnalysisConfig
) -> Path:
    del config
    short_term = bundle.get("short_term")
    assert isinstance(short_term, ShortTermLufsResult)
    return plot_short_term_lufs(short_term, out_path)


def render_peak_timeline(
    bundle: AnalysisBundle, out_path: Path, config: AnalysisConfig
) -> Path:
    peaks = bundle.get("peaks")
    assert isinstance(peaks, PeakTimelineResult)
    return plot_peak_timeline(peaks, out_path, config)


def render_peak_vs_rms(
    bundle: AnalysisBundle, out_path: Path, config: AnalysisConfig
) -> Path:
    peaks = bundle.get("peaks")
    rms = bundle.get("rms")
    assert isinstance(peaks, PeakTimelineResult)
    assert isinstance(rms, RmsEnvelopeResult)
    return plot_peak_vs_rms(peaks, rms, out_path, config)


def render_rms_histogram(
    bundle: AnalysisBundle, out_path: Path, config: AnalysisConfig
) -> Path:
    rms = bundle.get("rms")
    assert isinstance(rms, RmsEnvelopeResult)
    return plot_rms_histogram(rms, out_path, config)


def render_stereo_correlation_histogram(
    bundle: AnalysisBundle, out_path: Path, config: AnalysisConfig
) -> Path:
    del config
    stereo = bundle.get("stereo")
    assert isinstance(stereo, StereoCorrelationResult)
    return plot_stereo_correlation_histogram(stereo, out_path)
