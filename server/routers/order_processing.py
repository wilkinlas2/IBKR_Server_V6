from fastapi import APIRouter
from pydantic import BaseModel
from server.modules.order_processing.service import validate_order, enrich_order

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
