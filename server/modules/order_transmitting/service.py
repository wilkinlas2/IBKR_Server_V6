import uuid, threading, time, random
from queue import Queue
from server.modules.data.store import ORDERS, RESULTS

_q: "Queue[tuple[str, dict]]" = Queue()
_worker_started = False

def _worker():
    while True:
        order_id, order = _q.get()
        try:
            # simulatie: verzenden duurt even
            time.sleep(2.0)
            # fake fill prijs
            px = round(random.uniform(10, 500), 2)
            RESULTS[order_id] = {
                "status": "filled",
                "filled_qty": order.get("quantity", 0),
                "avg_price": px,
                "detail": order,
            }
        except Exception as e:
            RESULTS[order_id] = {"status": "error", "error": repr(e), "detail": order}
        finally:
            _q.task_done()

def start_worker_once():
    global _worker_started
    if not _worker_started:
        t = threading.Thread(target=_worker, daemon=True, name="transmit-worker")
        t.start()
        _worker_started = True

def enqueue_order(o: dict) -> str:
    start_worker_once()
    order_id = uuid.uuid4().hex[:12]
    ORDERS[order_id] = o
    RESULTS[order_id] = {"status": "queued", "detail": o}
    _q.put((order_id, o))
    return order_id

def queue_size() -> int:
    return _q.qsize()
