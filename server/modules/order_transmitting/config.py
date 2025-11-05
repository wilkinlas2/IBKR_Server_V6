import os

ADAPTER_NAME = os.getenv("IBKR_ADAPTER", "mock").lower()

def load_adapter():
    if ADAPTER_NAME == "ibkr":
        from .adapters.ibkr.adapter import ADAPTER
        return "ibkr", ADAPTER
    # default
    from .adapters.mock.adapter import ADAPTER
    return "mock", ADAPTER
