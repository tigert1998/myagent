from typing import Optional, Any

from pydantic import BaseModel


class ToolResult:
    content: str
    final_answer: Optional[str]

    def __init__(self, content: str, final_answer: Optional[str] = None):
        self.content = content
        self.final_answer = final_answer


class Tool:
    name: str
    desc: str

    class Parameters(BaseModel): ...

    def invoke(self, *args, **kwargs) -> ToolResult:
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
