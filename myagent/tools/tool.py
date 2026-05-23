import inspect
from typing import Optional, Any, get_origin, get_args, is_typeddict


class Tool:
    name: str
    desc: str

    def invoke(self, *args, **kwargs) -> str:
        raise NotImplementedError()

    def inject(self) -> Optional[str]:
        return None

    @staticmethod
    def function_call_type_schema(py_type: Any) -> dict:
        if py_type is str:
            return {"type": "string"}
        elif py_type is int:
            return {"type": "integer"}
        elif py_type is float:
            return {"type": "number"}
        elif py_type is bool:
            return {"type": "boolean"}

        origin = get_origin(py_type)
        args = get_args(py_type)

        if origin is list:
            if args:
                return {
                    "type": "array",
                    "items": Tool.function_call_type_schema(args[0]),
                }
            return {"type": "array"}

        if is_typeddict(py_type):
            properties = {
                field_name: Tool.function_call_type_schema(field_type)
                for field_name, field_type in py_type.__annotations__.items()
            }
            return {
                "type": "object",
                "properties": properties,
                "required": list(py_type.__annotations__.keys()),
            }

        raise ValueError(f"Invalid function call parameter type {py_type}")

    def schema(self) -> dict[str, Any]:
        sig = inspect.signature(self.invoke)
        properties = {
            param.name: Tool.function_call_type_schema(param.annotation)
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
