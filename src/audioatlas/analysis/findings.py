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
    mid_side = (
        summary.get("mid_side_energy") if isinstance(summary.get("mid_side_energy"), dict) else {}
    )
    spectrum = (
        summary.get("average_spectrum") if isinstance(summary.get("average_spectrum"), dict) else {}
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
                    "Check mono playback if this material needs mono compatibility.",
                ],
                confidence="medium",
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
                    "Check mono playback if side-heavy sections are important to translation.",
                ],
                confidence="medium",
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

    return FindingsResult(findings=findings)


def _fmt_measure(value: float | int) -> str:
    if isinstance(value, int):
        return str(value)
    return f"{value:.3f}"
