from typing import TYPE_CHECKING, Callable, Optional
import copy

from pydantic import BaseModel, Field

from myagent.tools.tool import Tool, ToolResult

if TYPE_CHECKING:
    from myagent.agent import ReActAgent


class SpawnSubAgentTool(Tool):
    name: str = "spawn_sub_agent"
    desc: str = (
        "Invoke a specialized sub-agent to handle complex, multi-step, or intensive sub-tasks. "
        "The sub-agent operates with its own independent reasoning loop and scratchpad, "
        "making it ideal for breaking down massive queries without cluttering the main agent's context."
    )

    class Parameters(BaseModel):
        query: str = Field(
            description=(
                "The specific sub-goal or self-contained task to be executed by the sub-agent. "
                "The sub-agent must fully commit to this objective and exhaust all available steps "
                "to produce a complete and final answer."
            ),
        )

    def __init__(
        self,
        build_sub_agent: Callable[[], "ReActAgent"],
        destroy_sub_agent: Optional[Callable[["ReActAgent"], None]] = None,
    ) -> None:
        self.build_sub_agent = build_sub_agent
        self.destroy_sub_agent = destroy_sub_agent

        self.remind_usage_every_n_tokens = 1 << 16
        self.remind_usage_limit = self.remind_usage_every_n_tokens

    def invoke(self, query: str) -> ToolResult:
        usage = self.agent_env["usage"]
        self.remind_usage_limit = (
            (usage.prompt_tokens + self.remind_usage_every_n_tokens - 1)
            // self.remind_usage_every_n_tokens
            * self.remind_usage_every_n_tokens
        )

        sub_agent = self.build_sub_agent()

        sub_agent.append_user_new_msg(query)
        _, final_answer = sub_agent.run(
            prev_messages=copy.deepcopy(self.agent_env["messages"])
        )

        if self.destroy_sub_agent is not None:
            self.destroy_sub_agent(sub_agent)
        return ToolResult(final_answer)

    def inject(self) -> Optional[str]:
        usage = self.agent_env["usage"]
        if usage.prompt_tokens >= self.remind_usage_limit:
            return (
                f"You have used about {usage.prompt_tokens:,} tokens of context. "
                f"If the remaining task is complex, multi-step, or memory-intensive, "
                f"consider using `{self.name}` to offload work to a sub-agent. "
                f"This creates a fresh, isolated workspace so you don't run out of context."
            )
        return None
