from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from server.modules.strategy_types.service import list_types, get_schema, validate

router = APIRouter(prefix="/strategy-types", tags=["strategy_types"])

@router.get("")
def list_all():
    return {"items": list_types()}

@router.get("/{strategy_id}/schema")
def schema(strategy_id: str):
    s = get_schema(strategy_id)
    if "error" in s:
        raise HTTPException(404, s["error"])
    return s

class ValidateIn(BaseModel):
    params: dict

@router.post("/{strategy_id}/validate")
def validate_params(strategy_id: str, body: ValidateIn):
    ok, msg = validate(strategy_id, body.params)
    if not ok:
        raise HTTPException(400, msg)
    return {"ok": True, "message": "ok"}
