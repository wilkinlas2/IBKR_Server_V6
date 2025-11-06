@'
taskkill /IM python.exe /F 2>$null
taskkill /IM uvicorn.exe /F 2>$null
'@ | Set-Content -Encoding UTF8 .\stop_server.ps1
