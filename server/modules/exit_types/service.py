import uuid
from typing import Dict, Any

from server.modules.data.store import RESULTS
from server.modules.order_transmitting.config import load_adapter

def place_bracket_order(
    symbol: str,
    side: str,
    quantity: int,
    target_price: float,
    stop_price: float,
    tif: str = "DAY",
    exchange: str = "SMART",
) -> Dict[str, Any]:
    """
    Stuurt parent + (target, stop) als OCO-bracket naar de actieve adapter (IBKR).
    We bewaren 3 interne order_id's en laten de adapter live status updates pushen.
    """
    adapter_name, adapter = load_adapter()
    if adapter_name != "ibkr":
        raise RuntimeError("Bracket exits vereisen IBKR adapter")

    # interne id's (parent + 2 kinderen)
    parent_id = uuid.uuid4().hex[:12]
    target_id = uuid.uuid4().hex[:12]
    stop_id   = uuid.uuid4().hex[:12]

    # basis orderdata
    base = {
        "symbol": symbol,
        "side": side.upper(),
        "quantity": int(quantity),
        "tif": tif,
        "exchange": exchange,
    }

    # init in RESULTS (visueel/trace)
    RESULTS[parent_id] = {"status": "queued", "detail": {**base, "order_type": "MKT"}, "adapter": adapter_name}
    RESULTS[target_id] = {"status": "queued", "detail": {**base, "order_type": "LMT", "limit_price": target_price}, "adapter": adapter_name}
    RESULTS[stop_id]   = {"status": "queued", "detail": {**base, "order_type": "STP", "stop_price":  stop_price},  "adapter": adapter_name}

    ok, payload = adapter.place_bracket(
        base_order=base,
        target_price=float(target_price),
        stop_price=float(stop_price),
        internal_ids={"parent": parent_id, "target": target_id, "stop": stop_id},
    )

    if not ok:
        err = payload.get("error", "unknown error")
        RESULTS[parent_id]["status"] = "error"; RESULTS[parent_id]["error"] = err
        RESULTS[target_id]["status"] = "error"; RESULTS[target_id]["error"] = err
        RESULTS[stop_id]["status"]   = "error"; RESULTS[stop_id]["error"]   = err
        raise RuntimeError(err)

    return {
        "parent_order_id": parent_id,
        "target_order_id": target_id,
        "stop_order_id": stop_id,
        "ibkr_ids": payload.get("ibkr_order_ids"),
    }
