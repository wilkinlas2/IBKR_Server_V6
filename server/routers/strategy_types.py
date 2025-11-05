from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from secrets import token_hex

from server.modules.strategy_types import list_ids, get_schema, build_order
from server.modules.order_transmitting.service import enqueue_order
from server.modules.order_transmitting.adapters.ibkr.adapter import ADAPTER
from server.modules.data.store import RESULTS

router = APIRouter(prefix="/strategy-types", tags=["strategy-types"])


# -------- models
class RunRequest(BaseModel):
    symbol: str
    strategy_id: str
    params: dict = {}


# -------- endpoints
@router.get("")
def strategy_list():
    return {"strategies": list_ids()}

@router.get("/{strategy_id}/schema")
def strategy_schema(strategy_id: str):
    try:
        return get_schema(strategy_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown strategy")

@router.post("/run")
def strategy_run(req: RunRequest):
    try:
        spec = build_order(req.strategy_id, req.symbol, req.params)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown strategy")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    typ = spec.get("type")

    if typ == "single":
        order = spec["order"]
        # gebruikt onze bestaande transmit-queue + results workflow
        ok, payload = enqueue_order(order)
        if not ok:
            raise HTTPException(status_code=400, detail=str(payload))
        return {"mode": "single", **payload}

    elif typ == "bracket":
        base = spec["base_order"]
        tp = float(spec["target_price"]); sp = float(spec["stop_price"])

        parent_id = token_hex(6); target_id = token_hex(6); stop_id = token_hex(6)
        RESULTS[parent_id] = {"status": "accepted", "adapter": "ibkr"}
        RESULTS[target_id] = {"status": "accepted", "adapter": "ibkr"}
        RESULTS[stop_id]   = {"status": "accepted", "adapter": "ibkr"}

        ok, payload = ADAPTER.place_bracket(
            base_order=base,
            target_price=tp,
            stop_price=sp,
            internal_ids={"parent": parent_id, "target": target_id, "stop": stop_id},
        )
        if not ok:
            RESULTS[parent_id] = RESULTS[target_id] = RESULTS[stop_id] = {
                "status": "error", "adapter": "ibkr", "error": payload.get("error")
            }
            raise HTTPException(status_code=400, detail=str(payload.get("error", "bracket failed")))
        return {"mode": "bracket", "parent_order_id": parent_id,
                "target_order_id": target_id, "stop_order_id": stop_id,
                "ibkr": payload}

    else:
        raise HTTPException(status_code=400, detail=f"unsupported spec type: {typ}")
