from typing import Callable, TYPE_CHECKING

from myagent.tools.call_sub_agent_tool import CallSubAgentTool
from myagent.tools.tools_list import ToolsList, BaseToolsList

if TYPE_CHECKING:
    from myagent.loggers import Logger


class FullToolsList(ToolsList):
    def __init__(
        self,
        send_msg: Callable[[str], None],
        request_msg: Callable[[], str],
        name_builder: Callable[[], str],
        llm_client,
        logger_builder: Callable[[str], "Logger"],
    ):
        base_tools_list = BaseToolsList(send_msg, request_msg)
        call_sub_agent_tool = CallSubAgentTool(
            name_builder,
            llm_client,
            base_tools_list,
            logger_builder,
        )
        super().__init__(base_tools_list.tools + [call_sub_agent_tool])
