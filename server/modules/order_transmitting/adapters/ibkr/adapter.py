from __future__ import annotations
import os
import threading
from queue import Queue
from typing import Tuple, Any, Optional, Callable

try:
    from ib_insync import IB, Stock, Order, MarketOrder, LimitOrder, StopOrder  # type: ignore
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
#  IBRunner: 1 thread die alle IB-calls uitvoert (met eigen asyncio loop)
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
        import asyncio
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

    def _thread_main(self):
        self._ensure_loop_in_thread()
        self.ib = IB()
        ok = self.ib.connect(_HOST, _PORT, clientId=_CLIENT_ID, readonly=False)
        if not ok:
            err = RuntimeError(f"IB.connect failed to {_HOST}:{_PORT} (clientId={_CLIENT_ID})")
            while True:
                task: _Task = self._q.get()
                task.error = err
                task.ev.set()
                self._q.task_done()
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
#  Helpers (draaien binnen IB-thread)
# =======================
def _qualified_stock(ib: IB, symbol: str, exchange: str = "SMART"):
    base = Stock(symbol=symbol, exchange=exchange, currency="USD")
    qualified = ib.qualifyContracts(base)
    if not qualified:
        raise RuntimeError(f"kon contract niet kwalificeren: {symbol}/{exchange}/USD")
    return qualified[0]

def _build_simple_order(order_dict: dict) -> Order:
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

def _place_simple(ib: IB, order_dict: dict):
    symbol = order_dict.get("symbol"); exchange = order_dict.get("exchange", "SMART")
    if not symbol: raise ValueError("order.symbol ontbreekt")
    contract = _qualified_stock(ib, symbol, exchange)
    ib_order = _build_simple_order(order_dict)
    trade = ib.placeOrder(contract, ib_order)
    return trade

def _opposite(side: str) -> str:
    return "SELL" if side.upper() == "BUY" else "BUY"

def _place_bracket(ib: IB, base_order: dict, target_price: float, stop_price: float):
    """
    Plaats parent (transmit=False) + target (transmit=False) + stop (transmit=True) met OCA.
    """
    symbol = base_order.get("symbol"); exchange = base_order.get("exchange", "SMART")
    side   = base_order.get("side", "BUY").upper()
    qty    = int(base_order.get("quantity", 0))
    tif    = base_order.get("tif", "DAY")

    if not symbol or qty <= 0:
        raise ValueError("symbol/quantity ontbreekt")

    contract = _qualified_stock(ib, symbol, exchange)

    # Parent (Market), transmit False
    parent = MarketOrder(action=side, totalQuantity=qty)
    parent.tif = tif
    parent.transmit = False
    parent_trade = ib.placeOrder(contract, parent)
    parent_id = parent_trade.order.orderId

    # OCA group
    oca_group = f"OCA-{parent_id}"

    # Children – opposite side
    child_side = _opposite(side)

    # Target (Limit), transmit False
    target = LimitOrder(action=child_side, totalQuantity=qty, lmtPrice=float(target_price))
    target.tif = tif
    target.parentId = parent_id
    target.ocaGroup = oca_group
    target.ocaType = 1  # CANCEL_WITH_BLOCK (typische OCO)
    target.transmit = False
    target_trade = ib.placeOrder(contract, target)

    # Stop (Stop), transmit True (laatste triggert de hele chain)
    stop = StopOrder(action=child_side, totalQuantity=qty, stopPrice=float(stop_price))
    stop.tif = tif
    stop.parentId = parent_id
    stop.ocaGroup = oca_group
    stop.ocaType = 1
    stop.transmit = True
    stop_trade = ib.placeOrder(contract, stop)

    return parent_trade, target_trade, stop_trade

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
                    "auxPrice": getattr(_trade.order, "auxPrice", None),
                    "stopPrice": getattr(_trade.order, "stopPrice", None),
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

    # ===== Single order (bestond al) =====
    def send(self, order: dict, internal_id: Optional[str] = None) -> Tuple[bool, dict[str, Any]]:
        try:
            trade = _runner.run(_place_simple, order)
            oid = getattr(trade.order, "orderId", None)
            if internal_id:
                _bind_trade_events(trade, internal_id)
            status = (getattr(trade.orderStatus, "status", None) or "queued").lower()
            return True, {"status": status, "detail": order, "ibkr": True, "ibkr_order_id": oid}
        except Exception as e:
            return False, {"status": "error", "error": str(e), "detail": order}

    # ===== Bracket (parent + OCO) =====
    def place_bracket(self, base_order: dict, target_price: float, stop_price: float,
                      internal_ids: dict[str, str]) -> Tuple[bool, dict[str, Any]]:
        """
        internal_ids: {"parent": <id>, "target": <id>, "stop": <id>}
        """
        try:
            parent_trade, target_trade, stop_trade = _runner.run(
                _place_bracket, base_order, float(target_price), float(stop_price)
            )
            # bind events naar onze 3 RESULTS sleutels
            _bind_trade_events(parent_trade, internal_ids["parent"])
            _bind_trade_events(target_trade, internal_ids["target"])
            _bind_trade_events(stop_trade,   internal_ids["stop"])

            ibkr_ids = {
                "parent": getattr(parent_trade.order, "orderId", None),
                "target": getattr(target_trade.order, "orderId", None),
                "stop":   getattr(stop_trade.order,   "orderId", None),
            }
            return True, {"ibkr_order_ids": ibkr_ids}
        except Exception as e:
            return False, {"status": "error", "error": str(e)}

    # ===== Cancel by internal id (optioneel) =====
    def cancel(self, internal_id: str):
        try:
            data = RESULTS.get(internal_id) or {}
            ibkr_id = data.get("ibkr_order_id")
            if ibkr_id is None:
                return {"ok": False, "error": "ibkr_order_id unknown"}
            def _cancel(ib: IB, oid: int):
                trade = next((t for t in ib.trades() if getattr(t.order, "orderId", None) == oid), None)
                if not trade:
                    return False
                ib.cancelOrder(trade.order)
                return True
            ok = _runner.run(_cancel, ibkr_id)
            return {"ok": bool(ok)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

ADAPTER = IbkrAdapter()
