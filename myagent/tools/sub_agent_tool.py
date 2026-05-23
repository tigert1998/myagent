from typing import TYPE_CHECKING

from myagent.tools.tool import Tool

if TYPE_CHECKING:
    from myagent.tools.tools_list import ToolsList
    from myagent.llm_client import LLMClient
    from myagent.loggers import Logger


class CallSubAgentTool(Tool):
    name: str = "call_subagent"
    desc: str = ""
    pin: bool = False

    def __init__(
        self,
        llm_client: "LLMClient",
        base_tools_list: "ToolsList",
        logger: "Logger",
        num_retries: int = 3,
    ) -> None:
        self.llm_client = llm_client
        self.base_tools_list = base_tools_list
        self.logger = logger
        self.num_retries = num_retries

    def invoke(self, query: str) -> str:
        from myagent.agent import ReActAgent
        from myagent.idsep_parser import IDSepParser

        idsep_parser = IDSepParser()

        sub_agent = ReActAgent(
            name="SubAgent",
            llm_client=self.llm_client,
            tools_list=self.base_tools_list,
            idsep_parser=idsep_parser,
            logger=self.logger,
            num_retries=self.num_retries,
        )

        return sub_agent.run(query)
