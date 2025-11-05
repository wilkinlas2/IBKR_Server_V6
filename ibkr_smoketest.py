"""
Losse test buiten FastAPI om te verifiëren dat IB connect + order werkt.
Run:
  .\.venv\Scripts\python.exe ibkr_smoketest.py
Zet vooraf (zelfde venster):
  $env:IBKR_HOST="127.0.0.1"; $env:IBKR_PORT="7497"; $env:IBKR_CLIENT_ID="9"
"""
import os, time
from typing import Any

try:
    from ib_insync import IB, Stock, MarketOrder  # type: ignore
except Exception as e:
    print("ib_insync import failed:", e)
    raise

HOST = os.getenv("IBKR_HOST", "127.0.0.1")
PORT = int(os.getenv("IBKR_PORT", "7497"))
CID  = int(os.getenv("IBKR_CLIENT_ID", "9"))

ib = IB()
print(f"Connecting to {HOST}:{PORT} cid={CID} ...")
ok = ib.connect(HOST, PORT, clientId=CID, readonly=False)
print("Connected:", ok, "isConnected:", ib.isConnected())
if not ok:
    raise SystemExit("IB.connect failed")

# Contract kwalificeren
contract = ib.qualifyContracts(Stock("AAPL", "SMART", "USD"))[0]
print("Qualified:", contract)

# Plaats testorder (GEEN real money als je in Paper zit)
order = MarketOrder("BUY", 1)
trade = ib.placeOrder(contract, order)
print("Placed; orderId:", trade.order.orderId, "status:", trade.orderStatus.status)

# Wacht even op update events
time.sleep(2.0)
print("Now status:", trade.orderStatus.status, "filled:", trade.filled, "avgPrice:", trade.orderStatus.avgFillPrice)

print("OK. Done.")
