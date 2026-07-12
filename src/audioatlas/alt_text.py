"""Measured-value alternative text for AudioAtlas report plots.

Alt text is derived from the already-computed summary. It must not recompute
analysis, infer quality, or imply musical content the analyzer did not detect.
"""

from __future__ import annotations

import math
from typing import Any

ALT_GRAPH_METADATA: dict[str, tuple[str, str]] = {
    "waveform_rms.png": ("waveform_rms", "Waveform + RMS Envelope"),
    "rms_timeline.png": ("rms_timeline", "Frame RMS Timeline"),
    "crest_factor_timeline.png": (
        "crest_factor_timeline",
        "Frame Crest Factor Timeline",
    ),
    "log_spectrogram.png": ("log_spectrogram", "Log-Frequency Spectrogram"),
    "average_spectrum.png": ("average_spectrum", "Welch Average Spectrum"),
    "sample_histogram.png": ("sample_histogram", "Sample Histogram"),
    "stereo_correlation.png": (
        "stereo_correlation",
        "Stereo Correlation Timeline",
    ),
    "mid_side_energy.png": ("mid_side_energy", "Mid/Side Energy Timeline"),
    "spectral_shape.png": ("spectral_shape", "Spectral Shape Timeline"),
    "band_energy_timeline.png": (
        "band_energy_timeline",
        "Relative Mean Band Power Timeline",
    ),
    "onset_density.png": ("onset_density", "Onset / Transient Density Timeline"),
    "chroma_cqt.png": ("chroma_cqt", "Chroma CQT (Pitch-Class Energy)"),
    "short_term_lufs.png": ("short_term_lufs", "Short-term LUFS Timeline"),
    "peak_timeline.png": ("peak_timeline", "Sample-Peak Timeline"),
    "peak_vs_rms.png": ("peak_vs_rms", "Peak vs RMS Levels"),
    "rms_histogram.png": ("rms_histogram", "RMS Level Distribution"),
    "stereo_correlation_histogram.png": (
        "stereo_correlation_histogram",
        "Stereo Correlation Distribution",
    ),
}


def plot_alt_text(filename: str, summary: dict[str, Any]) -> str:
    """Return concise measured-value alt text for one registered plot."""

    graph_metadata = ALT_GRAPH_METADATA.get(filename)
    if graph_metadata is None:
        return filename.rsplit(".", maxsplit=1)[0].replace("_", " ").title()
    key, title = graph_metadata

    duration = _number(_block(summary, "levels").get("duration_seconds"))
    duration_text = f" across {_fmt(duration, 2)} seconds" if duration is not None else ""

    if key in {"waveform_rms", "rms_timeline", "rms_histogram"}:
        rms = _block(summary, "rms_envelope")
        low = _number(rms.get("rms_dbfs_min"))
        high = _number(rms.get("rms_dbfs_max"))
        return _with_range(
            f"{title}{duration_text}",
            low,
            high,
            "dBFS RMS",
        )

    if key == "crest_factor_timeline":
        crest = _block(summary, "crest_factor_timeline")
        return _with_range(
            f"{title}{duration_text}",
            _number(crest.get("crest_factor_db_min")),
            _number(crest.get("crest_factor_db_max")),
            "dB crest factor",
        )

    if key == "log_spectrogram":
        metadata = _block(summary, "metadata")
        sample_rate = _number(metadata.get("samplerate"))
        if sample_rate is not None:
            return (
                f"{title}{duration_text}, showing relative spectral level from 20 to "
                f"{_fmt(sample_rate / 2.0, 0)} Hz."
            )
        return f"{title}{duration_text}, showing relative spectral level over time and frequency."

    if key == "average_spectrum":
        spectrum = _block(summary, "average_spectrum")
        strongest = _number(spectrum.get("strongest_bin_hz"))
        band = spectrum.get("highest_mean_power_band", spectrum.get("strongest_band"))
        details: list[str] = []
        if strongest is not None:
            details.append(f"strongest measured bin {_fmt(strongest, 1)} Hz")
        if isinstance(band, str) and band:
            details.append(f"highest mean-power band {band.replace('_', ' ')}")
        return _sentence(title, details or ["relative spectral shape within this track"])

    if key == "sample_histogram":
        levels = _block(summary, "levels")
        peak = _number(levels.get("sample_peak_dbfs"))
        clipped = _integer(levels.get("clipped_samples"))
        near = _integer(levels.get("near_clipping_samples"))
        details: list[str] = []
        if peak is not None:
            details.append(f"sample peak {_fmt(peak, 2)} dBFS")
        if clipped is not None:
            details.append(f"{clipped} clipped samples")
        if near is not None:
            details.append(f"{near} near-clipping samples")
        return _sentence(title, details or ["decoded sample-value distribution"])

    if key in {"stereo_correlation", "stereo_correlation_histogram"}:
        stereo = _block(summary, "stereo_correlation")
        low = _number(stereo.get("correlation_min"))
        high = _number(stereo.get("correlation_max"))
        median = _number(stereo.get("correlation_median"))
        text = _with_range(f"{title}{duration_text}", low, high, "Pearson r")
        if median is not None:
            text = text.removesuffix(".") + f"; median {_fmt(median, 3)}."
        return text

    if key == "mid_side_energy":
        block = _block(summary, "mid_side_energy")
        mid_low = _number(block.get("mid_rms_dbfs_min"))
        mid_high = _number(block.get("mid_rms_dbfs_max"))
        side_low = _number(block.get("side_rms_dbfs_min"))
        side_high = _number(block.get("side_rms_dbfs_max"))
        ratio = _number(block.get("side_to_mid_ratio_db_median"))
        details: list[str] = []
        if mid_low is not None and mid_high is not None:
            details.append(f"mid {_fmt(mid_low, 1)} to {_fmt(mid_high, 1)} dBFS")
        if side_low is not None and side_high is not None:
            details.append(f"side {_fmt(side_low, 1)} to {_fmt(side_high, 1)} dBFS")
        if ratio is not None:
            details.append(f"median side-to-mid ratio {_fmt(ratio, 2)} dB")
        return _sentence(f"{title}{duration_text}", details or ["mid and side RMS over time"])

    if key == "spectral_shape":
        shape = _block(summary, "spectral_shape")
        centroid_low = _number(shape.get("centroid_min_hz"))
        centroid_high = _number(shape.get("centroid_max_hz"))
        rolloff = _number(shape.get("rolloff_95_median_hz"))
        details: list[str] = []
        if centroid_low is not None and centroid_high is not None:
            details.append(
                f"centroid {_fmt(centroid_low, 0)} to {_fmt(centroid_high, 0)} Hz"
            )
        if rolloff is not None:
            details.append(f"median 95-percent rolloff {_fmt(rolloff, 0)} Hz")
        return _sentence(f"{title}{duration_text}", details or ["spectral centroid, rolloff, and bandwidth"])

    if key == "band_energy_timeline":
        block = _block(summary, "band_power_timeline")
        if not block:
            block = _block(summary, "band_energy_timeline")
        bands = block.get("bands") if isinstance(block.get("bands"), dict) else {}
        medians = [
            value
            for item in bands.values()
            if isinstance(item, dict)
            for value in [_number(item.get("median_db"))]
            if value is not None
        ]
        strongest = block.get(
            "highest_mean_power_band_by_median",
            block.get("strongest_band_by_median"),
        )
        details: list[str] = []
        if medians:
            details.append(
                f"band medians {_fmt(min(medians), 1)} to {_fmt(max(medians), 1)} dB relative"
            )
        if isinstance(strongest, str) and strongest:
            details.append(f"highest median band {strongest.replace('_', ' ')}")
        details.append("mean power per included FFT bin")
        return _sentence(f"{title}{duration_text}", details)

    if key == "onset_density":
        onset = _block(summary, "onset_density")
        median = _number(onset.get("onset_density_median"))
        maximum = _number(onset.get("onset_density_max"))
        details: list[str] = []
        if median is not None:
            details.append(f"median {_fmt(median, 3)}")
        if maximum is not None:
            details.append(f"maximum {_fmt(maximum, 3)}")
        details.append("relative attack activity, not punch or quality")
        return _sentence(f"{title}{duration_text}", details)

    if key == "chroma_cqt":
        chroma = _block(summary, "chroma_cqt")
        dominant = chroma.get("dominant_pitch_class")
        details = (
            [f"largest mean pitch-class bin {dominant}"]
            if isinstance(dominant, str) and dominant
            else ["no dominant pitch-class bin reported"]
        )
        details.append("not a key estimate")
        return _sentence(f"{title}{duration_text}", details)

    if key == "short_term_lufs":
        loudness = _block(summary, "short_term_lufs")
        low = _number(loudness.get("lufs_min"))
        high = _number(loudness.get("lufs_max"))
        text = _with_range(f"{title}{duration_text}", low, high, "LUFS")
        median = _number(loudness.get("lufs_median"))
        if median is not None:
            text = text.removesuffix(".") + f"; median {_fmt(median, 2)} LUFS."
        return text

    if key == "peak_timeline":
        peak = _block(summary, "peak_timeline")
        values = _numeric_list(peak.get("frame_peak_dbfs"))
        near_frames = _integer(peak.get("frames_with_near_clipping"))
        text = _with_range(
            f"{title}{duration_text}",
            min(values) if values else None,
            max(values) if values else None,
            "dBFS sample peak",
        )
        if near_frames is not None:
            text = text.removesuffix(".") + f"; {near_frames} frames with near-clipping."
        return text

    if key == "peak_vs_rms":
        peak = _block(summary, "peak_timeline")
        rms = _block(summary, "rms_envelope")
        peak_values = _numeric_list(peak.get("frame_peak_dbfs"))
        details: list[str] = []
        if peak_values:
            details.append(
                f"sample peak {_fmt(min(peak_values), 1)} to {_fmt(max(peak_values), 1)} dBFS"
            )
        rms_low = _number(rms.get("rms_dbfs_min"))
        rms_high = _number(rms.get("rms_dbfs_max"))
        if rms_low is not None and rms_high is not None:
            details.append(f"RMS {_fmt(rms_low, 1)} to {_fmt(rms_high, 1)} dBFS")
        return _sentence(f"{title}{duration_text}", details or ["sample peak and RMS on one level axis"])

    return f"{title}{duration_text}."


def _block(summary: dict[str, Any], key: str) -> dict[str, Any]:
    value = summary.get(key)
    return value if isinstance(value, dict) else {}


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return int(round(number)) if number is not None else None


def _numeric_list(value: Any) -> list[float]:
    if not isinstance(value, list):
        return []
    return [number for item in value for number in [_number(item)] if number is not None]


def _fmt(value: float | None, decimals: int) -> str:
    if value is None:
        return "unknown"
    if decimals == 0:
        return f"{value:.0f}"
    return f"{value:.{decimals}f}"


def _with_range(prefix: str, low: float | None, high: float | None, unit: str) -> str:
    if low is None or high is None:
        return f"{prefix}; measured range unavailable."
    return f"{prefix}; measured range {_fmt(low, 2)} to {_fmt(high, 2)} {unit}."


def _sentence(prefix: str, details: list[str]) -> str:
    return f"{prefix}; " + "; ".join(details) + "."
