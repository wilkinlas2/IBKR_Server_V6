from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from server.modules.order_processing.service import build_from_strategy
from server.modules.order_transmitting.service import enqueue_order

router = APIRouter(prefix="/system-panel", tags=["system_panel"])

class PlaceOrderIn(BaseModel):
    symbol: str = Field(..., examples=["AAPL"])
    strategy_id: str = Field(..., examples=["mkt_buy", "lmt_buy"])
    params: dict = Field(default_factory=dict)

@router.post("/place-order")
def place_order(req: PlaceOrderIn):
    ok, msg, order = build_from_strategy(req.symbol, req.strategy_id, req.params)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    order_id = enqueue_order(order)
    return {"status": "accepted", "order_id": order_id, "order": order}
