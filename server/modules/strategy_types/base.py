from __future__ import annotations
from typing import Any, Tuple
from pydantic import BaseModel

class BaseStrategy:
    """Minimal strategy interface: validate + to_order."""
    id: str = "base"
    name: str = "Base Strategy"
    Params: type[BaseModel] = BaseModel  # override in child

    @classmethod
    def schema(cls) -> dict:
        return cls.Params.model_json_schema()

    @classmethod
    def validate_params(cls, data: dict) -> Tuple[bool, str]:
        try:
            cls.Params(**data)
            return True, "ok"
        except Exception as e:
            return False, str(e)

    @classmethod
    def to_order(cls, *, symbol: str, params: dict) -> dict[str, Any]:
        """
        Produce a minimal order spec. Child classes MUST override.
        Return example:
          { "symbol": "AAPL", "side":"BUY", "order_type":"MKT", "quantity":1 }
        """
        raise NotImplementedError(f"{cls.__name__}.to_order not implemented")
