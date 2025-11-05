from fastapi import APIRouter

router = APIRouter(prefix="/exit-types", tags=["exit_types"])

EXIT_TYPES = [
    {"code":"TP","name":"Take Profit"},
    {"code":"SL","name":"Stop Loss"},
    {"code":"TS","name":"Trailing Stop"},
]

@router.get("")
def list_exit_types():
    return {"items": EXIT_TYPES}
