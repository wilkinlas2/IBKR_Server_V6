import uuid, threading, time, random
from queue import Queue
from server.modules.data.store import ORDERS, RESULTS
from .config import load_adapter

# Queue en worker worden ALLEEN gebruikt voor de mock-adapter.
_q: "Queue[tuple[str, dict]]" = Queue()
_worker_started = False

def _worker():
    """Mock-fill worker: alleen gebruiken met mock adapter."""
    while True:
        order_id, order = _q.get()
        try:
            time.sleep(2.0)
            px = round(random.uniform(10, 500), 2)
            RESULTS[order_id] = {
                "status": "filled",
                "filled_qty": order.get("quantity", 0),
                "avg_price": px,
                "detail": order,
                "adapter": "mock",
            }
        except Exception as e:
            RESULTS[order_id] = {"status": "error", "error": repr(e), "detail": order, "adapter": "mock"}
        finally:
            _q.task_done()

def start_worker_once():
    """Start alleen bij mock-adapter; voor IBKR doen events het werk."""
    global _worker_started
    adapter_name, _ = load_adapter()
    if adapter_name != "mock":
        return
    if not _worker_started:
        t = threading.Thread(target=_worker, daemon=True, name="transmit-worker")
        t.start()
        _worker_started = True

def enqueue_order(order: dict) -> str:
    """
    Stuurt order via geselecteerde adapter.
    - mock: zet RESULT 'queued' en worker simuleert fill.
    - ibkr: plaatst bij TWS/Gateway; RESULT wordt live geüpdatet via ib_insync events.
    In alle gevallen updaten we RESULTS met 'ok' of 'error' en geven een internal order_id terug.
    """
    adapter_name, adapter = load_adapter()
    order_id = uuid.uuid4().hex[:12]
    ORDERS[order_id] = order

    if adapter_name == "ibkr":
        try:
            ok, res = adapter.send(order, internal_id=order_id)
        except TypeError:
            ok, res = adapter.send(order)

        if ok:
            RESULTS[order_id] = {
                "status": res.get("status", "queued"),
                "detail": order,
                "adapter": adapter_name,
                "ibkr_order_id": res.get("ibkr_order_id"),
            }
        else:
            RESULTS[order_id] = {
                "status": "error",
                "error": res.get("error"),
                "detail": order,
                "adapter": adapter_name,
            }
        return order_id

    ok, res = adapter.send(order)
    if ok:
        RESULTS[order_id] = {
            "status": res.get("status", "queued"),
            "detail": order,
            "adapter": adapter_name,
        }
        _q.put((order_id, order))
    else:
        RESULTS[order_id] = {
            "status": "error",
            "error": res.get("error"),
            "detail": order,
            "adapter": adapter_name,
        }
    return order_id

def queue_size() -> int:
    return _q.qsize()
