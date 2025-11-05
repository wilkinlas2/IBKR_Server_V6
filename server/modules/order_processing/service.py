def validate_order(o: dict) -> tuple[bool,str]:
    if not o.get("symbol"):
        return False, "symbol required"
    if o.get("quantity",0) <= 0:
        return False, "quantity > 0 required"
    if o.get("order_type") == "LMT" and not o.get("limit_price"):
        return False, "limit_price required for LMT"
    return True, "ok"

def enrich_order(o: dict) -> dict:
    # add trivial defaults
    o = {**o}
    o.setdefault("tif","DAY")
    o.setdefault("exchange","SMART")
    return {"order": o}
