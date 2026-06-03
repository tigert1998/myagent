import json
from typing import Optional, Any

from pydantic import BaseModel


class ToolResult:
    for_agent: list[str]
    for_user: Optional[str]

    def __init__(self, for_agent: str | list[str], for_user: Optional[str] = None):
        if isinstance(for_agent, str):
            self.for_agent = [for_agent]
        else:
            self.for_agent = for_agent
        self.for_user = for_user


class Tool:
    name: str
    desc: str

    class Parameters(BaseModel): ...

    def update_agent_env(self, agent_env: dict[str, Any]) -> None:
        self.agent_env = agent_env

    def invoke(self, *args: Any, **kwargs: Any) -> ToolResult:
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


def json_md(obj: Any) -> str:
    return (
        "```json\n"
        + json.dumps(
            obj,
            indent=4,
            ensure_ascii=False,
        )
        + "\n```\n"
    )
