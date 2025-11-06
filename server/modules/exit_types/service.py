from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

# Eenvoudige in-memory registry voor onze OCA brackets
# key = oca_group (vb. "OCA-31")
# value = dict met meta + legs
ACTIVE_OCA: Dict[str, Dict[str, Any]] = {}


@dataclass
class OcaLeg:
    name: str            # "parent" | "target" | "stop"
    internal_id: str     # ons results-id
    ib_order_id: Optional[int]  # IBKR orderId (na plaatsen)
    side: str
    order_type: str
    price: Optional[float] = None


def remember_oca(
    oca_group: str,
    symbol: str,
    quantity: int,
    side: str,
    tif: str,
    legs: Dict[str, OcaLeg],
) -> None:
    """Bewaar/overschrijf een OCA group in het geheugen."""
    ACTIVE_OCA[oca_group] = {
        "symbol": symbol,
        "quantity": quantity,
        "side": side,
        "tif": tif,
        "legs": {k: asdict(v) for k, v in legs.items()},
    }


def list_oca() -> Dict[str, Dict[str, Any]]:
    """Geef alle gekende (door ons aangemaakte) OCA groups terug."""
    return ACTIVE_OCA


def remove_oca(oca_group: str) -> bool:
    """Verwijder een OCA group uit het geheugen (bijv. na volledige fill of cancel)."""
    return ACTIVE_OCA.pop(oca_group, None) is not None
