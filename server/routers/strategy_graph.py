from __future__ import annotations
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from secrets import token_hex

from server.modules.strategy_graph.models import StrategyGraph
from server.modules.strategy_graph.store  import save_graph, get_graph, list_graphs, delete_graph
from server.modules.strategy_graph.executor import run_graph

router = APIRouter(prefix="/strategy-graph", tags=["strategy-graph"])


class UpsertGraphRequest(BaseModel):
    id: str | None = None
    name: str
    description: str | None = None
    root: Dict[str, Any]


class RunGraphRequest(BaseModel):
    symbol: str


@router.get("")
def sg_list():
    return {"graphs": [g.dict() for g in list_graphs()]}


@router.get("/{graph_id}")
def sg_get(graph_id: str):
    g = get_graph(graph_id)
    if not g:
        raise HTTPException(status_code=404, detail="unknown graph")
    return g


@router.delete("/{graph_id}")
def sg_delete(graph_id: str):
    ok = delete_graph(graph_id)
    return {"deleted": ok}


@router.post("")
def sg_upsert(req: UpsertGraphRequest):
    graph_id = req.id or token_hex(6)
    try:
        g = StrategyGraph(id=graph_id, name=req.name, description=req.description, root=req.root)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"{e.__class__.__name__}: {e}")
    save_graph(g)
    return {"id": graph_id, "graph": g}


@router.post("/{graph_id}/run")
def sg_run(graph_id: str, req: RunGraphRequest):
    g = get_graph(graph_id)
    if not g:
        raise HTTPException(status_code=404, detail="unknown graph")
    try:
        results = run_graph(g, symbol=req.symbol)
        return {"graph_id": graph_id, "results": results}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"{e.__class__.__name__}: {e}")
