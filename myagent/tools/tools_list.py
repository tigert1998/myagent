from typing import Any

from myagent.tools.tool import Tool, ToolResult


class ToolsList:
    tools: list[Tool]

    def __init__(self, tools: list[Tool]):
        self.tools = tools

    def schema(self) -> list[dict[str, Any]]:
        return [t.schema() for t in self.tools]

    def parse_args(self, name: str, args: str) -> dict[str, Any]:
        for tool in self.tools:
            if name == tool.name:
                return tool.Parameters.model_validate_json(args).model_dump()

        raise ValueError(f'Invalid tool name "{name}"')

    def execute_tool(
        self, tool: str, args: dict[str, Any], agent_env: dict[str, Any]
    ) -> ToolResult:
        for t in self.tools:
            t.update_agent_env(agent_env)

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

        for t in self.tools:
            inject = t.inject()
            if inject is not None:
                for_agent.append(inject)

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
