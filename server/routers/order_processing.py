from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from server.modules.order_processing.service import (
    validate_order, enrich_order, build_from_strategy
)

router = APIRouter(prefix="/order-processing", tags=["order_processing"])

class RawOrder(BaseModel):
    symbol: str
    side: str
    quantity: int
    order_type: str = "MKT"
    limit_price: float | None = None

@router.post("/validate")
def validate(o: RawOrder):
    ok, msg = validate_order(o.dict())
    return {"valid": ok, "message": msg}

@router.post("/enrich")
def enrich(o: RawOrder):
    return enrich_order(o.dict())

class BuildIn(BaseModel):
    symbol: str
    strategy_id: str
    params: dict

@router.post("/build")
def build(body: BuildIn):
    ok, msg, order = build_from_strategy(body.symbol, body.strategy_id, body.params)
    if not ok:
        raise HTTPException(400, msg)
    return {"order": order}
