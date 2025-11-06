from __future__ import annotations
from typing import Dict, Optional, List
from .models import StrategyGraph

GRAPH_STORE: Dict[str, StrategyGraph] = {}


def save_graph(g: StrategyGraph) -> StrategyGraph:
    GRAPH_STORE[g.id] = g
    return g


def get_graph(graph_id: str) -> Optional[StrategyGraph]:
    return GRAPH_STORE.get(graph_id)


def list_graphs() -> List[StrategyGraph]:
    return list(GRAPH_STORE.values())


def delete_graph(graph_id: str) -> bool:
    return GRAPH_STORE.pop(graph_id, None) is not None
