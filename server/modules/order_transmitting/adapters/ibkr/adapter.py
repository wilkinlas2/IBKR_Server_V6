"""
IBKR adapter
- 1 dedicated IB-thread met eigen asyncio loop
- single orders + bracket (parent MKT + OCO target LMT + stop STP)
- status & cancel helpers die binnen dezelfde IB-verbinding draaien
"""

from __future__ import annotations
from typing import Any, Dict, Optional, Tuple, List, Callable
from queue import Queue
import threading
import os
import time

try:
    # ib_insync types
    from ib_insync import IB, Stock, Order, MarketOrder, LimitOrder, StopOrder  # type: ignore
except Exception as e:  # pragma: no cover
    IB = None  # type: ignore
    _IMPORT_ERROR = e
else:
    _IMPORT_ERROR = None

from server.modules.data.store import RESULTS

# -------------------------
# ENV
# -------------------------
_HOST = os.getenv("IBKR_HOST", "127.0.0.1")
_PORT = int(os.getenv("IBKR_PORT", "7497"))
_CLIENT_ID = int(os.getenv("IBKR_CLIENT_ID", "9"))

# -------------------------
# IB runner (dedicated thread)
# -------------------------

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
        # 1) event loop
        self._ensure_loop_in_thread()
        # 2) IB connect (blocking)
        self.ib = IB()
        ok = self.ib.connect(_HOST, _PORT, clientId=_CLIENT_ID, readonly=False)
        if not ok:
            err = RuntimeError(f"IB.connect failed to {_HOST}:{_PORT} (clientId={_CLIENT_ID})")
            # drain queue with error
            while True:
                task: _Task = self._q.get()
                task.error = err
                task.ev.set()
                self._q.task_done()
        # 3) task loop
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

_runner = IBRunner()

# -------------------------
# Helpers
# -------------------------

def _qualified_stock(ib: IB, symbol: str, exchange: str = "SMART"):
    base = Stock(symbol=symbol, exchange=exchange, currency="USD")
    q = ib.qualifyContracts(base)
    if not q:
        raise RuntimeError(f"kon contract niet kwalificeren: {symbol}/{exchange}/USD")
    return q[0]

def _build_order(order: dict) -> Order:
    side = (order.get("side") or "BUY").upper()
    tif = order.get("tif") or "DAY"
    qty = int(order.get("quantity", 0))
    typ = (order.get("order_type") or "MKT").upper()
    if qty <= 0:
        raise ValueError("quantity > 0 vereist")
    if typ == "MKT":
        o = MarketOrder(action=side, totalQuantity=qty)
    elif typ == "LMT":
        lp = float(order.get("limit_price", 0))
        if lp <= 0:
            raise ValueError("limit_price vereist voor LMT")
        o = LimitOrder(action=side, totalQuantity=qty, lmtPrice=lp)
    else:
        raise ValueError(f"unsupported order_type: {typ}")
    o.tif = tif
    return o

def _place_simple(ib: IB, order: dict):
    symbol = order.get("symbol")
    if not symbol:
        raise ValueError("order.symbol ontbreekt")
    exchange = order.get("exchange", "SMART")
    c = _qualified_stock(ib, symbol, exchange)
    trade = ib.placeOrder(c, _build_order(order))
    return trade

def _opposite(side: str) -> str:
    return "SELL" if (side or "").upper() == "BUY" else "BUY"

def _manual_bracket(ib: IB, base_order: dict, target_price: float, stop_price: float):
    """
    Bouw parent MKT + OCO children handmatig met correcte parentId/ocaGroup/transmit.
    """
    symbol = base_order.get("symbol")
    exchange = base_order.get("exchange", "SMART")
    side   = (base_order.get("side") or "BUY").upper()
    qty    = int(base_order.get("quantity", 0))
    tif    = base_order.get("tif") or "DAY"
    if not symbol or qty <= 0:
        raise ValueError("symbol/quantity ontbreekt")

    c = _qualified_stock(ib, symbol, exchange)

    parent = MarketOrder(action=side, totalQuantity=qty)
    parent.tif = tif
    parent.transmit = False
    parent_trade = ib.placeOrder(c, parent)

    # wacht even tot orderId er is
    ib.sleep(0.25)
    pid = getattr(parent_trade.order, "orderId", None)
    if pid is None:
        ib.waitOnUpdate(timeout=2)
        pid = getattr(parent_trade.order, "orderId", None)
        if pid is None:
            raise RuntimeError("kon parent orderId niet verkrijgen")

    oca_group = f"OCA-{pid}"
    child_side = _opposite(side)

    profit = LimitOrder(action=child_side, totalQuantity=qty, lmtPrice=float(target_price))
    profit.tif = tif
    profit.parentId = pid
    profit.ocaGroup = oca_group
    profit.ocaType  = 1
    profit.transmit = False

    stop = StopOrder(action=child_side, totalQuantity=qty, stopPrice=float(stop_price))
    stop.tif = tif
    stop.parentId = pid
    stop.ocaGroup = oca_group
    stop.ocaType  = 1
    stop.transmit = True

    profit_trade = ib.placeOrder(c, profit)
    ib.sleep(0.15)
    stop_trade = ib.placeOrder(c, stop)

    return parent_trade, profit_trade, stop_trade

def _place_bracket(ib: IB, base_order: dict, target_price: float, stop_price: float):
    """
    Probeer ib.bracketOrder helper; zo niet, doe manual.
    """
    symbol = base_order.get("symbol")
    exchange = base_order.get("exchange", "SMART")
    side   = (base_order.get("side") or "BUY").upper()
    qty    = int(base_order.get("quantity", 0))
    tif    = base_order.get("tif") or "DAY"
    if not symbol or qty <= 0:
        raise ValueError("symbol/quantity ontbreekt")

    c = _qualified_stock(ib, symbol, exchange)

    try:
        parent, profit, stop = ib.bracketOrder(
            action=side, quantity=qty,
            takeProfitPrice=float(target_price),
            stopLossPrice=float(stop_price)
        )
        parent.tif = profit.tif = stop.tif = tif
        # parent eerst
        pt = ib.placeOrder(c, parent)
        ib.sleep(0.25)
        pid = getattr(pt.order, "orderId", None)
        if pid is None:
            ib.waitOnUpdate(timeout=2)
            pid = getattr(pt.order, "orderId", None)
        # forceer relationele velden
        profit.parentId = pid; profit.transmit = False
        stop.parentId   = pid; stop.transmit   = True
        pr = ib.placeOrder(c, profit)
        ib.sleep(0.15)
        st = ib.placeOrder(c, stop)
        return pt, pr, st
    except TypeError:
        # oudere ib_insync signatuur? -> manual
        return _manual_bracket(ib, base_order, target_price, stop_price)

# -------------------------
# RESULTS updates
# -------------------------

def _coerce_filled(trade) -> int:
    try:
        val = getattr(trade, "filled", None)
        if callable(val):
            val = val()
        if val is None:
            val = getattr(trade.orderStatus, "filled", 0)
        return int(val or 0)
    except Exception:
        try:
            return int(getattr(trade.orderStatus, "filled", 0) or 0)
        except Exception:
            return 0

def _get_limit_price(order) -> Optional[float]:
    for a in ("lmtPrice", "limitPrice"):
        if hasattr(order, a):
            v = getattr(order, a)
            try:
                return float(v) if v is not None else None
            except Exception:
                pass
    return None

def _get_stop_price(order) -> Optional[float]:
    for a in ("stopPrice", "auxPrice"):
        if hasattr(order, a):
            v = getattr(order, a)
            try:
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
    def _on_update(_tr, *args):
        _update_results_from_trade(_tr, internal_id)
    if hasattr(trade, "updateEvent"):
        trade.updateEvent += _on_update
    else:
        if hasattr(trade, "statusEvent"):
            trade.statusEvent += lambda tr: _update_results_from_trade(tr, internal_id)
        if hasattr(trade, "fillsEvent"):
            trade.fillsEvent  += lambda tr, *a: _update_results_from_trade(tr, internal_id)

# -------------------------
# Adapter
# -------------------------

class IbkrAdapter:
    """Publieke adapter: single send + bracket + (legacy) cancel per internal_id."""

    def send(self, order: dict, internal_id: Optional[str] = None) -> Tuple[bool, Dict[str, Any]]:
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

    def place_bracket(
        self,
        *,
        base_order: dict,
        target_price: float,
        stop_price: float,
        internal_ids: Dict[str, str],
    ) -> Tuple[bool, Dict[str, Any]]:
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
        """Legacy: cancel via internal_id → zoek ib_order_id in RESULTS en cancel die."""
        try:
            data = RESULTS.get(internal_id) or {}
            ibkr_id = data.get("ibkr_order_id")
            if ibkr_id is None:
                return {"ok": False, "error": "ibkr_order_id unknown"}
            def _cancel_one(ib: IB, oid: int):
                # probeer trade → anders directe cancel op losse Order(orderId=...)
                tr = next((t for t in ib.trades() if getattr(t.order, "orderId", None) == int(oid)), None)
                if tr:
                    ib.cancelOrder(tr.order)
                    return True
                o = Order()
                o.orderId = int(oid)
                ib.cancelOrder(o)
                return True
            ok = _runner.run(_cancel_one, int(ibkr_id))
            return {"ok": bool(ok)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

ADAPTER = IbkrAdapter()

# -------------------------
# Module-level helpers for service.py
# -------------------------

def _prime_orders(ib: IB):
    """Zorg dat IB zijn caches vult (open & completed orders)."""
    try:
        ib.reqOpenOrders()
    except Exception:
        pass
    try:
        ib.reqAllOpenOrders()
    except Exception:
        pass
    try:
        ib.reqCompletedOrders(apiOnly=True)
    except Exception:
        pass
    try:
        ib.waitOnUpdate(timeout=1.0)
    except Exception:
        time.sleep(0.2)

def _find_trade_by_order_id(ib: IB, order_id: int):
    for tr in list(ib.openTrades()) + list(ib.trades()):
        try:
            oid = int(getattr(tr.order, "orderId", -1))
        except Exception:
            continue
        if oid == int(order_id):
            return tr
    return None

def get_order_status(order_id: int) -> Optional[str]:
    """
    Geef status string ('submitted'/'filled'/'cancelled'/...) of None wanneer onbekend.
    Draait in dezelfde IB-verbinding (geen tweede connectie).
    """
    def _inner(ib: IB, oid: int):
        _prime_orders(ib)
        tr = _find_trade_by_order_id(ib, oid)
        if tr is not None:
            st = getattr(tr.orderStatus, "status", None)
            return str(st).lower() if st else None
        # probeer completed list (ib.insync expose kan verschillen)
        try:
            completed = getattr(ib, "completedOrders", None)
            comp_list = completed() if callable(completed) else []
        except Exception:
            comp_list = []
        for co in comp_list or []:
            try:
                coid = int(getattr(getattr(co, "order", None), "orderId", -1))
            except Exception:
                continue
            if coid == int(oid):
                st = getattr(getattr(co, "orderState", None), "status", None) or getattr(co, "status", None)
                return str(st).lower() if st else "completed"
        return None
    return _runner.run(_inner, int(order_id))

def cancel_bracket(ib_ids: List[int]) -> None:
    """
    Cancel alle IB orderIds in dezelfde IB-thread/verbinding.
    - Probeert eerst via Trade
    - Indien niet gevonden: directe cancel met Order(orderId=...)
    Raise exception bij falen (service.py vangt en geeft 400).
    """
    if not ib_ids:
        return

    def _inner(ib: IB, ids: List[int]):
        _prime_orders(ib)
        errors: List[str] = []
        for oid in ids:
            tr = _find_trade_by_order_id(ib, int(oid))
            try:
                if tr is not None:
                    ib.cancelOrder(tr.order)
                else:
                    o = Order()
                    o.orderId = int(oid)
                    ib.cancelOrder(o)
            except Exception as exc:
                errors.append(f"orderId {oid}: {exc}")
        if errors:
            raise RuntimeError("; ".join(errors))
        return None

    _runner.run(_inner, [int(x) for x in ib_ids])
