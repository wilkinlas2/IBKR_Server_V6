from __future__ import annotations
from typing import Dict, Any, List
from secrets import token_hex

from server.modules.persistence.db import save_graph, load_graph, load_all_graphs

# In-memory registry (id -> graph dict)
_GRAPHS: Dict[str, Dict[str, Any]] = {}

def upsert_graph(graph: Dict[str, Any]) -> Dict[str, Any]:
    """
    graph = { name, description, root={...}, (optional id) }
    """
    gid = graph.get("id") or token_hex(6)
    graph["id"] = gid
    _GRAPHS[gid] = graph
    # persist
    save_graph(gid, graph.get("name") or gid, graph.get("description") or "", {
        "root": graph["root"]
    })
    return {"id": gid, **graph}

def get_graph(graph_id: str) -> Dict[str, Any] | None:
    # prefer memory; else load from DB and repopulate
    g = _GRAPHS.get(graph_id)
    if g:
        return g
    db = load_graph(graph_id)
    if db:
        _GRAPHS[graph_id] = db
    return db

def list_graphs() -> List[Dict[str, Any]]:
    if _GRAPHS:
        return list(_GRAPHS.values())
    db_all = load_all_graphs()
    for g in db_all:
        _GRAPHS[g["id"]] = g
    return db_all

def delete_graph(graph_id: str) -> bool:
    # soft delete: remove memory only. (DB cleanup out-of-scope now)
    return _GRAPHS.pop(graph_id, None) is not None
