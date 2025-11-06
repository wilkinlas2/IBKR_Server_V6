"""
Exit Types service: registry + (optioneel) IB helpers, adapter-agnostisch.
- ensure_registered: registreert bracket in registry
- get_oca_detail: status via adapter.get_order_status(order_id) -> IB fallback -> RESULTS fallback
- cancel_oca: voorkeur adapter.cancel_bracket; fallback adapter.cancel(internal_id); laatste redmiddel via IB by id
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from importlib import import_module

from fastapi import HTTPException

from server.modules.exit_types.registry import (
    list_active_ocas as registry_list_active_ocas,
    register_bracket as registry_register_bracket,
    get_record as registry_get_record,
    Leg,
)
from server.modules.data.store import RESULTS

# ---- Adapter helpers ----
_cancel_bracket = None
_get_order_status_from_adapter = None
_ADAPTER_OBJ = None
try:
    _adapter_mod = import_module("server.modules.order_transmitting.adapters.ibkr.adapter")
    _cancel_bracket = getattr(_adapter_mod, "cancel_bracket", None)
    _get_order_status_from_adapter = getattr(_adapter_mod, "get_order_status", None)
    _ADAPTER_OBJ = getattr(_adapter_mod, "ADAPTER", None)
except Exception:
    _cancel_bracket = None
    _get_order_status_from_adapter = None
    _ADAPTER_OBJ = None

def _leg_get(leg: Any, field: str):
    if isinstance(leg, dict):
        return leg.get(field)
    return getattr(leg, field, None)

def list_active_ocas() -> List[str]:
    return registry_list_active_ocas()

def register_bracket(oca_group: str, symbol: str, legs: List[Leg]) -> None:
    registry_register_bracket(oca_group, symbol, legs)

def _roles_order() -> List[str]:
    return ["parent", "target", "stop"]

def ensure_registered(*, symbol: str, ibkr_order_ids: Dict[str, int], internal_ids: Dict[str, str]) -> str:
    if not symbol:
        raise ValueError("symbol is required")
    if not ibkr_order_ids or not all(k in ibkr_order_ids for k in _roles_order()):
        raise ValueError("ibkr_order_ids must include 'parent','target','stop'")
    # synthetische OCA op basis van parent id
    parent_id = int(ibkr_order_ids["parent"])
    oca_group = f"OCA-{symbol}-{parent_id}"
    legs: List[Leg] = []
    for role in _roles_order():
        legs.append(
            Leg(
                role=role,
                internal_id=internal_ids.get(role, ""),
                ib_order_id=int(ibkr_order_ids.get(role)),
                status=None,
            )
        )
    registry_register_bracket(oca_group, symbol, legs)
    return oca_group

def _status_from_results(iid: str) -> Optional[str]:
    if not iid:
        return None
    data = RESULTS.get(iid) or {}
    st = data.get("status")
    return str(st) if st else None

def get_oca_detail(oca_group: str) -> Optional[Dict[str, Any]]:
    rec = registry_get_record(oca_group)
    if not rec:
        return None

    enriched: List[Dict[str, Any]] = []
    for leg in rec["legs"]:
        ib_id = _leg_get(leg, "ib_order_id")
        iid = _leg_get(leg, "internal_id") or ""
        status: Optional[str] = None

        # 1) adapter helper (zelfde IB-verbinding)
        if ib_id is not None and callable(_get_order_status_from_adapter):
            try:
                status = _get_order_status_from_adapter(int(ib_id))
            except Exception:
                status = None

        # 2) RESULTS fallback (laatst bekende)
        if not status:
            rs = _status_from_results(iid)
            if rs:
                status = rs

        enriched.append({
            "role": _leg_get(leg, "role") or "leg",
            "internal_id": iid,
            "ib_order_id": ib_id,
            "status": (str(status).lower() if status else None),
        })

    return {"oca_group": rec["oca_group"], "symbol": rec.get("symbol"), "legs": enriched}

def _cancel_via_adapter_cancel(internal_ids: List[str]) -> Tuple[int, List[str]]:
    if _ADAPTER_OBJ is None or not hasattr(_ADAPTER_OBJ, "cancel"):
        return 0, ["adapter.cancel unavailable"]
    ok_count = 0
    errors: List[str] = []
    for iid in internal_ids:
        if not iid:
            continue
        try:
            res = _ADAPTER_OBJ.cancel(iid)  # {"ok": True/False, ...}
            if isinstance(res, dict) and bool(res.get("ok")):
                ok_count += 1
            else:
                errors.append(str(res))
        except Exception as exc:
            errors.append(str(exc))
    return ok_count, errors

def cancel_oca(oca_group: str) -> Optional[Dict[str, Any]]:
    rec = registry_get_record(oca_group)
    if not rec:
        return None

    ib_ids = [int(_leg_get(l, "ib_order_id")) for l in rec["legs"] if _leg_get(l, "ib_order_id") is not None]
    internal_ids = [_leg_get(l, "internal_id") or "" for l in rec["legs"]]

    # 1) Preferred: adapter.cancel_bracket([ib_ids]) binnen IB-thread
    if callable(_cancel_bracket) and ib_ids:
        try:
            _cancel_bracket(ib_ids)
            return {"oca_group": oca_group, "cancelled_count": len(ib_ids), "ib_order_ids": ib_ids, "method": "adapter.cancel_bracket"}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Cancel of OCA '{oca_group}' failed: {exc}")

    # 2) Fallback: adapter.cancel(internal_id) per leg
    ok_count, errors = _cancel_via_adapter_cancel(internal_ids)
    if ok_count > 0:
        return {"oca_group": oca_group, "cancelled_count": ok_count, "attempted_internal_ids": internal_ids, "errors": errors, "method": "adapter.cancel(internal_id)"}

    raise HTTPException(status_code=400, detail="Cancel not supported (no adapter helpers available or no orders to cancel).")
