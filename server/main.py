from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="IBKR Server V6")

# ---- health & root ----
@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
def home():
    return "<h2>IBKR Server V6 API</h2><p>See /docs for API schema.</p>"

# ---- plek voor toekomstige routers (per foto 2) ----
# from .routers import system_panel, localizer, data, order_processing, strategy_types, editor, exit_types, order_transmitting, results
# app.include_router(system_panel.router, prefix="/system-panel", tags=["system_panel"])
