ID = "mkt_buy"
SCHEMA = {
    "description": "Market BUY",
    "params": {
        "quantity": {"type": "int", "min": 1, "required": True},
        "tif": {"type": "str", "default": "DAY"},
    },
}

def build(symbol: str, params: dict) -> dict:
    qty = int(params.get("quantity", 0))
    if qty <= 0:
        raise ValueError("quantity > 0 required")
    tif = params.get("tif", "DAY")
    return {
        "type": "single",
        "order": {
            "symbol": symbol,
            "side": "BUY",
            "order_type": "MKT",
            "quantity": qty,
            "tif": tif,
            "exchange": "SMART",
        },
    }
