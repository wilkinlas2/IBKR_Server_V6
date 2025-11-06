from __future__ import annotations
import os
import threading
from queue import Queue
from typing import Tuple, Any, Optional, Callable

try:
    from ib_insync import IB, Stock, Order, MarketOrder, LimitOrder, StopOrder  # type: ignore
except Exception as e:  # pragma: no cover
    IB = None
    _IMPORT_ERROR = e
else:
    _IMPORT_ERROR = None

from server.modules.data.store import RESULTS

_HOST = os.getenv("IBKR_HOST", "127.0.0.1")
_PORT = int(os.getenv("IBKR_PORT", "7497"))
_CLIENT_ID = int(os.getenv("IBKR_CLIENT_ID", "9"))

# ---------- IB thread runner ----------
class _Task:
    __slots__ = ("fn", "args", "kwargs", "ev", "result", "error")
    def __init__(self, fn: Callable, *args, **kwargs):
        import threading as _t
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.ev = _t.Event()
        self.result: Any = None
        self.error: Optional[BaseException] = None

class IBRunner:
    def __init__(self):
        if IB is None:
            raise RuntimeError(f"ib_insync not available: {_IMPORT_ERROR!r}")
        import threading as _t
        self._q: "Queue[_Task]" = Queue()
        self._t = _t.Thread(target=self._thread_main, name="IBKR-Thread", daemon=True)
        self._started = False
        self._lock = _t.Lock()
        self.ib: Optional[IB] = None

    def start(self):
        with self._lock:
            if not self._started:
                self._t.start()
                self._started = True

    def _ensure_loop(self):
        import asyncio
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.set_event_loop(asyncio.new_event_loop())

    def _thread_main(self):
        self._ensure_loop()
        self.ib = IB()
        ok = self.ib.connect(_HOST, _PORT, clientId=_CLIENT_ID, readonly=False)
        if not ok:
            err = RuntimeError(f"IB.connect failed to {_HOST}:{_PORT} (clientId={_CLIENT_ID})")
            while True:
                task = self._q.get()
                task.error = err
                task.ev.set()
                self._q.task_done()
        while True:
            task = self._q.get()
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

_runner = IBRunner()

# ---------- helpers ----------
def _qualified_stock(ib: IB, symbol: str, exchange: str = "SMART"):
    base = Stock(symbol=symbol, exchange=exchange, currency="USD")
    q = ib.qualifyContracts(base)
    if not q:
        raise RuntimeError(f"kon contract niet kwalificeren: {symbol}/{exchange}/USD")
    return q[0]

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
        lp = float(order_dict.get("limit_price", 0))
        if lp <= 0:
            raise ValueError("limit_price vereist voor LMT")
        o = LimitOrder(action=side, totalQuantity=qty, lmtPrice=lp)
    else:
        raise ValueError(f"unsupported order_type: {typ}")
    o.tif = tif
    return o

def _place_simple(ib: IB, order_dict: dict):
    symbol = order_dict.get("symbol"); exchange = order_dict.get("exchange", "SMART")
    if not symbol: raise ValueError("order.symbol ontbreekt")
    c = _qualified_stock(ib, symbol, exchange)
    trade = ib.placeOrder(c, _build_simple_order(order_dict))
    return trade

def _opposite(side: str) -> str:
    return "SELL" if side.upper() == "BUY" else "BUY"

def _manual_bracket(ib: IB, base_order: dict, target_price: float, stop_price: float):
    """
    Parent=MKT + OCO(Profit=LMT, Stop=STP) — met kleine waits en expliciete parentId op de kinderen.
    """
    symbol = base_order.get("symbol"); exchange = base_order.get("exchange", "SMART")
    side   = base_order.get("side", "BUY").upper()
    qty    = int(base_order.get("quantity", 0))
    tif    = base_order.get("tif", "DAY")
    if not symbol or qty <= 0:
        raise ValueError("symbol/quantity ontbreekt")

    c = _qualified_stock(ib, symbol, exchange)

    parent = MarketOrder(action=side, totalQuantity=qty); parent.tif = tif; parent.transmit = False
    parent_trade = ib.placeOrder(c, parent)
    # wacht héél even zodat IB een orderId en openOrder event terugstuurt
    ib.sleep(0.25)
    pid = getattr(parent_trade.order, "orderId", None)
    if pid is None:
        # extra wait als nodig
        ib.waitOnUpdate(timeout=2)
        pid = getattr(parent_trade.order, "orderId", None)
        if pid is None:
            raise RuntimeError("kon parent orderId niet verkrijgen")

    oca_group = f"OCA-{pid}"
    child_side = _opposite(side)

    profit = LimitOrder(action=child_side, totalQuantity=qty, lmtPrice=float(target_price))
    profit.tif = tif; profit.parentId = pid; profit.ocaGroup = oca_group; profit.ocaType = 1; profit.transmit = False

    stop = StopOrder(action=child_side, totalQuantity=qty, stopPrice=float(stop_price))
    stop.tif = tif; stop.parentId = pid; stop.ocaGroup = oca_group; stop.ocaType = 1; stop.transmit = True

    profit_trade = ib.placeOrder(c, profit)
    ib.sleep(0.15)
    stop_trade = ib.placeOrder(c, stop)

    return parent_trade, profit_trade, stop_trade

def _place_bracket(ib: IB, base_order: dict, target_price: float, stop_price: float):
    """
    Probeer helper (nieuwe signatuur), anders fallback naar manual met waits/parentId.
    """
    symbol = base_order.get("symbol"); exchange = base_order.get("exchange", "SMART")
    tif    = base_order.get("tif", "DAY")
    side   = base_order.get("side", "BUY").upper()
    qty    = int(base_order.get("quantity", 0))
    if not symbol or qty <= 0:
        raise ValueError("symbol/quantity ontbreekt")

    c = _qualified_stock(ib, symbol, exchange)

    try:
        # nieuwe signatuur: (action, quantity, takeProfitPrice, stopLossPrice)
        parent, profit, stop = ib.bracketOrder(action=side, quantity=qty,
                                               takeProfitPrice=float(target_price),
                                               stopLossPrice=float(stop_price))
        parent.tif = profit.tif = stop.tif = tif
        # Plaats parent en wacht op id
        parent_trade = ib.placeOrder(c, parent)
        ib.sleep(0.25)
        pid = getattr(parent_trade.order, "orderId", None)
        if pid is None:
            ib.waitOnUpdate(timeout=2)
            pid = getattr(parent_trade.order, "orderId", None)
        # Forceer parentId/ transmit flags op kinderen (sommige versies zetten dit niet consequent)
        profit.parentId = pid; profit.transmit = False
        stop.parentId   = pid; stop.transmit   = True
        profit_trade = ib.placeOrder(c, profit)
        ib.sleep(0.15)
        stop_trade   = ib.placeOrder(c, stop)
        return parent_trade, profit_trade, stop_trade
    except TypeError:
        # oude signatuur -> manual
        return _manual_bracket(ib, base_order, target_price, stop_price)

# ---------- result updates ----------
def _coerce_filled(trade) -> int:
    try:
        val = getattr(trade, "filled", None)
        if callable(val): val = val()
        if val is None:   val = getattr(trade.orderStatus, "filled", 0)
        return int(val or 0)
    except Exception:
        try:    return int(getattr(trade.orderStatus, "filled", 0) or 0)
        except Exception: return 0

def _get_limit_price(order) -> Optional[float]:
    for a in ("lmtPrice", "limitPrice"):
        if hasattr(order, a):
            try:
                v = getattr(order, a)
                return float(v) if v is not None else None
            except Exception:
                pass
    return None

def _get_stop_price(order) -> Optional[float]:
    for a in ("stopPrice", "auxPrice"):
        if hasattr(order, a):
            try:
                v = getattr(order, a)
                return float(v) if v is not None else None
            except Exception:
                pass
    return None

def _update_results_from_trade(trade, internal_id: str):
    try:
        status = (getattr(trade.orderStatus, "status", None) or "unknown").lower()
        filled = _coerce_filled(trade)
        avg    = getattr(trade.orderStatus, "avgFillPrice", None)
        oid    = getattr(trade.order, "orderId", None)
        RESULTS[internal_id] = {
            "status": status,
            "filled_qty": filled,
            "avg_price": avg,
            "detail": {
                "action": trade.order.action,
                "totalQuantity": trade.order.totalQuantity,
                "orderType": trade.order.orderType,
                "lmtPrice": _get_limit_price(trade.order),
                "stopPrice": _get_stop_price(trade.order),
                "tif": trade.order.tif,
            },
            "ibkr_order_id": oid,
            "adapter": "ibkr",
        }
    except Exception as e:
        RESULTS[internal_id] = {"status": "error", "error": str(e), "adapter": "ibkr"}

def _bind_trade_events(trade, internal_id: str):
    def _on_status(tr): _update_results_from_trade(tr, internal_id)
    def _on_fills(tr, *args): _update_results_from_trade(tr, internal_id)
    if hasattr(trade, "statusEvent"): trade.statusEvent += _on_status
    if hasattr(trade, "fillsEvent"):  trade.fillsEvent  += _on_fills

# ---------- public adapter ----------
class IbkrAdapter:
    def send(self, order: dict, internal_id: Optional[str] = None) -> Tuple[bool, dict[str, Any]]:
        try:
            tr = _runner.run(_place_simple, order)
            oid = getattr(tr.order, "orderId", None)
            if internal_id:
                _bind_trade_events(tr, internal_id)
                _update_results_from_trade(tr, internal_id)
            status = (getattr(tr.orderStatus, "status", None) or "queued").lower()
            return True, {"status": status, "detail": order, "ibkr": True, "ibkr_order_id": oid}
        except Exception as e:
            return False, {"status": "error", "error": str(e), "detail": order}

    def place_bracket(self, base_order: dict, target_price: float, stop_price: float,
                      internal_ids: dict[str, str]) -> Tuple[bool, dict[str, Any]]:
        try:
            pt, pr, st = _runner.run(_place_bracket, base_order, float(target_price), float(stop_price))
            _bind_trade_events(pt, internal_ids["parent"]); _update_results_from_trade(pt, internal_ids["parent"])
            _bind_trade_events(pr, internal_ids["target"]); _update_results_from_trade(pr, internal_ids["target"])
            _bind_trade_events(st, internal_ids["stop"]);   _update_results_from_trade(st, internal_ids["stop"])
            ibkr_ids = {
                "parent": getattr(pt.order, "orderId", None),
                "target": getattr(pr.order, "orderId", None),
                "stop":   getattr(st.order, "orderId", None),
            }
            return True, {"ibkr_order_ids": ibkr_ids}
        except Exception as e:
            return False, {"status": "error", "error": str(e)}

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
