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
    all_findings: list[Finding] = field(default_factory=list)
    findings_suppressed_count: int = 0
    max_findings: int | None = None

    def to_dict(self) -> dict[str, object]:
        all_findings = self.all_findings or self.findings
        return {
            "count": len(self.findings),
            "all_count": len(all_findings),
            "max_findings": self.max_findings,
            "findings_suppressed_count": self.findings_suppressed_count,
            "findings": [finding.to_dict() for finding in self.findings],
            "findings_shown": [finding.to_dict() for finding in self.findings],
            "all_findings": [finding.to_dict() for finding in all_findings],
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

    analysis_config = (
        summary.get("analysis_config") if isinstance(summary.get("analysis_config"), dict) else {}
    )
    max_findings = _positive_int(analysis_config, "max_findings", default=8)
    band_min_duration = _non_negative_number(
        analysis_config, "band_finding_min_duration_seconds", default=0.5
    )
    min_range_duration = _non_negative_number(
        analysis_config, "finding_min_time_range_seconds", default=0.25
    )
    db_floor = _number(analysis_config, "db_floor")
    if db_floor is None:
        db_floor = -100.0
    band_min_relative_db = _number(analysis_config, "band_finding_min_relative_db")
    if band_min_relative_db is None:
        band_min_relative_db = max(float(db_floor) + 20.0, -80.0)

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
    band_energy_timeline = (
        summary.get("band_energy_timeline")
        if isinstance(summary.get("band_energy_timeline"), dict)
        else {}
    )
    onset_density = (
        summary.get("onset_density") if isinstance(summary.get("onset_density"), dict) else {}
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
        negative_ranges = _ranges_at_least(
            stereo, "correlation_below_0_time_ranges", min_range_duration
        )
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

    low_corr_ranges = _ranges_at_least(
        stereo, "correlation_below_0_3_time_ranges", min_range_duration
    )
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
        side_ratio_ranges = _ranges_at_least(
            mid_side, "side_to_mid_ratio_above_minus_6_time_ranges", min_range_duration
        )
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

    centroid_median = _number(spectral_shape, "centroid_median_hz")
    elevated_ranges = _ranges_at_least(
        spectral_shape, "centroid_elevated_time_ranges", min_range_duration
    )
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

    reduced_ranges = _ranges_at_least(
        spectral_shape, "centroid_reduced_time_ranges", min_range_duration
    )
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

    shift_ranges = _ranges_at_least(
        spectral_shape, "centroid_large_shift_time_ranges", min_range_duration
    )
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

    band_timeline_bands = band_energy_timeline.get("bands")
    band_observations: list[dict[str, object]] = []
    if isinstance(band_timeline_bands, dict):
        for band, band_values in band_timeline_bands.items():
            if not isinstance(band_values, dict):
                continue
            elevated_ranges = _ranges_at_least(
                band_values, "elevated_time_ranges", band_min_duration
            )
            median_db = _number(band_values, "median_db")
            max_db = _number(band_values, "max_db")
            elevated_threshold = _number(band_values, "elevated_threshold_db")
            if (
                elevated_ranges
                and median_db is not None
                and max_db is not None
                and elevated_threshold is not None
                and median_db > band_min_relative_db
                and max_db > band_min_relative_db
            ):
                band_observations.append(
                    {
                        "band": str(band),
                        "direction": "elevated",
                        "median_db": median_db,
                        "threshold_db": elevated_threshold,
                        "time_ranges": elevated_ranges,
                    }
                )

            if band in {"high", "air"}:
                reduced_ranges = _ranges_at_least(
                    band_values, "reduced_time_ranges", band_min_duration
                )
                reduced_threshold = _number(band_values, "reduced_threshold_db")
                if (
                    reduced_ranges
                    and median_db is not None
                    and reduced_threshold is not None
                    and median_db > band_min_relative_db
                ):
                    band_observations.append(
                        {
                            "band": str(band),
                            "direction": "reduced",
                            "median_db": median_db,
                            "threshold_db": reduced_threshold,
                            "time_ranges": reduced_ranges,
                        }
                    )

    if band_observations:
        ranges: list[dict[str, float]] = []
        for observation in band_observations:
            observation_ranges = observation.get("time_ranges")
            if isinstance(observation_ranges, list):
                ranges.extend(observation_ranges)
        if len(band_observations) == 1:
            observation = band_observations[0]
            band = observation["band"]
            direction = observation["direction"]
            median_db = float(observation["median_db"])
            threshold_db = float(observation["threshold_db"])
            findings.append(
                Finding(
                    severity="info",
                    category="spectrum",
                    title=f"{band} band energy is {direction} relative to this track's median",
                    measured_value=median_db,
                    threshold=threshold_db,
                    unit="dB relative",
                    evidence=(
                        f"{band} median band energy measured {_fmt_measure(median_db)} dB; "
                        f"{len(ranges)} time range(s) exceed the duration and energy filters."
                    ),
                    why_it_matters=(
                        "This marks regions where a broad frequency band differs from its "
                        "own track-level median by a heuristic threshold."
                    ),
                    suggested_checks=[
                        f"Inspect the band energy timeline around the {band} band in these regions.",
                        "Listen for arrangement or EQ density changes in these regions.",
                    ],
                    confidence="medium",
                    time_ranges=ranges,
                )
            )
        else:
            labels = [f"{item['band']} {item['direction']}" for item in band_observations]
            findings.append(
                Finding(
                    severity="info",
                    category="spectrum",
                    title="Multiple band-energy changes detected",
                    measured_value=len(band_observations),
                    threshold=1,
                    unit="band observations",
                    evidence=(
                        "Affected bands after duration and energy filters: "
                        + ", ".join(labels)
                        + "."
                    ),
                    why_it_matters=(
                        "This groups broad frequency-band changes that crossed relative "
                        "track-level thresholds."
                    ),
                    suggested_checks=[
                        "Inspect the frequency band energy timeline around the listed regions.",
                        "Check whether arrangement, source content, or processing changes align with these regions.",
                    ],
                    confidence="medium",
                    time_ranges=ranges,
                )
            )

    high_onset_ranges = _ranges_at_least(
        onset_density, "high_onset_density_time_ranges", min_range_duration
    )
    onset_density_median = _number(onset_density, "onset_density_median")
    if high_onset_ranges and onset_density_median is not None:
        findings.append(
            Finding(
                severity="info",
                category="dynamics",
                title="Onset density is elevated relative to this track's median",
                measured_value=onset_density_median,
                threshold=_number(onset_density, "high_onset_density_threshold") or 0,
                unit="onset strength",
                evidence=(
                    f"onset_density_median measured {_fmt_measure(onset_density_median)}; "
                    f"{len(high_onset_ranges)} time range(s) exceed the relative threshold."
                ),
                why_it_matters=(
                    "This marks regions with higher onset-strength activity by a relative "
                    "track-level heuristic."
                ),
                suggested_checks=[
                    "Check whether these sections feel rhythmically dense or transient-heavy.",
                    "Inspect drums, strums, plucks, consonants, or percussive elements in these regions.",
                ],
                confidence="medium",
                time_ranges=high_onset_ranges,
            )
        )

    sorted_findings = _sort_findings(findings)
    shown = sorted_findings[:max_findings]
    return FindingsResult(
        findings=shown,
        all_findings=sorted_findings,
        findings_suppressed_count=max(0, len(sorted_findings) - len(shown)),
        max_findings=max_findings,
    )


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


def _ranges_at_least(block: dict, key: str, min_duration: float) -> list[dict[str, float]]:
    return [item for item in _ranges(block, key) if item["duration"] >= min_duration]


def _positive_int(block: dict, key: str, *, default: int) -> int:
    value = block.get(key)
    if isinstance(value, bool):
        return default
    if isinstance(value, int) and value > 0:
        return value
    return default


def _non_negative_number(block: dict, key: str, *, default: float) -> float:
    value = block.get(key)
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)) and value >= 0:
        return float(value)
    return default


def _sort_findings(findings: list[Finding]) -> list[Finding]:
    severity_order = {"issue": 0, "warning": 1, "info": 2}

    def priority_area(finding: Finding) -> int:
        title = finding.title.lower()
        if "clipping" in title or "clipped" in title:
            return 1
        if "onset" in title:
            return 5
        if finding.category == "levels":
            return 0
        if finding.category == "dynamics":
            return 2
        if finding.category == "stereo":
            return 3
        if finding.category == "spectrum":
            return 4
        return 6

    indexed = list(enumerate(findings))
    indexed.sort(
        key=lambda item: (
            severity_order[item[1].severity],
            priority_area(item[1]),
            item[0],
        )
    )
    return [finding for _index, finding in indexed]
