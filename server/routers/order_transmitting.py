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
