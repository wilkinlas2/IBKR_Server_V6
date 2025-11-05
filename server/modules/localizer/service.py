_LANG = "en"

def get_locale() -> str:
    return _LANG

def set_locale(lang: str) -> None:
    global _LANG
    _LANG = lang
