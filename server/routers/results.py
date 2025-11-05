from fastapi import APIRouter
from server.modules.results.service import get_result

router = APIRouter(prefix="/results", tags=["results"])

@router.get("/{order_id}")
def by_id(order_id: str):
    return get_result(order_id)
