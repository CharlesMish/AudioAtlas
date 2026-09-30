"""Small internal vocabulary, not a public schema or universal units framework."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MeasurementReference:
    identity: str
    unit: str
    channel_basis: str
    normalization: str
    does_not_mean: str


REFERENCES = {
    "mono_rms": MeasurementReference(
        "decoded_full_scale",
        "dBFS",
        "arithmetic_average_mono",
        "amplitude 1",
        "Not pooled-channel RMS or hearing-weighted loudness; opposing channels can cancel.",
    ),
    "sample_peak": MeasurementReference(
        "decoded_full_scale",
        "dBFS",
        "all_channels",
        "amplitude 1",
        "Not reconstructed true peak or loudness.",
    ),
    "crest": MeasurementReference(
        "amplitude_ratio",
        "dB",
        "all_channels",
        "frame peak / pooled frame RMS",
        "Not punch, compression amount, or a quality score.",
    ),
    "short_term": MeasurementReference(
        "k_weighted_loudness",
        "LUFS",
        "pyloudnorm_channel_weights",
        "BS.1770 offset",
        "Not instantaneous loudness; the integration window and filter history matter.",
    ),
    "stereo": MeasurementReference(
        "dimensionless",
        "Pearson r",
        "channels_0_1",
        "demeaned covariance / deviations",
        "Not perceived width; mono +1 is a convention; multichannel uses channels 0/1.",
    ),
    "mid_side": MeasurementReference(
        "amplitude_ratio",
        "dB",
        "mid_side_channels_0_1",
        "side RMS / mid RMS",
        "Not perceived width; side uses a numerical floor, undefined mid is not zero.",
    ),
    "lr_balance": MeasurementReference(
        "amplitude_ratio",
        "dB",
        "exactly_two_channels",
        "left RMS / right RMS",
        "Not pan position, perceived balance, or an imbalance finding.",
    ),
    "centroid": MeasurementReference(
        "frequency",
        "Hz",
        "arithmetic_average_mono",
        "magnitude-weighted mean frequency",
        "Not note pitch or an EQ recommendation.",
    ),
    "band_power": MeasurementReference(
        "within_analysis_relative",
        "dB relative",
        "arithmetic_average_mono",
        "maximum mean FFT-bin power over every band/frame in this analyzed view",
        "Not absolute band level, integrated band energy, or cross-view level change.",
    ),
    "onset": MeasurementReference(
        "log_mel_flux",
        "raw onset strength",
        "arithmetic_average_mono",
        "positive lag-1 log-mel change, moving mean; global top-dB clipping",
        "Not events per second, punch, or rhythm quality.",
    ),
    "chroma": MeasurementReference(
        "normalized_within_frame",
        "relative pitch-class energy",
        "arithmetic_average_mono",
        "maximum per frame",
        "Not F0, tuning, or a scalar evidence lane.",
    ),
}
