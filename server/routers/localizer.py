from fastapi import APIRouter
from pydantic import BaseModel
from server.modules.localizer.service import get_locale, set_locale

router = APIRouter(prefix="/localizer", tags=["localizer"])

class LocaleIn(BaseModel):
    lang: str

@router.get("/current")
def current():
    return {"lang": get_locale()}

@router.post("/set")
def set_lang(body: LocaleIn):
    set_locale(body.lang)
    return {"ok": True, "lang": get_locale()}
