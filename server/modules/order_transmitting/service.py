import uuid
from server.modules.data.store import ORDERS, RESULTS

def enqueue_order(o: dict) -> str:
    order_id = uuid.uuid4().hex[:12]
    ORDERS[order_id] = o
    # instantly mark as 'queued' (later: real IBKR API call)
    RESULTS[order_id] = {"status":"queued","detail":o}
    return order_id

def queue_size() -> int:
    return len(ORDERS)
