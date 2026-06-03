from typing import Any

from myagent.tools.tool import Tool, ToolResult


class ToolsList:
    tools: list[Tool]

    def __init__(self, tools: list[Tool]):
        self.tools = tools

    def schema(self) -> list[dict[str, Any]]:
        return [t.schema() for t in self.tools]

    def parse_args(self, name: str, args: str) -> Any:
        for tool in self.tools:
            if name == tool.name:
                return tool.Parameters.model_validate_json(args)

        raise ValueError(f'Invalid tool name "{name}"')

    def execute_tool(self, tool: str, args: dict[str, Any]) -> ToolResult:
        tool_found: bool = False
        for t in self.tools:
            if tool == t.name:
                tool_found = True
                result = t.invoke(**args)
                for_agent = result.for_agent
                for_user = result.for_user
                break

        if not tool_found:
            raise ValueError(f'Invalid tool name "{tool}"')

        additional_output: list[str] = []
        for t in self.tools:
            inject = t.inject()
            if inject is not None:
                additional_output.append(inject)

        if len(additional_output) > 0:
            for_agent = for_agent + "\n\n" + "\n\n".join(additional_output)

        return ToolResult(for_agent, for_user)


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
