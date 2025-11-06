from __future__ import annotations
from typing import Any, Dict, Tuple
from secrets import token_hex

from .models import StrategyGraph, SingleOrderNode, BracketExitNode, SequenceNode, Node
from server.modules.order_transmitting.service import enqueue_order
from server.modules.order_transmitting.adapters.ibkr.adapter import ADAPTER
from server.modules.data.store import RESULTS


def _normalize_enqueue_result(ret: Any) -> Tuple[bool, dict]:
    """
    Maak van verschillende mogelijke return-vormen van enqueue_order()
    een uniforme (ok: bool, payload: dict).
    Ondersteunt:
      - (ok, payload)
      - (ok, payload, extra...)
      - payload (dict)
      - anders: success met {"data": ret}
    """
    if isinstance(ret, tuple):
        if len(ret) >= 2:
            ok, payload = ret[0], ret[1]
            if not isinstance(payload, dict):
                payload = {"data": payload}
            return bool(ok), payload
        elif len(ret) == 1:
            only = ret[0]
            if isinstance(only, dict):
                return True, only
            return True, {"data": only}
        else:
            return False, {"error": "empty tuple from enqueue_order"}
    if isinstance(ret, dict):
        return True, ret
    return True, {"data": ret}


def run_graph(graph: StrategyGraph, symbol: str) -> Dict[str, Any]:
    """
    Execute de graph top-down. MVP: Sequence = kinderen na elkaar.
    """
    ctx: Dict[str, Any] = {"symbol": symbol, "results": {}}

    def _run(node: Node):
        if isinstance(node, SingleOrderNode):
            res = _run_single_order(node, ctx["symbol"])
            ctx["results"][node.id] = res
            return res

        if isinstance(node, BracketExitNode):
            res = _run_bracket(node, ctx["symbol"])
            ctx["results"][node.id] = res
            return res

        if isinstance(node, SequenceNode):
            seq_results = []
            for child in node.children:
                r = _run(child)
                seq_results.append(r)
            ctx["results"][node.id] = {"sequence": seq_results}
            return seq_results

        raise ValueError(f"Unsupported node type: {node}")

    _run(graph.root)
    return ctx["results"]


def _run_single_order(node: SingleOrderNode, symbol: str) -> Dict[str, Any]:
    order: Dict[str, Any] = {
        "symbol": symbol,
        "side": node.side,
        "order_type": node.order_type,
        "quantity": node.quantity,
        "tif": node.tif,
        "exchange": "SMART",
    }
    if node.order_type == "LMT":
        order["limit_price"] = float(node.limit_price)  # type: ignore

    ok, payload = _normalize_enqueue_result(enqueue_order(order))
    if not ok:
        return {"ok": False, "error": str(payload)}
    return {"ok": True, **payload}


def _run_bracket(node: BracketExitNode, symbol: str) -> Dict[str, Any]:
    base_order = {
        "symbol": symbol,
        "side": node.side,
        "quantity": node.quantity,
        "tif": node.tif,
        "exchange": "SMART",
    }

    parent_id = token_hex(6)
    target_id = token_hex(6)
    stop_id   = token_hex(6)
    RESULTS[parent_id] = {"status": "accepted", "adapter": "ibkr"}
    RESULTS[target_id] = {"status": "accepted", "adapter": "ibkr"}
    RESULTS[stop_id]   = {"status": "accepted", "adapter": "ibkr"}

    ok, payload = ADAPTER.place_bracket(
        base_order=base_order,
        target_price=float(node.target_price),
        stop_price=float(node.stop_price),
        internal_ids={"parent": parent_id, "target": target_id, "stop": stop_id},
    )
    if not ok:
        return {"ok": False, "error": str(payload.get("error", "bracket failed"))}

    ib_ids = payload.get("ibkr_order_ids", {}) or payload.get("ibkr_ids", {}) or {}
    return {
        "ok": True,
        "parent_order_id": parent_id,
        "target_order_id": target_id,
        "stop_order_id":   stop_id,
        "ibkr_order_ids":  ib_ids,
    }
