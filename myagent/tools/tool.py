import inspect
from typing import Optional, Any


class Tool:
    name: str
    desc: str

    def invoke(self, *args, **kwargs) -> str:
        raise NotImplementedError()

    def inject(self) -> Optional[str]:
        return None

    def schema(self) -> dict[str, Any]:
        def annotation_to_str(annotation):
            if annotation == str:
                return "string"
            elif annotation == int:
                return "integer"
            elif annotation == float:
                return "number"
            elif annotation == bool:
                return "boolean"
            raise ValueError(f"Invalid function call parameter type {annotation}")

        sig = inspect.signature(self.invoke)
        properties = {
            param.name: {"type": annotation_to_str(param.annotation)}
            for param in sig.parameters.values()
        }
        required = [
            param.name
            for param in sig.parameters.values()
            if param.default is inspect.Parameter.empty
        ]
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.desc,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }
