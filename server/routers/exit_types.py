from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, validator
from typing import Literal

from server.modules.exit_types.service import place_bracket_order

router = APIRouter(prefix="/exit-types", tags=["exit_types"])

Side = Literal["BUY", "SELL"]

class BracketRequest(BaseModel):
    symbol: str = Field(..., description="Ticker, bv. AAPL")
    side: Side = Field(..., description="'BUY' of 'SELL' voor de parent")
    quantity: int = Field(..., gt=0)
    target_price: float = Field(..., gt=0, description="Absolute target limit price")
    stop_price: float = Field(..., gt=0, description="Absolute stop trigger price")
    tif: str = Field("DAY", description="TIF, bv. DAY of GTC")
    exchange: str = Field("SMART")

    @validator("side")
    def _upper(cls, v):
        return v.upper()

@router.post("/bracket")
def create_bracket(req: BracketRequest):
    try:
        return place_bracket_order(
            symbol=req.symbol,
            side=req.side,
            quantity=req.quantity,
            target_price=req.target_price,
            stop_price=req.stop_price,
            tif=req.tif,
            exchange=req.exchange,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
