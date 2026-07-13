"""Factual findings generated from existing summary data."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

from audioatlas.release import FINDING_RULESET_VERSION, FINDINGS_SCHEMA_VERSION

Severity = Literal["info", "warning", "issue"]
Category = Literal["levels", "dynamics", "stereo", "spectrum", "metadata"]
Confidence = Literal["low", "medium", "high"]
Comparator = Literal[">", ">=", "<", "<=", "=="]


@dataclass(frozen=True)
class EvidenceItem:
    """One machine-readable measurement supporting a finding.

    ``label`` remains suitable for direct report display. The other fields make
    the trigger auditable without parsing prose.
    """

    metric: str
    label: str
    value: float | int
    unit: str
    comparator: Comparator | None = None
    threshold: float | int | None = None
    time_ranges: list[dict[str, float]] = field(default_factory=list)


@dataclass(frozen=True)
class Finding:
    rule_id: str
    rule_version: int
    severity: Severity
    category: Category
    title: str
    measured_value: float | int | None
    threshold: float | int | None
    unit: str
    evidence: str
    why_it_matters: str
    does_not_mean: str
    suggested_checks: list[str]
    confidence: Confidence
    time_ranges: list[dict[str, float]] = field(default_factory=list)
    evidence_items: list[EvidenceItem] = field(default_factory=list)
    associated_graphs: list[str] = field(default_factory=list)

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
            "schema_version": FINDINGS_SCHEMA_VERSION,
            "ruleset_version": FINDING_RULESET_VERSION,
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
    min_range_duration = _non_negative_number(
        analysis_config, "finding_min_time_range_seconds", default=0.25
    )

    levels = summary.get("levels") if isinstance(summary.get("levels"), dict) else {}
    metadata = summary.get("metadata") if isinstance(summary.get("metadata"), dict) else {}
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
    findings: list[Finding] = []
    track_duration = _number(levels, "duration_seconds")
    is_lossy = _is_lossy_metadata(metadata)
    sample_label = "decoded samples" if is_lossy else "samples"
    near_clip_sample_label = (
        "decoded near-clipping samples" if is_lossy else "near-clipping samples"
    )
    audio_label = "decoded audio" if is_lossy else "audio"

    true_peak = _number(levels, "true_peak_dbtp")
    near_clipping = _number(levels, "near_clipping_samples")
    near_clip_ranges = _ranges(peak_timeline, "near_clipping_time_ranges")
    meaningful_near_clip_ranges = _ranges_at_least(
        peak_timeline, "near_clipping_time_ranges", min_range_duration
    )
    clipped = _number(levels, "clipped_samples")
    true_peak_does_not_mean = (
        "This does not establish whether the original master clipped or is audibly distorting."
        if is_lossy
        else "This does not mean the file is audibly distorting."
    )
    near_clip_does_not_mean = (
        "This does not establish whether the original master clipped."
        if is_lossy
        else "This does not mean the passage is clipped or audibly distorted."
    )
    clipped_does_not_mean = (
        "This does not establish whether the original master clipped or what caused the decoded samples."
        if is_lossy
        else "This does not identify the cause of the clipping or whether it was intentional."
    )
    if true_peak is not None and true_peak > 0.0:
        true_peak_evidence = (
            f"Approximate true peak measured {_fmt_measure(true_peak)} dBTP."
        )
        true_peak_evidence_items = [
            EvidenceItem(
                metric="levels.true_peak_dbtp",
                label=true_peak_evidence,
                value=true_peak,
                unit="dBTP",
                comparator=">",
                threshold=0.0,
            )
        ]
        if (
            near_clipping is not None
            and 0 < near_clipping <= 10
            and not meaningful_near_clip_ranges
            and (clipped is None or clipped <= 0)
        ):
            near_clip_count = int(near_clipping)
            near_clip_label = (
                near_clip_sample_label.removesuffix("s")
                if near_clip_count == 1
                else near_clip_sample_label
            )
            true_peak_evidence += (
                f" Near-clipping count measured {near_clip_count} {near_clip_label}."
            )
            true_peak_evidence_items.append(
                EvidenceItem(
                    metric="levels.near_clipping_samples",
                    label=(
                        f"Near-clipping count measured {near_clip_count} {near_clip_label}."
                    ),
                    value=near_clip_count,
                    unit="samples",
                    comparator=">",
                    threshold=0,
                )
            )
        findings.append(
            Finding(
                rule_id="levels.true_peak_above_zero",
                rule_version=1,
                severity="warning",
                category="levels",
                title="Approximate true peak is above 0 dBTP",
                measured_value=true_peak,
                threshold=0.0,
                unit="dBTP",
                evidence=true_peak_evidence,
                why_it_matters=(
                    "Samples reconstructed by downstream playback or encoding can exceed "
                    "nominal full scale when true peak is above 0 dBTP."
                ),
                does_not_mean=true_peak_does_not_mean,
                suggested_checks=[
                    "Check a dedicated true-peak meter if this file will be encoded or limited.",
                    "Inspect the loudest passage for inter-sample peak behavior.",
                ],
                confidence="medium",
                evidence_items=true_peak_evidence_items,
                associated_graphs=["peak_timeline", "waveform_rms"],
            )
        )

    if near_clipping is not None and near_clipping > 0:
        near_clipping_count = int(near_clipping)
        if (
            true_peak is not None
            and true_peak > 0.0
            and near_clipping_count <= 10
            and not meaningful_near_clip_ranges
            and (clipped is None or clipped <= 0)
        ):
            near_clipping_severity = None
        elif true_peak is not None and true_peak > 0.0:
            near_clipping_severity: Severity | None = "warning"
        elif near_clipping_count <= 10:
            near_clipping_severity = None
        elif near_clipping_count < 100:
            near_clipping_severity = "info"
        else:
            near_clipping_severity = "warning"
    else:
        near_clipping_severity = None
    if near_clipping is not None and near_clipping > 0 and near_clipping_severity is not None:
        findings.append(
            Finding(
                rule_id="levels.near_full_scale_samples",
                rule_version=1,
                severity=near_clipping_severity,
                category="levels",
                title="Near-full-scale samples detected",
                measured_value=int(near_clipping),
                threshold=0,
                unit="samples",
                evidence=(
                    f"Near-clipping count measured {int(near_clipping)} "
                    f"{near_clip_sample_label}."
                ),
                why_it_matters=(
                    f"Near-full-scale {sample_label} can leave little margin for later encoding, "
                    "sample-rate conversion, or level changes."
                ),
                does_not_mean=near_clip_does_not_mean,
                suggested_checks=[
                    "Inspect the sample histogram and peak values.",
                    "Check whether near-full-scale samples cluster in a specific passage.",
                ],
                confidence="high",
                time_ranges=near_clip_ranges,
                evidence_items=[
                    EvidenceItem(
                        metric="levels.near_clipping_samples",
                        label=(
                            f"Near-clipping count measured {int(near_clipping)} "
                            f"{near_clip_sample_label}."
                        ),
                        value=int(near_clipping),
                        unit="samples",
                        comparator=">",
                        threshold=0,
                        time_ranges=near_clip_ranges,
                    )
                ],
                associated_graphs=["peak_timeline", "sample_histogram", "waveform_rms"],
            )
        )

    if clipped is not None and clipped > 0:
        findings.append(
            Finding(
                rule_id="levels.sample_clipping",
                rule_version=1,
                severity="issue",
                category="levels",
                title="Sample clipping detected",
                measured_value=int(clipped),
                threshold=0,
                unit="samples",
                evidence=f"Sample clipping count measured {int(clipped)} in {sample_label}.",
                why_it_matters=(
                    "Samples at or beyond the clipping threshold can indicate flattened "
                    f"waveform peaks in the {audio_label}."
                ),
                does_not_mean=clipped_does_not_mean,
                suggested_checks=[
                    "Inspect the waveform around peak sections.",
                    "Check whether clipping is intentional source material or processing.",
                ],
                confidence="high",
                evidence_items=[
                    EvidenceItem(
                        metric="levels.clipped_samples",
                        label=(
                            f"Sample clipping count measured {int(clipped)} in {sample_label}."
                        ),
                        value=int(clipped),
                        unit="samples",
                        comparator=">",
                        threshold=0,
                    )
                ],
                associated_graphs=["peak_timeline", "waveform_rms", "sample_histogram"],
            )
        )

    plr = _number(levels, "plr_db")
    plr_has_independent_level_context = (
        (true_peak is not None and true_peak > 0.0)
        or (near_clipping is not None and near_clipping >= 100)
        or (clipped is not None and clipped > 0)
    )
    if plr is not None and plr < 8.0 and plr_has_independent_level_context:
        plr_evidence_items = [
            EvidenceItem(
                metric="levels.plr_db",
                label=f"Peak-to-loudness ratio measured {_fmt_measure(plr)} dB.",
                value=plr,
                unit="dB",
                comparator="<",
                threshold=8.0,
            )
        ]
        if true_peak is not None and true_peak > 0.0:
            plr_evidence_items.append(
                EvidenceItem(
                    metric="levels.true_peak_dbtp",
                    label=f"Approximate true peak measured {_fmt_measure(true_peak)} dBTP.",
                    value=true_peak,
                    unit="dBTP",
                    comparator=">",
                    threshold=0.0,
                )
            )
        if near_clipping is not None and near_clipping >= 100:
            plr_evidence_items.append(
                EvidenceItem(
                    metric="levels.near_clipping_samples",
                    label=(
                        f"Near-clipping count measured {int(near_clipping)} "
                        f"{near_clip_sample_label}."
                    ),
                    value=int(near_clipping),
                    unit="samples",
                    comparator=">=",
                    threshold=100,
                )
            )
        if clipped is not None and clipped > 0:
            plr_evidence_items.append(
                EvidenceItem(
                    metric="levels.clipped_samples",
                    label=f"Sample clipping count measured {int(clipped)} in {sample_label}.",
                    value=int(clipped),
                    unit="samples",
                    comparator=">",
                    threshold=0,
                )
            )
        findings.append(
            Finding(
                rule_id="dynamics.low_plr_with_level_pressure",
                rule_version=2,
                severity="warning",
                category="dynamics",
                title="Low peak-to-loudness ratio accompanies a high-level footprint",
                measured_value=plr,
                threshold=8.0,
                unit="dB",
                evidence=" ".join(item.label for item in plr_evidence_items),
                why_it_matters=(
                    "Low PLR means the highest reconstructed peak sits relatively close to "
                    "integrated loudness. Alongside the separate high-level measurement, it is "
                    "useful context for inspecting dense, limited, clipped, or intentionally "
                    "distorted passages."
                ),
                does_not_mean=(
                    "This does not identify compression, transient quality, audibility, or a "
                    "delivery problem by itself. Loudness normalization changes both measurements "
                    "by the same gain and does not change PLR."
                ),
                suggested_checks=[
                    "Inspect the crest-factor, frame-RMS, and peak timelines together.",
                    "Listen for whether dense sections and transient sections feel distinct enough for the intent.",
                ],
                confidence="medium",
                evidence_items=plr_evidence_items,
                associated_graphs=[
                    "crest_factor_timeline",
                    "rms_timeline",
                    "peak_timeline",
                    "waveform_rms",
                ],
            )
        )

    side_ratio = _number(mid_side, "side_to_mid_ratio_db_median")
    corr_median = _number(stereo, "correlation_median")
    negative_ranges = _ranges_at_least(
        stereo, "correlation_below_0_time_ranges", min_range_duration
    )
    low_corr_ranges = _ranges_at_least(
        stereo, "correlation_below_0_3_time_ranges", min_range_duration
    )
    negative_duration = _total_duration(negative_ranges)
    low_corr_duration = _total_duration(low_corr_ranges)
    negative_percent = _duration_percent(negative_duration, track_duration)
    low_corr_percent = _duration_percent(low_corr_duration, track_duration)
    healthy_stereo_context = (
        corr_median is not None
        and corr_median > 0.75
        and (side_ratio is None or side_ratio < -8.0)
    )

    corr_min = _number(stereo, "correlation_min")
    stereo_evidence: list[str] = []
    stereo_evidence_items: list[EvidenceItem] = []
    stereo_severity: Severity | None = None
    stereo_confidence: Confidence = "medium"
    side_ratio_ranges: list[dict[str, float]] = []

    if corr_min is not None and corr_min < 0.0 and negative_ranges:
        negative_is_brief = _is_brief_stereo_duration(
            negative_duration, negative_percent
        )
        stereo_warning_context = _has_stereo_warning_context(
            corr_median,
            side_ratio,
            negative_duration,
            negative_percent,
        )
        if healthy_stereo_context and negative_is_brief:
            negative_severity: Severity | None = "info"
        elif stereo_warning_context:
            negative_severity = "warning"
        else:
            negative_severity = "info"
    else:
        negative_severity = None
    if corr_min is not None and corr_min < 0.0 and negative_ranges and negative_severity:
        corr_min_label = f"Minimum frame correlation: {_fmt_measure(corr_min)}."
        negative_duration_label = (
            f"Total time below 0 correlation: {_fmt_measure(negative_duration)} seconds "
            f"across {len(negative_ranges)} region(s)."
        )
        stereo_evidence.extend([corr_min_label, negative_duration_label])
        stereo_evidence_items.extend(
            [
                EvidenceItem(
                    metric="stereo_correlation.correlation_min",
                    label=corr_min_label,
                    value=corr_min,
                    unit="correlation",
                    comparator="<",
                    threshold=0.0,
                    time_ranges=negative_ranges,
                ),
                EvidenceItem(
                    metric="stereo_correlation.correlation_below_0_total_duration_seconds",
                    label=negative_duration_label,
                    value=negative_duration,
                    unit="seconds",
                    comparator=">",
                    threshold=0.0,
                    time_ranges=negative_ranges,
                ),
            ]
        )
        stereo_severity = _max_severity(stereo_severity, negative_severity)

    low_corr_is_brief = _is_brief_stereo_duration(low_corr_duration, low_corr_percent)
    if low_corr_ranges and not (healthy_stereo_context and low_corr_is_brief):
        low_corr_label = (
            f"Total time below 0.3 correlation: {_fmt_measure(low_corr_duration)} seconds "
            f"across {len(low_corr_ranges)} region(s)."
        )
        stereo_evidence.append(low_corr_label)
        stereo_evidence_items.append(
            EvidenceItem(
                metric="stereo_correlation.correlation_below_0_3_total_duration_seconds",
                label=low_corr_label,
                value=low_corr_duration,
                unit="seconds",
                comparator=">",
                threshold=0.0,
                time_ranges=low_corr_ranges,
            )
        )
        stereo_severity = _max_severity(stereo_severity, "info")

    if corr_median is not None and corr_median < 0.5:
        corr_median_label = f"Median L/R correlation: {_fmt_measure(corr_median)}."
        stereo_evidence.append(corr_median_label)
        stereo_evidence_items.append(
            EvidenceItem(
                metric="stereo_correlation.correlation_median",
                label=corr_median_label,
                value=corr_median,
                unit="correlation",
                comparator="<",
                threshold=0.5,
            )
        )
        stereo_severity = _max_severity(stereo_severity, "warning")

    side_ratio = _number(mid_side, "side_to_mid_ratio_db_median")
    if side_ratio is not None and side_ratio > -6.0:
        side_ratio_ranges = _ranges_at_least(
            mid_side, "side_to_mid_ratio_above_minus_6_time_ranges", min_range_duration
        )
        side_ratio_label = f"Median side/mid ratio: {_fmt_measure(side_ratio)} dB."
        stereo_evidence.append(side_ratio_label)
        stereo_evidence_items.append(
            EvidenceItem(
                metric="mid_side_energy.side_to_mid_ratio_db_median",
                label=side_ratio_label,
                value=side_ratio,
                unit="dB",
                comparator=">",
                threshold=-6.0,
                time_ranges=side_ratio_ranges,
            )
        )
        if side_ratio_ranges:
            side_ratio_regions_label = (
                f"Side/mid ratio above -6 dB: {len(side_ratio_ranges)} region(s)."
            )
            stereo_evidence.append(side_ratio_regions_label)
            stereo_evidence_items.append(
                EvidenceItem(
                    metric="mid_side_energy.side_to_mid_ratio_above_minus_6_regions",
                    label=side_ratio_regions_label,
                    value=len(side_ratio_ranges),
                    unit="regions",
                    comparator=">",
                    threshold=0,
                    time_ranges=side_ratio_ranges,
                )
            )
        stereo_severity = _max_severity(stereo_severity, "info")

    if stereo_evidence and stereo_severity is not None:
        unique_checks = [
            "Inspect the stereo correlation timeline around the lowest-correlation regions.",
            "Listen in mono around sustained low-correlation regions if mono compatibility matters.",
            "Inspect the mid/side energy plot around side-heavy regions.",
        ]
        stereo_title = (
            "Stereo field shows sustained low-correlation / side-heavy regions"
            if len(stereo_evidence) > 1
            else "Stereo image shows a wide / low-correlation passage"
        )
        stereo_display_ranges = (
            low_corr_ranges
            if low_corr_ranges
            else negative_ranges if negative_ranges else side_ratio_ranges
        )
        if len(stereo_evidence_items) == 1:
            primary = stereo_evidence_items[0]
            primary_value: float | int | None = primary.value
            primary_threshold: float | int | None = primary.threshold
            primary_unit = primary.unit
        else:
            primary_value = None
            primary_threshold = None
            primary_unit = ""
        findings.append(
            Finding(
                rule_id="stereo.low_correlation_or_side_heavy",
                rule_version=1,
                severity=stereo_severity,
                category="stereo",
                title=stereo_title,
                measured_value=primary_value,
                threshold=primary_threshold,
                unit=primary_unit,
                evidence="; ".join(stereo_evidence),
                why_it_matters=(
                    "Low correlation and higher side energy can point to passages where mono "
                    "playback may change tone, level, apparent width, or center focus."
                ),
                does_not_mean=(
                    "This does not mean the stereo image is incorrect; wide and phase-rich material "
                    "can be intentional."
                ),
                suggested_checks=unique_checks,
                confidence=stereo_confidence,
                time_ranges=_dedupe_ranges(stereo_display_ranges),
                evidence_items=stereo_evidence_items,
                associated_graphs=["stereo_correlation", "mid_side_energy"],
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


def _total_duration(ranges: list[dict[str, float]]) -> float:
    return float(sum(item["duration"] for item in ranges))


def _duration_percent(duration: float, track_duration: float | int | None) -> float | None:
    if track_duration is None or track_duration <= 0:
        return None
    return float(100.0 * duration / track_duration)


def _is_brief_stereo_duration(duration: float, percent: float | None) -> bool:
    if percent is None:
        return duration < 0.5
    return duration < 0.5 or percent < 1.0


def _has_stereo_warning_context(
    corr_median: float | int | None,
    side_ratio: float | int | None,
    duration: float,
    percent: float | None,
) -> bool:
    if corr_median is not None and corr_median < 0.5:
        return True
    if side_ratio is not None and side_ratio > -6.0:
        return True
    return duration >= 0.5 and (percent is None or percent >= 1.0)


def _max_severity(current: Severity | None, candidate: Severity) -> Severity:
    if current is None:
        return candidate
    severity_order = {"info": 0, "warning": 1, "issue": 2}
    return candidate if severity_order[candidate] > severity_order[current] else current


def _dedupe_ranges(ranges: list[dict[str, float]]) -> list[dict[str, float]]:
    out: list[dict[str, float]] = []
    seen: set[tuple[float, float, float]] = set()
    for item in ranges:
        key = (item["start"], item["end"], item["duration"])
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _is_lossy_metadata(metadata: dict) -> bool:
    values = [
        str(metadata.get("format", "")),
        str(metadata.get("subtype", "")),
        str(metadata.get("filename", "")),
        str(metadata.get("path", "")),
    ]
    text = " ".join(values).lower()
    return any(token in text for token in ("mp3", "mpeg", "aac", "ogg", "opus", "vorbis", "m4a"))


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
