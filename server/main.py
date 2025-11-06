from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from server.routers import (
    system_panel,
    localizer,
    data,
    exit_types,
    order_processing,
    order_transmitting,
    results,
    strategy_types,
    editor,
)
from server.modules.order_transmitting.service import start_worker_once
from server.routers import exit_types
from server.routers import strategy_types
from server.routers import strategy_graph

# ---- maak eerst de app ----
app = FastAPI(title="IBKR Server V6")

# ---- lifecycle ----
@app.on_event("startup")
def _startup():
    start_worker_once()

# ---- basic routes ----
@app.get("/api/health")
def health():
    return {"status": "ok"}
app.include_router(strategy_types.router)

@app.get("/", response_class=HTMLResponse)
def home():
    return "<h2>IBKR Server V6 API</h2><p>See /docs for API schema.</p>"

# ---- include routers (na app) ----
app.include_router(system_panel.router)
app.include_router(localizer.router)
app.include_router(data.router)
app.include_router(exit_types.router)
app.include_router(order_processing.router)
app.include_router(order_transmitting.router)
app.include_router(results.router)
app.include_router(strategy_types.router)
app.include_router(editor.router)
app.include_router(exit_types.router)
app.include_router(strategy_graph.router)