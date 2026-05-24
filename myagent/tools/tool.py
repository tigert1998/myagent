from typing import Optional, Any

from pydantic import BaseModel


class Tool:
    name: str
    desc: str

    class Parameters(BaseModel): ...

    def invoke(self, *args, **kwargs) -> tuple[str, bool]:
        raise NotImplementedError()

    def inject(self) -> Optional[str]:
        return None

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.desc,
                "parameters": self.Parameters.model_json_schema(),
            },
        }
