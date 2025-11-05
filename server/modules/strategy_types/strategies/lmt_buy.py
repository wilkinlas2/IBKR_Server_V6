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

register(LmtBuy)
