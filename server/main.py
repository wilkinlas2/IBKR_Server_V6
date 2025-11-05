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
)

app = FastAPI(title="IBKR Server V6")

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
def home():
    return "<h2>IBKR Server V6 API</h2><p>See /docs for API schema.</p>"

# include routers
app.include_router(system_panel.router)
app.include_router(localizer.router)
app.include_router(data.router)
app.include_router(exit_types.router)
app.include_router(order_processing.router)
app.include_router(order_transmitting.router)
app.include_router(results.router)
