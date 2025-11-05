from typing import Tuple
from .registry import all_types, get

def _resolve(strategy_id: str) -> str | None:
    """Allow numeric aliases: '1' -> first id, etc."""
    if strategy_id.isdigit():
        items = all_types()
        idx = int(strategy_id) - 1
        if 0 <= idx < len(items):
            return items[idx]["id"]
        return None
    return strategy_id

def list_types() -> list[dict]:
    # voeg index toe voor duidelijkheid
    return [
        {"index": i + 1, "id": item["id"], "name": item["name"]}
        for i, item in enumerate(all_types())
    ]

def get_schema(strategy_id: str) -> dict:
    sid = _resolve(strategy_id)
    if not sid:
        return {"error": f"strategy '{strategy_id}' not found"}
    cls = get(sid)
    if not cls:
        return {"error": f"strategy '{strategy_id}' not found"}
    return {"id": cls.id, "name": cls.name, "schema": cls.schema()}

def validate(strategy_id: str, params: dict) -> Tuple[bool, str]:
    sid = _resolve(strategy_id)
    if not sid:
        return False, f"strategy '{strategy_id}' not found"
    cls = get(sid)
    if not cls:
        return False, f"strategy '{strategy_id}' not found"
    return cls.validate_params(params)
