import re
import os
import importlib
from textwrap import indent

STRATEGIES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "strategy_types", "strategies"
)

VALID_TYPE = {"int": "int", "float": "float", "str": "str"}

def _safe_id(s: str) -> bool:
    return re.fullmatch(r"[a-z0-9_]+", s) is not None

def _strategy_file_path(strategy_id: str) -> str:
    return os.path.abspath(os.path.join(STRATEGIES_DIR, f"{strategy_id}.py"))

def create_strategy_file(strategy_id: str, name: str, fields: list[dict]) -> dict:
    """
    fields: list of {"name": str, "type": "int|float|str", "gt": number|None, "description": str|None}
    """
    if not _safe_id(strategy_id):
        return {"ok": False, "error": "strategy_id alleen lowercase, cijfers en _"}
    path = _strategy_file_path(strategy_id)
    if os.path.exists(path):
        return {"ok": False, "error": f"bestaat al: {path}"}

    # build Pydantic Params model
    lines = ["from pydantic import BaseModel, Field",
             "from ..base import BaseStrategy",
             "from ..registry import register",
             "",
             "class Params(BaseModel):"]
    if not fields:
        lines.append("    pass")
    else:
        for f in fields:
            fname = f.get("name")
            ftype = VALID_TYPE.get(str(f.get("type", "")))
            if not fname or not ftype:
                return {"ok": False, "error": f"ongeldig veld: {f}"}
            extras = []
            if ftype in ("int", "float") and f.get("gt") is not None:
                extras.append(f"gt={float(f['gt'])}")
            if f.get("description"):
                extras.append(f'description="{str(f["description"]).replace(chr(34), r"\\\"")}"')
            extra = ", ".join(extras)
            if extra:
                line = f"    {fname}: {ftype} = Field({extra})"
            else:
                line = f"    {fname}: {ftype}"
            lines.append(line)

    # Strategy class
    cls = f"""
class {strategy_id.title().replace('_','')} (BaseStrategy):
    id = "{strategy_id}"
    name = "{name}"
    Params = Params

register({strategy_id.title().replace('_','')})
""".lstrip("\n")

    content = "\n".join(lines) + "\n\n" + cls

    # ensure folder exists
    os.makedirs(STRATEGIES_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    # hot-load the new module so it appears immediately
    importlib.invalidate_caches()
    mod_name = f"server.modules.strategy_types.strategies.{strategy_id}"
    importlib.import_module(mod_name)

    return {"ok": True, "path": path, "module": mod_name}
