from pydantic import BaseModel

class BaseStrategy:
    """Minimal strategy interface."""
    id: str = "base"
    name: str = "Base Strategy"
    Params: type[BaseModel] = BaseModel  # override in child

    @classmethod
    def schema(cls) -> dict:
        return cls.Params.model_json_schema()

    @classmethod
    def validate_params(cls, data: dict) -> tuple[bool, str]:
        try:
            cls.Params(**data)
            return True, "ok"
        except Exception as e:
            return False, str(e)
