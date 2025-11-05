from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from server.modules.editor.service import create_strategy_file
from server.modules.strategy_types.service import list_types

router = APIRouter(prefix="/editor", tags=["editor"])

class FieldIn(BaseModel):
    name: str
    type: str  # "int" | "float" | "str"
    gt: float | None = None
    description: str | None = None

class CreateStrategyIn(BaseModel):
    strategy_id: str
    name: str
    fields: list[FieldIn] = []

@router.post("/strategy/create")
def create_strategy(body: CreateStrategyIn):
    res = create_strategy_file(body.strategy_id, body.name, [f.dict() for f in body.fields])
    if not res.get("ok"):
        raise HTTPException(400, res.get("error", "unknown error"))
    # return updated list for convenience
    return {"created": res, "available": list_types()}
