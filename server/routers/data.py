from fastapi import APIRouter
from server.modules.data.store import get_symbols, get_status

router = APIRouter(prefix="/data", tags=["data"])

@router.get("/symbols")
def symbols():
    return {"symbols": get_symbols()}

@router.get("/status")
def status():
    return get_status()
