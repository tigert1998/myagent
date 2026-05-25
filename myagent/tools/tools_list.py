from typing import Any

from myagent.tools.tool import Tool


class ToolsList:
    tools: list[Tool]

    def __init__(self, tools: list[Tool]):
        self.tools = tools

    def schema(self) -> list[dict[str, Any]]:
        return [t.schema() for t in self.tools]

    def parse_args(self, name: str, args: str):
        for tool in self.tools:
            if name == tool.name:
                return tool.Parameters.model_validate_json(args)

        raise ValueError(f'Invalid tool name "{name}"')

    def execute_tool(self, name: str, args: dict[str, Any]) -> str:
        tool_found: bool = False
        for tool in self.tools:
            if name == tool.name:
                tool_found = True
                output = tool.invoke(**args)
                break

        if not tool_found:
            raise ValueError(f'Invalid tool name "{name}"')

        additional_output: list[str] = []
        for tool in self.tools:
            inject = tool.inject()
            if inject is not None:
                additional_output.append(inject)

        if len(additional_output) > 0:
            output = output + "\n\n" + "\n\n".join(additional_output)

        return output


class ConcatToolsList(ToolsList):
    def __init__(self, *ls: ToolsList | list[Tool] | Tool):
        tools = []
        for i in ls:
            if isinstance(i, ToolsList):
                tools.extend(i.tools)
            elif isinstance(i, Tool):
                tools.append(i)
            elif isinstance(i, list):
                tools.extend(i)
        super().__init__(tools)
