from typing import Callable, TYPE_CHECKING

from myagent.tools.call_sub_agent_tool import CallSubAgentTool
from myagent.tools.tools_list import ToolsList, BaseToolsList

if TYPE_CHECKING:
    from myagent.loggers import Logger


class FullToolsList(ToolsList):
    def __init__(
        self,
        send_msg: Callable[[str], None],
        name_builder: Callable[[], str],
        llm_client,
        logger_builder: Callable[[str], "Logger"],
        num_retries: int = 3,
    ):
        base_tools_list = BaseToolsList(send_msg)
        call_sub_agent_tool = CallSubAgentTool(
            name_builder,
            llm_client,
            send_msg,
            base_tools_list,
            logger_builder,
            num_retries,
        )
        super().__init__(base_tools_list.tools + [call_sub_agent_tool])
