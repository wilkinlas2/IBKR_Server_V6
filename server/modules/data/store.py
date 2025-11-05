# simple in-memory store
SYMBOLS = ["AAPL","MSFT","NVDA","META","TSLA","GOOGL"]
ORDERS: dict[str, dict] = {}
RESULTS: dict[str, dict] = {}

def get_symbols():
    return SYMBOLS

def get_status():
    return {
        "symbols": len(SYMBOLS),
        "orders": len(ORDERS),
        "results": len(RESULTS)
    }
