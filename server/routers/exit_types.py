from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, validator
from secrets import token_hex

from server.modules.data.store import RESULTS
from server.modules.exit_types.service import remember_oca, list_oca
from server.modules.order_transmitting.adapters.ibkr.adapter import ADAPTER

router = APIRouter(prefix="/exit-types", tags=["exit-types"])


# ---------- Models ----------
class BracketRequest(BaseModel):
    symbol: str
    side: str = Field(..., description="BUY of SELL (parent richting)")
    quantity: int = Field(..., gt=0)
    target_price: float = Field(..., gt=0)
    stop_price: float = Field(..., gt=0)
    tif: str = "DAY"
    exchange: str = "SMART"

    @validator("side")
    def _v_side(cls, v: str) -> str:
        v = v.upper()
        if v not in ("BUY", "SELL"):
            raise ValueError("side must be BUY or SELL")
        return v


class BracketResponse(BaseModel):
    parent_order_id: str
    target_order_id: str
    stop_order_id: str
    ibkr_ids: dict
    oca_group: str


# ---------- Endpoints ----------
@router.post("/bracket", response_model=BracketResponse)
def place_bracket(req: BracketRequest):
    """
    Plaats parent (MKT) + target (LMT) + stop (STP) als 1 OCA-bracket via IBKR.
    Slaat de OCA-group op zodat we die later kunnen opvragen.
    """
    # 1) interne result-ids genereren
    parent_id = token_hex(6)
    target_id = token_hex(6)
    stop_id   = token_hex(6)

    # init "accepted" snapshots in RESULTS (zodat de UI iets heeft om te tonen)
    RESULTS[parent_id] = {"status": "accepted", "adapter": "ibkr"}
    RESULTS[target_id] = {"status": "accepted", "adapter": "ibkr"}
    RESULTS[stop_id]   = {"status": "accepted", "adapter": "ibkr"}

    # 2) adapter call
    base_order = {
        "symbol": req.symbol,
        "side": req.side,
        "quantity": req.quantity,
        "tif": req.tif,
        "exchange": req.exchange,
    }
    ok, payload = ADAPTER.place_bracket(
        base_order=base_order,
        target_price=req.target_price,
        stop_price=req.stop_price,
        internal_ids={"parent": parent_id, "target": target_id, "stop": stop_id},
    )
    if not ok:
        # zet results op error
        RESULTS[parent_id] = {"status": "error", "adapter": "ibkr", "error": payload.get("error")}
        RESULTS[target_id] = {"status": "error", "adapter": "ibkr", "error": payload.get("error")}
        RESULTS[stop_id]   = {"status": "error", "adapter": "ibkr", "error": payload.get("error")}
        raise HTTPException(status_code=400, detail=str(payload.get("error", "bracket failed")))

    ibkr_ids = payload.get("ibkr_order_ids", {})
    parent_ib = ibkr_ids.get("parent")
    # onze OCA group (zoals TWS toont) = "OCA-{parent_ib_order_id}"
    oca_group = f"OCA-{parent_ib}" if parent_ib is not None else "OCA-?"

    # 3) OCA onthouden in registry
    remember_oca(
        oca_group=oca_group,
        symbol=req.symbol,
        quantity=req.quantity,
        side=req.side,
        tif=req.tif,
        legs={
            "parent": dict_to_leg("parent", parent_id, ibkr_ids.get("parent"), req.side, "MKT", None),
            "target": dict_to_leg("target", target_id, ibkr_ids.get("target"), opposite(req.side), "LMT", req.target_price),
            "stop":   dict_to_leg("stop",   stop_id,   ibkr_ids.get("stop"),   opposite(req.side), "STP", req.stop_price),
        },
    )

    return BracketResponse(
        parent_order_id=parent_id,
        target_order_id=target_id,
        stop_order_id=stop_id,
        ibkr_ids=ibkr_ids,
        oca_group=oca_group,
    )


@router.get("/list-active")
def list_active():
    """Geef alle OCA groepen terug die wij hebben opgeslagen."""
    return list_oca()


# ---------- helpers ----------
def opposite(side: str) -> str:
    return "SELL" if side.upper() == "BUY" else "BUY"


def dict_to_leg(name: str, internal_id: str, ib_order_id, side: str, order_type: str, price):
    return __import__("server.modules.exit_types.service", fromlist=["OcaLeg"]).OcaLeg(
        name=name,
        internal_id=internal_id,
        ib_order_id=int(ib_order_id) if ib_order_id is not None else None,
        side=side,
        order_type=order_type,
        price=float(price) if price is not None else None,
    )
