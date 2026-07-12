"""Graph selection profiles and validation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from audioatlas.graph_profiles import VALID_PROFILES, selection_profile

if TYPE_CHECKING:
    from audioatlas.graphs.registry import GraphSpec


class GraphSelectionError(ValueError):
    """Raised when graph selection input cannot be resolved."""


@dataclass(frozen=True)
class GraphSelection:
    """Rendering selection for report graphs.

    This is intentionally separate from ``AnalysisConfig`` because it controls
    plot rendering only, not DSP behavior.
    """

    profile: str = "standard"
    enable: tuple[str, ...] = ()
    disable: tuple[str, ...] = ()

    def resolve(self, graphs: Sequence[GraphSpec]) -> tuple[GraphSpec, ...]:
        """Validate and return selected graph specs ordered by ``GraphSpec.order``."""

        ordered_graphs = tuple(sorted(graphs, key=lambda graph: graph.order))
        graph_by_key = {graph.key: graph for graph in ordered_graphs}
        valid_keys = tuple(graph_by_key)

        if self.profile not in VALID_PROFILES:
            raise GraphSelectionError(
                f"Unknown graph profile {self.profile!r}. Valid profiles: "
                f"{', '.join(VALID_PROFILES)}."
            )

        enable = tuple(dict.fromkeys(self.enable))
        disable = tuple(dict.fromkeys(self.disable))
        unknown = [key for key in (*enable, *disable) if key not in graph_by_key]
        if unknown:
            unknown_list = ", ".join(repr(key) for key in dict.fromkeys(unknown))
            raise GraphSelectionError(
                f"Unknown graph key(s): {unknown_list}. Valid graph keys: "
                f"{', '.join(valid_keys)}."
            )

        conflicts = sorted(set(enable) & set(disable))
        if conflicts:
            conflict_list = ", ".join(conflicts)
            raise GraphSelectionError(
                f"Graph key(s) present in both enable and disable: {conflict_list}."
            )

        resolved_profile = selection_profile(self.profile)
        selected_keys = {
            graph.key for graph in ordered_graphs if resolved_profile in graph.profiles
        }
        selected_keys.update(enable)
        selected_keys.difference_update(disable)
        if not selected_keys:
            raise GraphSelectionError("Graph selection is empty; nothing to render.")

        return tuple(graph for graph in ordered_graphs if graph.key in selected_keys)

