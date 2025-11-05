from pydantic import BaseModel, Field
from ..base import BaseStrategy
from ..registry import register

class Params(BaseModel):
    quantity: int = Field(gt=0, description="Number of shares/contracts")

class MktBuy(BaseStrategy):
    id = "mkt_buy"
    name = "Market Buy"
    Params = Params

    @classmethod
    def to_order(cls, *, symbol: str, params: dict) -> dict:
        p = cls.Params(**params)
        return {
            "symbol": symbol,
            "side": "BUY",
            "order_type": "MKT",
            "quantity": p.quantity,
        }

register(MktBuy)
