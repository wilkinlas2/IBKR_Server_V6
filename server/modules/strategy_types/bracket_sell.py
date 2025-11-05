ID = "bracket_sell"
SCHEMA = {
    "description": "Bracket SELL (parent MKT + target LMT + stop STP)",
    "params": {
        "quantity": {"type": "int", "min": 1, "required": True},
        "target_price": {"type": "float", "min": 0.0, "required": True},
        "stop_price": {"type": "float", "min": 0.0, "required": True},
        "tif": {"type": "str", "default": "DAY"},
    },
}

def build(symbol: str, params: dict) -> dict:
    qty = int(params.get("quantity", 0))
    tp  = float(params.get("target_price", 0))
    sp  = float(params.get("stop_price", 0))
    if qty <= 0: raise ValueError("quantity > 0 required")
    if tp <= 0 or sp <= 0: raise ValueError("target_price & stop_price > 0 required")
    tif = params.get("tif", "DAY")
    return {
        "type": "bracket",
        "base_order": {
            "symbol": symbol, "side": "SELL", "quantity": qty, "tif": tif, "exchange": "SMART"
        },
        "target_price": tp,
        "stop_price": sp,
    }
