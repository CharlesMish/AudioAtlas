"""Factual findings generated from existing summary data."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

Severity = Literal["info", "warning", "issue"]
Category = Literal["levels", "dynamics", "stereo", "spectrum", "metadata"]
Confidence = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class Finding:
    severity: Severity
    category: Category
    title: str
    measured_value: float | int
    threshold: float | int
    unit: str
    evidence: str
    why_it_matters: str
    suggested_checks: list[str]
    confidence: Confidence
    time_ranges: list[dict[str, float]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class FindingsResult:
    findings: list[Finding]

    def to_dict(self) -> dict[str, object]:
        return {
            "count": len(self.findings),
            "findings": [finding.to_dict() for finding in self.findings],
        }


def _number(block: dict, key: str) -> float | int | None:
    value = block.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def generate_findings(summary: dict) -> FindingsResult:
    """Generate factual findings from an AudioAtlas summary dictionary."""

    levels = summary.get("levels") if isinstance(summary.get("levels"), dict) else {}
    stereo = (
        summary.get("stereo_correlation")
        if isinstance(summary.get("stereo_correlation"), dict)
        else {}
    )
    peak_timeline = (
        summary.get("peak_timeline") if isinstance(summary.get("peak_timeline"), dict) else {}
    )
    mid_side = (
        summary.get("mid_side_energy") if isinstance(summary.get("mid_side_energy"), dict) else {}
    )
    spectrum = (
        summary.get("average_spectrum") if isinstance(summary.get("average_spectrum"), dict) else {}
    )
    spectral_shape = (
        summary.get("spectral_shape") if isinstance(summary.get("spectral_shape"), dict) else {}
    )

    findings: list[Finding] = []

    true_peak = _number(levels, "true_peak_dbtp")
    if true_peak is not None and true_peak > 0.0:
        findings.append(
            Finding(
                severity="warning",
                category="levels",
                title="Approximate true peak is above 0 dBTP",
                measured_value=true_peak,
                threshold=0.0,
                unit="dBTP",
                evidence=f"true_peak_dbtp measured {_fmt_measure(true_peak)} dBTP.",
                why_it_matters=(
                    "Samples reconstructed by downstream playback or encoding can exceed "
                    "nominal full scale when true peak is above 0 dBTP."
                ),
                suggested_checks=[
                    "Check a dedicated true-peak meter if this file will be encoded or limited.",
                    "Inspect the loudest passage for inter-sample peak behavior.",
                ],
                confidence="medium",
            )
        )

    near_clipping = _number(levels, "near_clipping_samples")
    if near_clipping is not None and near_clipping > 0:
        near_clip_ranges = _ranges(peak_timeline, "near_clipping_time_ranges")
        findings.append(
            Finding(
                severity="warning",
                category="levels",
                title="Near-full-scale samples detected",
                measured_value=int(near_clipping),
                threshold=0,
                unit="samples",
                evidence=f"near_clipping_samples measured {int(near_clipping)}.",
                why_it_matters=(
                    "Samples near full scale can indicate limited headroom, even when no "
                    "sample reaches the clipping threshold."
                ),
                suggested_checks=[
                    "Inspect the sample histogram and peak values.",
                    "Check whether near-full-scale samples cluster in a specific passage.",
                ],
                confidence="high",
                time_ranges=near_clip_ranges,
            )
        )

    clipped = _number(levels, "clipped_samples")
    if clipped is not None and clipped > 0:
        findings.append(
            Finding(
                severity="issue",
                category="levels",
                title="Sample clipping detected",
                measured_value=int(clipped),
                threshold=0,
                unit="samples",
                evidence=f"clipped_samples measured {int(clipped)}.",
                why_it_matters=(
                    "Samples at or beyond the clipping threshold can indicate flattened "
                    "waveform peaks in the decoded audio."
                ),
                suggested_checks=[
                    "Inspect the waveform around peak sections.",
                    "Check whether clipping is intentional source material or processing.",
                ],
                confidence="high",
            )
        )

    integrated_lufs = _number(levels, "integrated_lufs")
    if integrated_lufs is not None and integrated_lufs > -10.0:
        findings.append(
            Finding(
                severity="info",
                category="levels",
                title="Integrated loudness is above -10 LUFS",
                measured_value=integrated_lufs,
                threshold=-10.0,
                unit="LUFS",
                evidence=f"integrated_lufs measured {_fmt_measure(integrated_lufs)} LUFS.",
                why_it_matters=(
                    "Integrated LUFS is a whole-track loudness measurement; values above "
                    "-10 LUFS indicate a high measured loudness for this file."
                ),
                suggested_checks=[
                    "Compare this measured loudness with the intended delivery context.",
                    "Check PLR and waveform/RMS plots for additional context.",
                ],
                confidence="high",
            )
        )

    plr = _number(levels, "plr_db")
    if plr is not None and plr < 8.0:
        findings.append(
            Finding(
                severity="warning",
                category="dynamics",
                title="Peak-to-loudness ratio is below 8 dB",
                measured_value=plr,
                threshold=8.0,
                unit="dB",
                evidence=f"plr_db measured {_fmt_measure(plr)} dB.",
                why_it_matters=(
                    "PLR is the difference between true peak and integrated LUFS; lower "
                    "values indicate less peak headroom relative to measured loudness."
                ),
                suggested_checks=[
                    "Inspect the frame RMS timeline alongside peak metrics.",
                    "Check whether this PLR matches the intended production style.",
                ],
                confidence="medium",
            )
        )

    corr_min = _number(stereo, "correlation_min")
    if corr_min is not None and corr_min < 0.0:
        negative_ranges = _ranges(stereo, "correlation_below_0_time_ranges")
        findings.append(
            Finding(
                severity="warning",
                category="stereo",
                title="Minimum L/R correlation is below 0",
                measured_value=corr_min,
                threshold=0.0,
                unit="Pearson r",
                evidence=f"correlation_min measured {_fmt_measure(corr_min)}.",
                why_it_matters=(
                    "Negative L/R correlation can indicate phase-inverted content in at "
                    "least part of the measured timeline."
                ),
                suggested_checks=[
                    "Inspect the stereo correlation plot around the low-correlation region.",
                    "Listen in mono around these regions if mono compatibility matters.",
                ],
                confidence="medium",
                time_ranges=negative_ranges,
            )
        )

    low_corr_ranges = _ranges(stereo, "correlation_below_0_3_time_ranges")
    if low_corr_ranges:
        findings.append(
            Finding(
                severity="info",
                category="stereo",
                title="L/R correlation falls below 0.3 in some regions",
                measured_value=len(low_corr_ranges),
                threshold=0.3,
                unit="regions",
                evidence=(
                    f"{len(low_corr_ranges)} time range(s) have frame correlation below 0.3."
                ),
                why_it_matters=(
                    "Low L/R correlation marks regions where the two channels are less "
                    "similar by this measurement."
                ),
                suggested_checks=[
                    "Inspect the stereo correlation plot around these regions.",
                    "Listen in mono around these regions if mono compatibility matters.",
                ],
                confidence="medium",
                time_ranges=low_corr_ranges,
            )
        )

    corr_median = _number(stereo, "correlation_median")
    if corr_median is not None and corr_median < 0.5:
        findings.append(
            Finding(
                severity="warning",
                category="stereo",
                title="Median L/R correlation is below 0.5",
                measured_value=corr_median,
                threshold=0.5,
                unit="Pearson r",
                evidence=f"correlation_median measured {_fmt_measure(corr_median)}.",
                why_it_matters=(
                    "A lower median L/R correlation indicates less similarity between the "
                    "left and right channels over the measured frames."
                ),
                suggested_checks=[
                    "Inspect the stereo correlation timeline for persistent low-correlation sections.",
                    "Check whether the stereo presentation matches the intended playback context.",
                ],
                confidence="medium",
            )
        )

    side_ratio = _number(mid_side, "side_to_mid_ratio_db_median")
    if side_ratio is not None and side_ratio > -6.0:
        side_ratio_ranges = _ranges(mid_side, "side_to_mid_ratio_above_minus_6_time_ranges")
        findings.append(
            Finding(
                severity="info",
                category="stereo",
                title="Median side-to-mid ratio is above -6 dB",
                measured_value=side_ratio,
                threshold=-6.0,
                unit="dB",
                evidence=f"side_to_mid_ratio_db_median measured {_fmt_measure(side_ratio)} dB.",
                why_it_matters=(
                    "A higher side-to-mid ratio means side-channel RMS is closer to mid-channel "
                    "RMS in the measured frames."
                ),
                suggested_checks=[
                    "Inspect the mid/side energy plot and side-to-mid ratio panel.",
                    "Listen in mono around these regions if side-heavy sections matter.",
                ],
                confidence="medium",
                time_ranges=side_ratio_ranges,
            )
        )

    strongest_bin = _number(spectrum, "strongest_bin_hz")
    if strongest_bin is not None and 120.0 <= strongest_bin <= 350.0:
        findings.append(
            Finding(
                severity="info",
                category="spectrum",
                title="Strongest average-spectrum bin is in the low-mid region",
                measured_value=strongest_bin,
                threshold=120,
                unit="Hz",
                evidence=f"strongest_bin_hz measured {_fmt_measure(strongest_bin)} Hz.",
                why_it_matters=(
                    "This identifies where the strongest Welch average-spectrum bin falls; "
                    "it does not describe whether the balance is desirable."
                ),
                suggested_checks=[
                    "Inspect the average spectrum plot around 120-350 Hz.",
                    "Listen for which instruments or sources occupy that region.",
                ],
                confidence="medium",
            )
        )

    strongest_band = spectrum.get("strongest_band")
    band_energies = spectrum.get("band_energies")
    if isinstance(strongest_band, str) and isinstance(band_energies, dict):
        band_values = band_energies.get(strongest_band)
        energy_db = (
            band_values.get("energy_db")
            if isinstance(band_values, dict)
            else None
        )
        if isinstance(energy_db, (int, float)):
            findings.append(
                Finding(
                    severity="info",
                    category="spectrum",
                    title=f"Strongest average-spectrum band is {strongest_band}",
                    measured_value=float(energy_db),
                    threshold=0,
                    unit="dB relative",
                    evidence=(
                        f"strongest_band measured {strongest_band}; "
                        f"band energy measured {_fmt_measure(float(energy_db))} dB relative."
                    ),
                    why_it_matters=(
                        "This identifies the named frequency band with the highest measured "
                        "average-spectrum band energy."
                    ),
                    suggested_checks=[
                        f"Inspect the average spectrum around the {strongest_band} band.",
                        "Listen for which sources occupy the strongest measured band.",
                    ],
                    confidence="medium",
                )
            )

    centroid_median = _number(spectral_shape, "centroid_median_hz")
    elevated_ranges = _ranges(spectral_shape, "centroid_elevated_time_ranges")
    if centroid_median is not None and elevated_ranges:
        findings.append(
            Finding(
                severity="info",
                category="spectrum",
                title="Spectral centroid is elevated relative to this track's median",
                measured_value=centroid_median,
                threshold=_number(spectral_shape, "centroid_elevated_threshold_hz") or 0,
                unit="Hz",
                evidence=(
                    f"centroid_median_hz measured {_fmt_measure(centroid_median)} Hz; "
                    f"{len(elevated_ranges)} time range(s) exceed the relative threshold."
                ),
                why_it_matters=(
                    "Spectral centroid is a frequency-distribution statistic; elevated "
                    "regions indicate the centroid is higher than this track's median by "
                    "the configured heuristic."
                ),
                suggested_checks=[
                    "Inspect EQ, arrangement density, cymbals, distortion, or vocal presence in these regions.",
                    "Check whether these sections sound brighter or denser; centroid is only a proxy.",
                ],
                confidence="medium",
                time_ranges=elevated_ranges,
            )
        )

    reduced_ranges = _ranges(spectral_shape, "centroid_reduced_time_ranges")
    if centroid_median is not None and reduced_ranges:
        findings.append(
            Finding(
                severity="info",
                category="spectrum",
                title="Spectral centroid is reduced relative to this track's median",
                measured_value=centroid_median,
                threshold=_number(spectral_shape, "centroid_reduced_threshold_hz") or 0,
                unit="Hz",
                evidence=(
                    f"centroid_median_hz measured {_fmt_measure(centroid_median)} Hz; "
                    f"{len(reduced_ranges)} time range(s) fall below the relative threshold."
                ),
                why_it_matters=(
                    "Spectral centroid is a frequency-distribution statistic; reduced "
                    "regions indicate the centroid is lower than this track's median by "
                    "the configured heuristic."
                ),
                suggested_checks=[
                    "Inspect EQ, arrangement density, instrumentation, or source changes in these regions.",
                    "Check whether these sections sound less high-frequency-weighted; centroid is only a proxy.",
                ],
                confidence="medium",
                time_ranges=reduced_ranges,
            )
        )

    rolloff_95_median = _number(spectral_shape, "rolloff_95_median_hz")
    if rolloff_95_median is not None and rolloff_95_median < 8000.0:
        findings.append(
            Finding(
                severity="info",
                category="spectrum",
                title="Median 95% spectral rolloff is below 8 kHz",
                measured_value=rolloff_95_median,
                threshold=8000.0,
                unit="Hz",
                evidence=(
                    f"rolloff_95_median_hz measured {_fmt_measure(rolloff_95_median)} Hz."
                ),
                why_it_matters=(
                    "Rolloff 95% marks the frequency below which 95% of measured spectral "
                    "energy falls for each frame; this finding describes concentration of "
                    "energy, not quality."
                ),
                suggested_checks=[
                    "Inspect the spectral shape timeline and log spectrogram.",
                    "Check whether instrumentation, cymbals, distortion, or vocal presence explain the measured rolloff.",
                ],
                confidence="medium",
            )
        )

    shift_ranges = _ranges(spectral_shape, "centroid_large_shift_time_ranges")
    if shift_ranges:
        findings.append(
            Finding(
                severity="info",
                category="spectrum",
                title="Spectral centroid changes sharply in some regions",
                measured_value=len(shift_ranges),
                threshold=_number(spectral_shape, "centroid_large_shift_threshold_hz") or 0,
                unit="regions",
                evidence=(
                    f"{len(shift_ranges)} time range(s) exceed the relative centroid-change heuristic."
                ),
                why_it_matters=(
                    "Sharp centroid changes can mark transitions in arrangement, instrumentation, "
                    "or processing by this frequency-distribution measurement."
                ),
                suggested_checks=[
                    "Inspect the spectral shape timeline around these regions.",
                    "Check whether arrangement or source changes align with the measured shifts.",
                ],
                confidence="medium",
                time_ranges=shift_ranges,
            )
        )

    return FindingsResult(findings=findings)


def _fmt_measure(value: float | int) -> str:
    if isinstance(value, int):
        return str(value)
    return f"{value:.3f}"


def _ranges(block: dict, key: str) -> list[dict[str, float]]:
    value = block.get(key)
    if not isinstance(value, list):
        return []
    out: list[dict[str, float]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        start = item.get("start")
        end = item.get("end")
        duration = item.get("duration")
        if isinstance(start, (int, float)) and isinstance(end, (int, float)):
            if isinstance(duration, (int, float)):
                item_duration = float(duration)
            else:
                item_duration = float(end - start)
            out.append(
                {
                    "start": float(start),
                    "end": float(end),
                    "duration": item_duration,
                }
            )
    return out
