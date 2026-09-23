"""CLI report-depth convenience presets; measurement and summary contracts are unchanged."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from audioatlas.graphs.selection import GraphSelection

REPORT_DEPTHS = {
    "overview": ("compact", "compact"),
    "standard": ("full", "standard"),
    "detailed": ("full", "full"),
}


@dataclass(frozen=True)
class ReportPlan:
    depth: str
    analysis_mode: str
    selection: GraphSelection
    plot_count: int
    restored: tuple[str, ...]

    def display(self) -> str:
        return (
            f"Report depth: {self.depth}\n"
            f"Analysis breadth: {self.analysis_mode.title()}\n"
            f"Plots: {self.plot_count} per report\n"
            f"Additional restored analyses: {', '.join(self.restored) or 'none'}"
        )


def resolve_report_plan(
    depth: str | None, mode: str, selection: GraphSelection,
) -> ReportPlan:
    """Resolve only existing controls; never introduce a new pipeline mode.

    Presets promise a fixed pair. Advanced selections that change that promise
    are rejected; without a preset every existing advanced combination remains
    available and unmatched combinations are described as Custom.
    """
    from audioatlas.execution import plan_analysis
    from audioatlas.graphs import GraphSelection, all_graphs

    graphs = all_graphs()
    selected = selection.resolve(graphs)
    plan = plan_analysis(mode, selected)
    matched_depth = "Custom"
    for name, (preset_mode, preset_profile) in REPORT_DEPTHS.items():
        expected = GraphSelection(profile=preset_profile).resolve(graphs)
        if mode == preset_mode and selected == expected:
            matched_depth = name.title()
    if depth is not None:
        if depth not in REPORT_DEPTHS:
            raise ValueError(f"Unknown report depth {depth!r}.")
        if matched_depth != depth.title():
            raise ValueError(
                f"--report-depth {depth} conflicts with the selected computation or plots. "
                "Remove --report-depth to customize with --analysis-mode, --graphs-profile, "
                "--enable/--disable, or YAML; otherwise remove the conflicting overrides."
            )
        selection = GraphSelection(profile=REPORT_DEPTHS[depth][1])
    compact_default = plan_analysis("compact", GraphSelection(profile="compact").resolve(graphs))
    restored = tuple(name for name in plan.required if name not in compact_default.required) \
        if mode == "compact" else ()
    return ReportPlan(matched_depth, mode, selection, len(selected), restored)
