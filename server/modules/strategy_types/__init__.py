from __future__ import annotations
from typing import Dict, Callable, Any

# elke strategy module exposeert:
#   ID: str
#   SCHEMA: dict (verwachte params)
#   def build(symbol: str, params: dict) -> dict

from . import mkt_buy, mkt_sell, lmt_buy, bracket_buy, bracket_sell

REGISTRY: Dict[str, Any] = {
    mkt_buy.ID: mkt_buy,
    mkt_sell.ID: mkt_sell,
    lmt_buy.ID: lmt_buy,
    bracket_buy.ID: bracket_buy,
    bracket_sell.ID: bracket_sell,
}

def list_ids():
    return list(REGISTRY.keys())

def get_schema(strategy_id: str) -> dict:
    mod = REGISTRY.get(strategy_id)
    if not mod:
        raise KeyError(strategy_id)
    return mod.SCHEMA

def build_order(strategy_id: str, symbol: str, params: dict) -> dict:
    mod = REGISTRY.get(strategy_id)
    if not mod:
        raise KeyError(strategy_id)
    return mod.build(symbol, params or {})
