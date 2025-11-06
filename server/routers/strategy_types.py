from __future__ import annotations
from typing import Any, Tuple
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


# -------- helpers
def http400(e: Exception):
    raise HTTPException(status_code=400, detail=f"{e.__class__.__name__}: {e}")

def _normalize_enqueue_result(ret: Any) -> Tuple[bool, dict]:
    """
    enqueue_order() kan in projecten verschillende signatures hebben.
    - (ok, payload)
    - (ok, payload, extra...)
    - payload (dict)
    Deze helper normaliseert naar (ok, payload_dict).
    """
    if isinstance(ret, tuple):
        if len(ret) >= 2:
            ok, payload = ret[0], ret[1]
            if not isinstance(payload, dict):
                payload = {"data": payload}
            return bool(ok), payload
        elif len(ret) == 1:
            only = ret[0]
            if isinstance(only, dict):
                return True, only
            return True, {"data": only}
        else:
            return False, {"error": "empty tuple from enqueue_order"}
    # dict → beschouw als success payload
    if isinstance(ret, dict):
        return True, ret
    # fallback
    return True, {"data": ret}


# -------- endpoints
@router.get("")
def strategy_list():
    try:
        return {"strategies": list_ids()}
    except Exception as e:
        http400(e)


@router.get("/{strategy_id}/schema")
def strategy_schema(strategy_id: str):
    try:
        return get_schema(strategy_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown strategy")
    except Exception as e:
        http400(e)


@router.post("/run/spec")
def strategy_run_spec(req: RunRequest):
    """Dry-run: toon de spec die de strategy bouwt (geen plaatsing)."""
    try:
        spec = build_order(req.strategy_id, req.symbol, req.params)
        return {"spec": spec}
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown strategy")
    except Exception as e:
        http400(e)


@router.post("/run")
def strategy_run(req: RunRequest):
    """
    Run een strategy:
      - type == 'single'  -> enqueue_order(...)
      - type == 'bracket' -> ADAPTER.place_bracket(...)
    """
    try:
        spec = build_order(req.strategy_id, req.symbol, req.params)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown strategy")
    except Exception as e:
        http400(e)

    typ = spec.get("type")

    # ----- SINGLE -----
    if typ == "single":
        try:
            order = spec["order"]
            ok, payload = _normalize_enqueue_result(enqueue_order(order))
            if not ok:
                raise RuntimeError(payload)
            return {"mode": "single", **payload}
        except Exception as e:
            http400(e)

    # ----- BRACKET -----
    if typ == "bracket":
        try:
            base = spec["base_order"]
            tp = float(spec["target_price"])
            sp = float(spec["stop_price"])

            # interne ids voor status tracking
            parent_id = token_hex(6)
            target_id = token_hex(6)
            stop_id   = token_hex(6)
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
                raise RuntimeError(payload.get("error", "bracket failed"))
            ib_ids = payload.get("ibkr_order_ids", {}) or payload.get("ibkr_ids", {}) or {}

            return {
                "mode": "bracket",
                "parent_order_id": parent_id,
                "target_order_id": target_id,
                "stop_order_id":   stop_id,
                "ibkr_order_ids":  ib_ids,
            }
        except Exception as e:
            http400(e)

    # ----- unsupported -----
    raise HTTPException(status_code=400, detail=f"unsupported spec type: {typ}")
