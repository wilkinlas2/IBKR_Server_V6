import os

def current_adapter_name() -> str:
    return os.getenv("IBKR_ADAPTER", "mock").lower()

def load_adapter(name: str | None = None):
    adapter_name = (name or current_adapter_name())
    if adapter_name == "ibkr":
        from .adapters.ibkr.adapter import ADAPTER
        return "ibkr", ADAPTER
    from .adapters.mock.adapter import ADAPTER
    return "mock", ADAPTER
