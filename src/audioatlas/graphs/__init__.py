"""Graph registry for AudioAtlas report plots."""

from audioatlas.graphs.registry import GraphSpec, all_graphs, graph_by_filename, graph_by_key
from audioatlas.graphs.selection import GraphSelection, GraphSelectionError

__all__ = [
    "GraphSelection",
    "GraphSelectionError",
    "GraphSpec",
    "all_graphs",
    "graph_by_filename",
    "graph_by_key",
]
