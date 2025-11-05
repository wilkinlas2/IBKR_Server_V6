from fastapi import APIRouter
from server.modules.order_transmitting.service import queue_size

router = APIRouter(prefix="/transmit", tags=["order_transmitting"])

@router.get("/queue")
def get_queue_size():
    return {"queued": queue_size()}
