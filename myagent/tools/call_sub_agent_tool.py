from typing import TYPE_CHECKING, Callable

from pydantic import BaseModel, Field

from myagent.tools.tool import Tool

if TYPE_CHECKING:
    from myagent.tools.tools_list import BaseToolsList
    from myagent.llm_client import LLMClient
    from myagent.loggers import Logger


class CallSubAgentTool(Tool):
    name: str = "call_sub_agent"
    desc: str = (
        "Invoke a specialized sub-agent to handle complex, multi-step, or intensive sub-tasks. "
        "The sub-agent operates with its own independent reasoning loop and scratchpad, "
        "making it ideal for breaking down massive queries without cluttering the main agent's context."
    )

    class Parameters(BaseModel):
        query: str = Field(description="")

    def __init__(
        self,
        name_builder: Callable[[], str],
        llm_client: "LLMClient",
        base_tools_list: "BaseToolsList",
        logger_builder: Callable[[str], "Logger"],
    ) -> None:
        self.name_builder = name_builder
        self.llm_client = llm_client
        self.base_tools_list = base_tools_list
        self.logger_builder = logger_builder

    def invoke(self, query: str) -> tuple[str, bool]:
        from myagent.agent import ReActAgent

        name = self.name_builder()
        logger = self.logger_builder(name)

        sub_agent = ReActAgent(
            name=name,
            llm_client=self.llm_client,
            tools_list=self.base_tools_list,
            logger=logger,
        )

        return sub_agent.run(query), False
