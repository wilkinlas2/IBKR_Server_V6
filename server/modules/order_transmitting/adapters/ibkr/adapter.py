from __future__ import annotations
import os
import threading
from queue import Queue
from typing import Tuple, Any, Optional, Callable

try:
    from ib_insync import IB, Stock, Order, MarketOrder, LimitOrder  # type: ignore
except Exception as e:  # pragma: no cover
    IB = None  # sentinel
    _IMPORT_ERROR = e
else:
    _IMPORT_ERROR = None

from server.modules.data.store import RESULTS  # we updaten rechtstreeks onze in-memory store

# --- ENV CONFIG ---
_HOST = os.getenv("IBKR_HOST", "127.0.0.1")
_PORT = int(os.getenv("IBKR_PORT", "7497"))       # paper vaak 7497, live vaak 7496
_CLIENT_ID = int(os.getenv("IBKR_CLIENT_ID", "9"))

# =======================
#  IBRunner: 1 thread die alle IB-calls uitvoert
# =======================
class _Task:
    __slots__ = ("fn", "args", "kwargs", "ev", "result", "error")
    def __init__(self, fn: Callable, *args, **kwargs):
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.ev = threading.Event()
        self.result: Any = None
        self.error: Optional[BaseException] = None

class IBRunner:
    def __init__(self):
        if IB is None:
            raise RuntimeError(f"ib_insync not available: {_IMPORT_ERROR!r}")
        self._q: "Queue[_Task]" = Queue()
        self._thread = threading.Thread(target=self._thread_main, name="IBKR-Thread", daemon=True)
        self._started = False
        self._lock = threading.Lock()
        self.ib: Optional[IB] = None

    def start(self):
        with self._lock:
            if not self._started:
                self._thread.start()
                self._started = True

    def _ensure_loop_in_thread(self):
        # maak een asyncio event loop in deze dedicated thread
        import asyncio
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

    def _thread_main(self):
        # 1) event loop klaarzetten
        self._ensure_loop_in_thread()
        # 2) IB connecten (synchronisch)
        self.ib = IB()
        ok = self.ib.connect(_HOST, _PORT, clientId=_CLIENT_ID, readonly=False)
        if not ok:
            # als connect faalt, takel binnenkomende taken af met error
            err = RuntimeError(f"IB.connect failed to {_HOST}:{_PORT} (clientId={_CLIENT_ID})")
            while True:
                task: _Task = self._q.get()
                task.error = err
                task.ev.set()
                self._q.task_done()
        # 3) event loop voor taken
        while True:
            task: _Task = self._q.get()
            try:
                task.result = task.fn(self.ib, *task.args, **task.kwargs)
            except BaseException as e:
                task.error = e
            finally:
                task.ev.set()
                self._q.task_done()

    def run(self, fn: Callable, *args, **kwargs):
        """Voer callable uit in IB-thread, blokkeer tot klaar."""
        self.start()
        task = _Task(fn, *args, **kwargs)
        self._q.put(task)
        task.ev.wait()
        if task.error:
            raise task.error
        return task.result

# singleton runner
_runner = IBRunner()

# =======================
#  Adapter hulpfuncties (draaien binnen IB-thread via _runner.run)
# =======================
def _qualified_stock(ib: IB, symbol: str, exchange: str = "SMART"):
    base = Stock(symbol=symbol, exchange=exchange, currency="USD")
    qualified = ib.qualifyContracts(base)
    if not qualified:
        raise RuntimeError(f"kon contract niet kwalificeren: {symbol}/{exchange}/USD")
    return qualified[0]

def _build_order(order_dict: dict) -> Order:
    side = order_dict.get("side", "BUY").upper()
    tif = order_dict.get("tif", "DAY")
    qty = int(order_dict.get("quantity", 0))
    if qty <= 0:
        raise ValueError("quantity moet > 0 zijn")
    typ = order_dict.get("order_type", "MKT").upper()
    if typ == "MKT":
        o = MarketOrder(action=side, totalQuantity=qty)
    elif typ == "LMT":
        limit_price = float(order_dict.get("limit_price", 0))
        if limit_price <= 0:
            raise ValueError("limit_price vereist voor LMT")
        o = LimitOrder(action=side, totalQuantity=qty, lmtPrice=limit_price)
    else:
        raise ValueError(f"unsupported order_type: {typ}")
    o.tif = tif
    return o

def _place_on_ib(ib: IB, order_dict: dict):
    symbol = order_dict.get("symbol")
    if not symbol:
        raise ValueError("order.symbol ontbreekt")
    exchange = order_dict.get("exchange", "SMART")
    contract = _qualified_stock(ib, symbol, exchange)
    ib_order = _build_order(order_dict)
    trade = ib.placeOrder(contract, ib_order)
    return trade

# =======================
#  Public adapter
# =======================
def _bind_trade_events(trade, internal_id: str):
    def _update_from_trade(_trade):
        try:
            status = (_trade.orderStatus.status or "unknown").lower()
            filled = int(getattr(_trade, "filled", 0) or 0)
            avg = getattr(_trade.orderStatus, "avgFillPrice", None)
            oid = getattr(_trade.order, "orderId", None)
            RESULTS[internal_id] = {
                "status": status,
                "filled_qty": filled,
                "avg_price": avg,
                "detail": {
                    "action": _trade.order.action,
                    "totalQuantity": _trade.order.totalQuantity,
                    "orderType": _trade.order.orderType,
                    "lmtPrice": getattr(_trade.order, "lmtPrice", None),
                    "tif": _trade.order.tif,
                },
                "ibkr_order_id": oid,
                "adapter": "ibkr",
            }
        except Exception as e:
            RESULTS[internal_id] = {"status": "error", "error": str(e), "adapter": "ibkr"}
    trade.updateEvent += _update_from_trade

class IbkrAdapter:
    """IBKR adapter via dedicated IB-thread met eigen event loop."""

    def send(self, order: dict, internal_id: Optional[str] = None) -> Tuple[bool, dict[str, Any]]:
        try:
            trade = _runner.run(_place_on_ib, order)
            oid = getattr(trade.order, "orderId", None)
            if internal_id:
                _bind_trade_events(trade, internal_id)
            status = (getattr(trade.orderStatus, "status", None) or "queued").lower()
            return True, {
                "status": status,
                "detail": order,
                "ibkr": True,
                "ibkr_order_id": oid,
            }
        except Exception as e:
            return False, {"status": "error", "error": str(e), "detail": order}

ADAPTER = IbkrAdapter()
