from typing import TYPE_CHECKING, Callable, Optional

from pydantic import BaseModel

from myagent.tools.tool import Tool, ToolResult

if TYPE_CHECKING:
    from myagent.agent import ReActAgent


class CallSubAgentTool(Tool):
    name: str = "call_sub_agent"
    desc: str = (
        "Invoke a specialized sub-agent to handle complex, multi-step, or intensive sub-tasks. "
        "The sub-agent operates with its own independent reasoning loop and scratchpad, "
        "making it ideal for breaking down massive queries without cluttering the main agent's context."
    )

    class Parameters(BaseModel):
        query: str

    def __init__(
        self,
        build_sub_agent: Callable[[], "ReActAgent"],
        destroy_sub_agent: Optional[Callable[["ReActAgent"], None]] = None,
    ) -> None:
        self.build_sub_agent = build_sub_agent
        self.destroy_sub_agent = destroy_sub_agent

    def invoke(self, query: str) -> ToolResult:
        sub_agent = self.build_sub_agent()

        sub_agent.append_user_new_msg(query)
        _, final_answer = sub_agent.run()

        if self.destroy_sub_agent is not None:
            self.destroy_sub_agent(sub_agent)
        return ToolResult(final_answer)
