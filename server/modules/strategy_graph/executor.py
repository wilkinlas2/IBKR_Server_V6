from __future__ import annotations
import time
from typing import Any, Dict

from server.modules.strategy_graph.models import (
    StrategyGraph, parse_node,
    SequenceNode, SingleOrderNode, BracketExitNode,
    WaitForFillNode, WaitForStatusNode
)
from server.modules.order_transmitting.service import enqueue_order
from server.modules.order_transmitting.adapters.ibkr.adapter import ADAPTER
from server.modules.data.store import RESULTS

def _status_of(internal_id: str) -> str | None:
    rec = RESULTS.get(internal_id) or {}
    s = (rec.get("status") or "").lower() or None
    return s

def _wait_until(predicate, timeout_sec: int) -> bool:
    t0 = time.time()
    while True:
        if predicate():
            return True
        if timeout_sec is not None and timeout_sec >= 0 and (time.time() - t0) >= timeout_sec:
            return False
        time.sleep(0.25)

def _run_single_order(node: SingleOrderNode, symbol: str) -> Dict[str, Any]:
    order: Dict[str, Any] = {
        "symbol": symbol,
        "side": node.side.upper(),
        "order_type": node.order_type.upper(),
        "quantity": int(node.quantity),
        "tif": node.tif,
    }
    if node.order_type.upper() == "LMT":
        if node.limit_price is None or float(node.limit_price) <= 0:
            raise ValueError("limit_price required for LMT")
        order["limit_price"] = float(node.limit_price)
    ok, payload = enqueue_order(order)
    if not ok:
        raise RuntimeError(payload)
    # normalize: enqueue may return dict or tuple etc.
    if isinstance(payload, dict):
        return {"mode": "single", **payload}
    return {"mode": "single", "data": payload}

def _run_bracket_exit(node: BracketExitNode, symbol: str) -> Dict[str, Any]:
    # build base order for SELL parent if oco_only=False
    if not node.oco_only:
        base = {
            "symbol": symbol,
            "side": node.side.upper(),
            "order_type": "MKT",
            "quantity": int(node.quantity),
            "tif": node.tif,
        }
    else:
        base = {
            "symbol": symbol,
            "side": node.side.upper(),
            "order_type": "NONE",  # adapter interprets oco_only
            "quantity": int(node.quantity),
            "tif": node.tif,
        }

    # track internally
    import secrets
    parent_id = secrets.token_hex(6)
    target_id = secrets.token_hex(6)
    stop_id   = secrets.token_hex(6)
    RESULTS[parent_id] = {"status": "accepted", "adapter": "ibkr"}
    RESULTS[target_id] = {"status": "accepted", "adapter": "ibkr"}
    RESULTS[stop_id]   = {"status": "accepted", "adapter": "ibkr"}

    ok, payload = ADAPTER.place_bracket(
        base_order=base,
        target_price=float(node.target_price),
        stop_price=float(node.stop_price),
        internal_ids={"parent": parent_id, "target": target_id, "stop": stop_id},
    )
    if not ok:
        raise RuntimeError(payload.get("error", "bracket failed"))

    ib_ids = payload.get("ibkr_order_ids", {}) or payload.get("ibkr_ids", {}) or {}
    resp = {
        "mode": "bracket",
        "parent_order_id": parent_id,
        "target_order_id": target_id,
        "stop_order_id":   stop_id,
        "ibkr_order_ids":  ib_ids,
        "oca_group":       payload.get("oca_group"),  # in case adapter/service set it
    }
    return resp

def _run_wait_for_fill(node: WaitForFillNode) -> Dict[str, Any]:
    iid = node.waits_for_internal_id
    if not iid:
        raise ValueError("wait_for_fill: waits_for_internal_id required")
    ok = _wait_until(lambda: (_status_of(iid) == "filled"), node.timeout_sec)
    if not ok and not node.proceed_on_timeout:
        raise TimeoutError(f"wait_for_fill timeout after {node.timeout_sec}s for {iid}")
    return {"mode": "wait_for_fill", "internal_id": iid, "timeout": (not ok), "proceeded": (not ok and node.proceed_on_timeout)}

def _run_wait_for_status(node: WaitForStatusNode) -> Dict[str, Any]:
    iid = node.waits_for_internal_id
    targets = [s.lower() for s in (node.statuses or ["filled"])]
    ok = _wait_until(lambda: (_status_of(iid) in targets), node.timeout_sec)
    if not ok and not node.proceed_on_timeout:
        raise TimeoutError(f"wait_for_status timeout after {node.timeout_sec}s for {iid} (wanted {targets})")
    return {
        "mode": "wait_for_status",
        "internal_id": iid,
        "matches": (targets if ok else []),
        "timeout": (not ok),
        "proceeded": (not ok and node.proceed_on_timeout),
        "status": _status_of(iid),
    }

def _run_sequence(node: SequenceNode, symbol: str) -> Dict[str, Any]:
    out = []
    for child in node.children:
        if isinstance(child, dict):
            ch = parse_node(child)
        else:
            ch = child
        if isinstance(ch, SingleOrderNode):
            out.append(_run_single_order(ch, symbol))
        elif isinstance(ch, BracketExitNode):
            out.append(_run_bracket_exit(ch, symbol))
        elif isinstance(ch, WaitForFillNode):
            out.append(_run_wait_for_fill(ch))
        elif isinstance(ch, WaitForStatusNode):
            out.append(_run_wait_for_status(ch))
        elif isinstance(ch, SequenceNode):
            out.append(_run_sequence(ch, symbol))
        else:
            raise ValueError(f"Unsupported child node: {type(ch).__name__}")
    return {"mode": "sequence", "results": out}

def run_graph(g: StrategyGraph, symbol: str) -> Dict[str, Any]:
    root = parse_node(g.root)
    if not isinstance(root, SequenceNode):
        raise ValueError("Root must be sequence")
    return _run_sequence(root, symbol)
