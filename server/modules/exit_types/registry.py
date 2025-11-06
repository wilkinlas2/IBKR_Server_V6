from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

from server.modules.persistence.db import oca_upsert, oca_upsert_leg, oca_load_all

@dataclass
class Leg:
    role: str
    internal_id: str
    ib_order_id: Optional[int] = None
    status: Optional[str] = None

# In-memory registry
# shape: { oca_group: { "symbol": str, "legs": List[Leg] } }
_OCA: Dict[str, Dict[str, Any]] = {}

def _load_from_db_once():
    """Prime de in-memory registry vanuit SQLite (éénmalig)."""
    global _OCA
    if _OCA:
        return
    rows = oca_load_all()  # {oca: {symbol, legs:[{role,internal_id,ib_order_id,status}, ...]}}
    for oca_group, data in rows.items():
        legs = [Leg(**l) for l in data.get("legs", [])]
        _OCA[oca_group] = {"symbol": data.get("symbol"), "legs": legs}

# prime bij import
_load_from_db_once()

# -----------------
# Nieuwe API namen
# -----------------

def list_active() -> Dict[str, bool]:
    """Geeft alle bekende OCA-groepen terug als { oca_group: True }."""
    if not _OCA:
        _load_from_db_once()
    return {k: True for k in _OCA.keys()}

def get_detail(oca_group: str) -> Dict[str, Any] | None:
    """Detail van een OCA: symbol + legs incl. status/ids (legs als dicts)."""
    reg = _OCA.get(oca_group)
    if not reg:
        _load_from_db_once()
        reg = _OCA.get(oca_group)
        if not reg:
            return None
    legs = [
        {
            "role": l.role,
            "internal_id": l.internal_id,
            "ib_order_id": l.ib_order_id,
            "status": l.status,
        }
        for l in reg["legs"]
    ]
    return {"oca_group": oca_group, "symbol": reg["symbol"], "legs": legs}

def register_bracket(oca_group: str, symbol: str, legs: List[Leg]) -> str:
    """
    Registreer/overschrijf een OCA met legs (parent/target/stop of OCO-only).
    Schrijft zowel in memory als in SQLite.
    """
    if not oca_group or not symbol:
        raise ValueError("oca_group/symbol required")
    _OCA[oca_group] = {"symbol": symbol, "legs": legs}
    oca_upsert(oca_group, symbol)
    for l in legs:
        oca_upsert_leg(oca_group, l.role, l.internal_id, l.ib_order_id, l.status)
    return oca_group

def ensure_registered(symbol: str, ibkr_order_ids: Dict[str, int], internal_ids: Dict[str, str]) -> str:
    """
    Convenience: maak OCA naam o.b.v. parent IB id en registreer alle legs.
    """
    if not symbol or not ibkr_order_ids:
        raise ValueError("symbol/ibkr_order_ids required")
    if not all(k in ibkr_order_ids for k in ("parent", "target", "stop")):
        raise ValueError("ibkr_order_ids must contain parent/target/stop")
    oca_group = f"OCA-{symbol}-{int(ibkr_order_ids['parent'])}"
    legs = [
        Leg(role="parent", internal_id=str(internal_ids.get("parent")), ib_order_id=int(ibkr_order_ids["parent"])),
        Leg(role="target", internal_id=str(internal_ids.get("target")), ib_order_id=int(ibkr_order_ids["target"])),
        Leg(role="stop",   internal_id=str(internal_ids.get("stop")),   ib_order_id=int(ibkr_order_ids["stop"])),
    ]
    register_bracket(oca_group, symbol, legs)
    return oca_group

def update_leg_status(oca_group: str, role: str, status: Optional[str]):
    """Werk status van één leg bij (memory + SQLite)."""
    reg = _OCA.get(oca_group)
    if not reg:
        return
    for l in reg["legs"]:
        if l.role == role:
            l.status = status
            oca_upsert_leg(oca_group, l.role, l.internal_id, l.ib_order_id, status)
            break

# ----------------------------
# Backward-compatibele aliassen
# ----------------------------

def list_active_ocas() -> Dict[str, bool]:
    """Alias voor oudere code die list_active_ocas importeert."""
    return list_active()

def get_oca_detail(oca_group: str) -> Dict[str, Any] | None:
    """Alias voor oudere code die get_oca_detail importeert."""
    return get_detail(oca_group)

def get_record(oca_group: str) -> Dict[str, Any] | None:
    """
    Alias voor oudere code die get_record importeert.
    Geeft dezelfde shape als get_detail() terug (legs als dicts) om compatibel te blijven.
    """
    return get_detail(oca_group)
