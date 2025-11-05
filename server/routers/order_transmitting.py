from fastapi import APIRouter
from server.modules.order_transmitting.service import queue_size
from server.modules.order_transmitting.config import load_adapter

router = APIRouter(prefix="/transmit", tags=["order_transmitting"])

@router.get("/queue")
def get_queue_size():
    return {"queued": queue_size()}

@router.get("/adapter")
def get_adapter():
    name, _ = load_adapter()
    return {"adapter": name}

@router.get("/diag")
def diag():
    name, _ = load_adapter()
    info = {"adapter": name}
    if name == "ibkr":
        try:
            # lazy import om circulars te vermijden
            from server.modules.order_transmitting.adapters.ibkr.adapter import _runner, _HOST, _PORT, _CLIENT_ID
            # forceer start van de runner; geeft connect errors meteen
            try:
                _runner.start()
                connected = True  # als start niet crasht, is connect gelukt of wordt lazily gedaan op eerste taak
            except Exception as e:
                connected = False
                info["error"] = str(e)
            info.update({"connected": connected, "host": _HOST, "port": _PORT, "clientId": _CLIENT_ID})
        except Exception as e:
            info.update({"connected": False, "error": str(e)})
    return info
