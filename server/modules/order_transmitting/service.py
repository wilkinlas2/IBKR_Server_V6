import uuid, threading, time, random
from queue import Queue
from typing import Tuple
from server.modules.data.store import ORDERS, RESULTS
from .config import load_adapter

_q: "Queue[tuple[str, dict]]" = Queue()
_worker_started = False

def _worker():
    """Pullt orders uit de queue en simuleert fills (onafhankelijk van adapter)."""
    while True:
        order_id, order = _q.get()
        try:
            # kleine wachttijd om "transmit" te simuleren
            time.sleep(2.0)
            # fake fill
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

def enqueue_order(order: dict) -> str:
    # kies adapter
    adapter_name, adapter = load_adapter()
    # stuur order via adapter
    ok, res = adapter.send(order)
    order_id = uuid.uuid4().hex[:12]
    ORDERS[order_id] = order

    if ok:
        # queued door adapter; worker zal later 'filled' invullen
        RESULTS[order_id] = {"status": res.get("status","queued"), "detail": order, "adapter": adapter_name}
        # in queue steken zodat worker kan 'filled' zetten (mock/stub gedrag)
        _q.put((order_id, order))
    else:
        RESULTS[order_id] = {"status": "error", "detail": order, "adapter": adapter_name, "error": res.get("error")}

    return order_id

def queue_size() -> int:
    return _q.qsize()
