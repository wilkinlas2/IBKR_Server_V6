from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Literal, Optional
from server.modules.order_processing.service import validate_order
from server.modules.order_transmitting.service import enqueue_order

router = APIRouter(prefix="/system-panel", tags=["system_panel"])

class OrderRequest(BaseModel):
    symbol: str = Field(..., examples=["AAPL"])
    side: Literal["BUY","SELL"]
    quantity: int = Field(..., gt=0)
    order_type: Literal["MKT","LMT"] = "MKT"
    limit_price: Optional[float] = None
    strategy: Optional[str] = None

@router.post("/place-order")
def place_order(req: OrderRequest):
    ok, msg = validate_order(req.dict())
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    order_id = enqueue_order(req.dict())
    return {"status":"accepted","order_id":order_id}
