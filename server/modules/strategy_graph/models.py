from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

# --- Node definitions ---

@dataclass
class Node:
    id: str
    type: str

@dataclass
class SingleOrderNode(Node):
    type: str = field(default="single_order", init=False)
    side: str = "BUY"            # BUY|SELL
    order_type: str = "MKT"      # MKT|LMT
    quantity: int = 1
    tif: str = "DAY"
    limit_price: Optional[float] = None

@dataclass
class BracketExitNode(Node):
    type: str = field(default="bracket_exit", init=False)
    side: str = "SELL"           # tegenpositie op basis van entry
    quantity: int = 1
    target_price: float = 0.0
    stop_price: float = 0.0
    tif: str = "DAY"
    oco_only: bool = False       # als True: geen parent, alleen OCO legs

@dataclass
class WaitForFillNode(Node):
    type: str = field(default="wait_for_fill", init=False)
    waits_for_internal_id: str = ""
    timeout_sec: int = 300
    proceed_on_timeout: bool = False  # nieuw: bij timeout toch verder

@dataclass
class WaitForStatusNode(Node):
    type: str = field(default="wait_for_status", init=False)
    waits_for_internal_id: str = ""
    statuses: List[str] = field(default_factory=lambda: ["filled"])
    timeout_sec: int = 300
    proceed_on_timeout: bool = False

@dataclass
class SequenceNode(Node):
    type: str = field(default="sequence", init=False)
    children: List[Node] = field(default_factory=list)

@dataclass
class StrategyGraph:
    id: str
    root: Dict[str, Any]  # JSON-ish tree (we parse at runtime)

# --- Factory ---

def parse_node(d: Dict[str, Any]) -> Node:
    t = (d.get("type") or "").lower()
    nid = d.get("id") or ""
    if t == "single_order":
        return SingleOrderNode(
            id=nid,
            side=d.get("side", "BUY"),
            order_type=d.get("order_type", "MKT"),
            quantity=int(d.get("quantity", 1)),
            tif=d.get("tif", "DAY"),
            limit_price=(float(d["limit_price"]) if "limit_price" in d and d["limit_price"] is not None else None),
        )
    if t == "bracket_exit":
        return BracketExitNode(
            id=nid,
            side=d.get("side", "SELL"),
            quantity=int(d.get("quantity", 1)),
            target_price=float(d.get("target_price", 0)),
            stop_price=float(d.get("stop_price", 0)),
            tif=d.get("tif", "DAY"),
            oco_only=bool(d.get("oco_only", False)),
        )
    if t == "wait_for_fill":
        return WaitForFillNode(
            id=nid,
            waits_for_internal_id=str(d.get("waits_for_internal_id", "")),
            timeout_sec=int(d.get("timeout_sec", 300)),
            proceed_on_timeout=bool(d.get("proceed_on_timeout", False)),
        )
    if t == "wait_for_status":
        sts = d.get("statuses") or ["filled"]
        if not isinstance(sts, list):
            sts = [str(sts)]
        return WaitForStatusNode(
            id=nid,
            waits_for_internal_id=str(d.get("waits_for_internal_id", "")),
            statuses=[str(s).lower() for s in sts],
            timeout_sec=int(d.get("timeout_sec", 300)),
            proceed_on_timeout=bool(d.get("proceed_on_timeout", False)),
        )
    if t == "sequence":
        return SequenceNode(
            id=nid,
            children=[parse_node(c) for c in (d.get("children") or [])],
        )
    raise ValueError(f"Unknown node type: {t}")
