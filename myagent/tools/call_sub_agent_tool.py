from typing import TYPE_CHECKING, Callable

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
    pin: bool = False

    def __init__(
        self,
        name_builder: Callable[[], str],
        llm_client: "LLMClient",
        base_tools_list: "BaseToolsList",
        logger_builder: Callable[[str], "Logger"],
        num_retries: int,
        summarize_num: int,
        summarize_keep_latest_num: int,
    ) -> None:
        self.name_builder = name_builder
        self.llm_client = llm_client
        self.base_tools_list = base_tools_list
        self.logger_builder = logger_builder
        self.num_retries = num_retries
        self.summarize_num = summarize_num
        self.summarize_keep_latest_num = summarize_keep_latest_num

    def invoke(self, query: str) -> str:
        from myagent.agent import ReActAgent
        from myagent.idsep_parser import IDSepParser

        name = self.name_builder()
        idsep_parser = IDSepParser()
        logger = self.logger_builder(name)

        sub_agent = ReActAgent(
            name=name,
            llm_client=self.llm_client,
            tools_list=self.base_tools_list,
            idsep_parser=idsep_parser,
            logger=logger,
            num_retries=self.num_retries,
            summarize_num=self.summarize_num,
            summarize_keep_latest_num=self.summarize_keep_latest_num,
        )

        return sub_agent.run(query)
