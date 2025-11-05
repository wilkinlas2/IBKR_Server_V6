ID = "lmt_buy"
SCHEMA = {
    "description": "Limit BUY",
    "params": {
        "quantity": {"type": "int", "min": 1, "required": True},
        "limit_price": {"type": "float", "min": 0.0, "required": True},
        "tif": {"type": "str", "default": "DAY"},
    },
}

def build(symbol: str, params: dict) -> dict:
    qty = int(params.get("quantity", 0))
    price = float(params.get("limit_price", 0))
    if qty <= 0: raise ValueError("quantity > 0 required")
    if price <= 0: raise ValueError("limit_price > 0 required")
    tif = params.get("tif", "DAY")
    return {
        "type": "single",
        "order": {
            "symbol": symbol,
            "side": "BUY",
            "order_type": "LMT",
            "quantity": qty,
            "limit_price": price,
            "tif": tif,
            "exchange": "SMART",
        },
    }
