from __future__ import annotations
from typing import Dict, Type
from .base import BaseStrategy

_registry: Dict[str, Type[BaseStrategy]] = {}

def register(strategy_cls: Type[BaseStrategy]) -> None:
    _registry[strategy_cls.id] = strategy_cls

def all_types() -> list[dict]:
    return [{"id": c.id, "name": c.name} for c in _registry.values()]

def get(id_: str) -> Type[BaseStrategy] | None:
    return _registry.get(id_)

# import strategies to populate the registry
def _bootstrap():
    # side-effect imports
    from .strategies import mkt_buy, lmt_buy  # noqa: F401

_bootstrap()
