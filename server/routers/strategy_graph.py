from __future__ import annotations
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Body

from server.modules.strategy_graph.models import StrategyGraph
from server.modules.strategy_graph.store import upsert_graph, list_graphs, get_graph, delete_graph
from server.modules.strategy_graph.executor import run_graph

router = APIRouter(prefix="/strategy-graph", tags=["strategy-graph"])

@router.post("")
def create_or_upsert(graph: Dict[str, Any] = Body(...)):
    # graph: {name, description, root={...}, optional id}
    try:
        if "name" not in graph:
            raise HTTPException(status_code=400, detail="name is required")
        if "root" not in graph:
            raise HTTPException(status_code=400, detail="root is required")
        return upsert_graph(graph)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("")
def list_all():
    return list_graphs()

@router.get("/{graph_id}")
def fetch(graph_id: str):
    g = get_graph(graph_id)
    if not g:
        raise HTTPException(status_code=404, detail="not found")
    return g

@router.delete("/{graph_id}")
def remove(graph_id: str):
    ok = delete_graph(graph_id)
    if not ok:
        raise HTTPException(status_code=404, detail="not found")
    return {"deleted": True, "id": graph_id}

@router.post("/{graph_id}/run")
def run(graph_id: str, symbol: str = Body(..., embed=True)):
    g = get_graph(graph_id)
    if not g:
        raise HTTPException(status_code=404, detail="not found")
    try:
        sg = StrategyGraph(id=g["id"], root=g["root"])
        return run_graph(sg, symbol=symbol)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"{e.__class__.__name__}: {e}")
