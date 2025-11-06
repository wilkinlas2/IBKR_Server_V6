from fastapi import HTTPException
from server.modules.data.store import RESULTS
from server.modules.exit_types import registry

def _status_from_results(internal_id: str) -> str | None:
    d = RESULTS.get(internal_id) or {}
    s = (d.get("status") or "").strip()
    return s or None

def get_oca_detail(oca_group: str, refresh: bool = False) -> dict:
    rec = registry.get_record(oca_group)
    if not rec:
        # Geen snapshot bekend → echte unknown
        raise HTTPException(status_code=404, detail="Unknown OCA group")

    if not refresh:
        return {
            "oca_group": oca_group,
            "symbol": rec.get("symbol"),
            "legs": rec.get("legs", []),
        }

    # refresh: vul statussen vanuit RESULTS
    legs = []
    for leg in rec.get("legs", []):
        st = _status_from_results(leg.get("internal_id", ""))
        new_leg = dict(leg)
        if st:
            new_leg["status"] = st
        legs.append(new_leg)

    rec_out = {"oca_group": oca_group, "symbol": rec.get("symbol"), "legs": legs}
    # snapshot bijwerken (maar zelfs zonder blijft detail werken)
    registry.upsert_record(oca_group, {**rec, "legs": legs})
    return rec_out

def cancel_oca(oca_group: str) -> dict:
    rec = registry.get_record(oca_group)
    if not rec:
        raise HTTPException(status_code=404, detail="Unknown OCA group")

    ib_ids = [int(leg.get("ib_order_id")) for leg in rec.get("legs", []) if leg.get("ib_order_id") is not None]
    # annuleren via adapter (zoals je al had)
    from server.modules.order_transmitting.adapters.ibkr.adapter import ADAPTER
    cnt = ADAPTER.cancel_bracket(ib_ids)
    registry.mark_inactive(oca_group)
    return {"oca_group": oca_group, "cancelled_count": cnt, "ib_order_ids": set(ib_ids), "method": "adapter.cancel_bracket"}
