from pydantic import BaseModel, Field
from ..base import BaseStrategy
from ..registry import register

class Params(BaseModel):
    quantity: int = Field(gt=0)
    limit_price: float = Field(gt=0)

class LmtBuy(BaseStrategy):
    id = "lmt_buy"
    name = "Limit Buy"
    Params = Params

    @classmethod
    def to_order(cls, *, symbol: str, params: dict) -> dict:
        p = cls.Params(**params)
        return {
            "symbol": symbol,
            "side": "BUY",
            "order_type": "LMT",
            "quantity": p.quantity,
            "limit_price": p.limit_price,
        }

register(LmtBuy)
