# IBKR_Server_V6

Monorepo volgens architectuur (foto 2).

## Mappen
- frontend/ – HTML pagina's (System Panel UI, HTML Webpages).
- server/
  - main.py – FastAPI bootstrap + routers
  - routers/ – API endpoints
  - modules/
    - system_panel/
    - localizer/
    - data/
    - order_processing/
    - strategy_types/
    - editor/
    - exit_types/
    - order_transmitting/
    - results/
  - logging/ – centrale logging
- tests/ – unit/integration tests
- docs/ – documentatie en diagrammen

## Developer quickstart
```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn server.main:app --reload
