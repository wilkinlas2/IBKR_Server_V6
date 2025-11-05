from __future__ import annotations

class IbkrAdapter:
    """
    IBKR stub adapter.
    TODO: vervang later door echte TWS/Gateway integratie (bv. ib_insync).
    Voor nu doen we een 'queued' response zodat de bestaande worker flow blijft werken.
    """
    def send(self, order: dict):
        # TODO: connectie + plaats order + capture orderId + status
        return True, {"status": "queued", "detail": order, "ibkr": True}

ADAPTER = IbkrAdapter()
