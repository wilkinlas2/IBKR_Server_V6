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

def _bootstrap() -> None:
    """Automatically import every module in .strategies package."""
    import pkgutil
    import importlib
    from . import strategies
    for m in pkgutil.iter_modules(strategies.__path__):
        importlib.import_module(f"{strategies.__name__}.{m.name}")

_bootstrap()
