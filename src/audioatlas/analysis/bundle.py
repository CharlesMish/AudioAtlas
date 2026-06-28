"""Lazy analysis result bundle for graph rendering."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from audioatlas.analysis.dynamics import compute_onset_density
from audioatlas.analysis.levels import (
    compute_crest_factor_timeline,
    compute_peak_timeline,
    compute_rms_envelope,
    compute_scalar_levels,
)
from audioatlas.analysis.loudness import compute_short_term_lufs
from audioatlas.analysis.spectral import (
    compute_average_spectrum,
    compute_band_energy_timeline,
    compute_log_spectrogram,
    compute_spectral_shape,
)
from audioatlas.analysis.stereo import compute_mid_side_energy, compute_stereo_correlation
from audioatlas.analysis.tonal import compute_chroma_cqt
from audioatlas.config import AnalysisConfig
from audioatlas.io import AudioData

AnalysisCompute = Callable[[Any, int, AnalysisConfig], object]

_COMPUTE: dict[str, AnalysisCompute] = {
    "levels": compute_scalar_levels,
    "rms": compute_rms_envelope,
    "crest": compute_crest_factor_timeline,
    "short_term": compute_short_term_lufs,
    "peaks": compute_peak_timeline,
    "spectrogram": compute_log_spectrogram,
    "average_spectrum": compute_average_spectrum,
    "spectral_shape": compute_spectral_shape,
    "band_energy": compute_band_energy_timeline,
    "onset": compute_onset_density,
    "chroma": compute_chroma_cqt,
    "stereo": compute_stereo_correlation,
    "mid_side": compute_mid_side_energy,
}


class AnalysisBundle:
    """Compute and memoize analysis results once per run."""

    def __init__(self, audio: AudioData, config: AnalysisConfig) -> None:
        self.audio = audio
        self.config = config
        self._cache: dict[str, object] = {}

    def get(self, name: str) -> object:
        """Return a named analysis result, computing it on first access."""

        if name not in _COMPUTE:
            raise KeyError(f"Unknown analysis result: {name}")
        if name not in self._cache:
            self._cache[name] = _COMPUTE[name](self.audio.y, self.audio.sr, self.config)
        return self._cache[name]

