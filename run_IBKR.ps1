# run_ibkr.ps1  — start FastAPI with IBKR adapter (paper: 7497)
$ErrorActionPreference = "SilentlyContinue"
taskkill /IM python.exe /F 2>$null
taskkill /IM uvicorn.exe /F 2>$null
$ErrorActionPreference = "Continue"

# always run from project root
Set-Location -Path "C:\Users\Korneel\Desktop\IBKR_Server_V6"

# activate venv
. ".\.venv\Scripts\Activate.ps1"

# set env vars for THIS process (inherited by uvicorn child)
$env:IBKR_ADAPTER   = "ibkr"
$env:IBKR_HOST      = "127.0.0.1"
$env:IBKR_PORT      = "7497"
$env:IBKR_CLIENT_ID = "9"

Write-Host "`nAdapter:$env:IBKR_ADAPTER Host:$env:IBKR_HOST Port:$env:IBKR_PORT ClientId:$env:IBKR_CLIENT_ID`n" -ForegroundColor Cyan
Write-Host "Starting uvicorn on http://127.0.0.1:8000 ..." -ForegroundColor Green

# keep window open after start (run in same process)
uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload --log-level info
