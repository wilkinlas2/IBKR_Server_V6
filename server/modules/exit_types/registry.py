# --- snippet: voeg/controleer deze helpers ---
_REGISTRY: dict[str, dict] = {}     # oca_group -> record {symbol, legs:[...], active: bool}
_ACTIVE:   dict[str, bool] = {}     # oca_group -> bool

def upsert_record(oca_group: str, record: dict) -> None:
    _REGISTRY[oca_group] = dict(record)
    _ACTIVE[oca_group]   = bool(record.get("active", True))

def mark_inactive(oca_group: str) -> None:
    if oca_group in _ACTIVE:
        _ACTIVE[oca_group] = False
    if oca_group in _REGISTRY:
        _REGISTRY[oca_group]["active"] = False

def list_active_ocas() -> dict[str, bool]:
    return {k: v for k, v in _ACTIVE.items() if v}

def get_record(oca_group: str) -> dict | None:
    # Geef snapshot terug, ook als inactive.
    return _REGISTRY.get(oca_group)
