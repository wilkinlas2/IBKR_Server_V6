# IBKR Quick Start (local)

Set in PowerShell (same session):

$env:IBKR_ADAPTER = "ibkr"
$env:IBKR_HOST    = "127.0.0.1"
$env:IBKR_PORT    = "7497"   # paper: 7497, live: 7496
$env:IBKR_CLIENT_ID = "9"

uvicorn server.main:app --reload

# smoketest
.\.venv\Scripts\python.exe ibkr_smoketest.py
