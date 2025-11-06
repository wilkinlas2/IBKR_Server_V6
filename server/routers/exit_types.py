from fastapi import APIRouter, HTTPException, Query
from server.modules.exit_types.service import get_oca_detail, cancel_oca
from server.modules.exit_types.registry import list_active_ocas

router = APIRouter(prefix="/exit-types", tags=["exit-types"])

@router.get("/list-active")
def list_active():
    return {"active": list_active_ocas()}

@router.get("/detail/{oca_group}")
def detail(oca_group: str, refresh: bool = Query(False)):
    return get_oca_detail(oca_group, refresh=refresh)

@router.post("/cancel/{oca_group}")
def cancel(oca_group: str):
    return cancel_oca(oca_group)
