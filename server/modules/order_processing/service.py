from __future__ import annotations
from typing import Tuple
from server.modules.strategy_types.service import validate as validate_strategy, _resolve
from server.modules.strategy_types.registry import get as get_strategy

def validate_order(o: dict) -> Tuple[bool, str]:
    # (basisvalidatie blijft voor oudere paden bruikbaar)
    if not o.get("symbol"):
        return False, "symbol required"
    if o.get("quantity", 0) <= 0 and not o.get("params"):
        return False, "quantity > 0 required (or use strategy params)"
    if o.get("order_type") == "LMT" and not o.get("limit_price"):
        return False, "limit_price required for LMT"
    return True, "ok"

def enrich_order(o: dict) -> dict:
    o = {**o}
    o.setdefault("tif", "DAY")
    o.setdefault("exchange", "SMART")
    return {"order": o}

def build_from_strategy(symbol: str, strategy_id: str, params: dict) -> Tuple[bool, str, dict]:
    """Validate via strategy and map to final order spec using strategy.to_order()."""
    sid = _resolve(strategy_id) or strategy_id
    ok, msg = validate_strategy(sid, params)
    if not ok:
        return False, msg, {}
    cls = get_strategy(sid)
    if not cls:
        return False, f"strategy '{strategy_id}' not found", {}
    order = cls.to_order(symbol=symbol, params=params)
    # add generic defaults
    order.setdefault("tif", "DAY")
    order.setdefault("exchange", "SMART")
    return True, "ok", order
