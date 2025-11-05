from pydantic import BaseModel, Field
from ..base import BaseStrategy
from ..registry import register

class Params(BaseModel):
    quantity: int = Field(gt=0, description="Number of shares/contracts")

class MktBuy(BaseStrategy):
    id = "mkt_buy"
    name = "Market Buy"
    Params = Params

register(MktBuy)
