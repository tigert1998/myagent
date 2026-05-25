from typing import Callable, TYPE_CHECKING, Optional

from myagent.tools.basic_tools import (
    ReadFileTool,
    WriteFileTool,
    EditFileTool,
    BashTool,
    LoadSkillTool,
)
from myagent.tools.todo_tools_list import TODOToolsList
from myagent.tools.tools_list import ConcatToolsList
from myagent.tools.call_sub_agent_tool import CallSubAgentTool

if TYPE_CHECKING:
    from myagent.agent import ReActAgent


def build_basic_tools_list(send_msg: Callable[[str], None]):
    return ConcatToolsList(
        ReadFileTool(),
        WriteFileTool(),
        EditFileTool(),
        BashTool(),
        LoadSkillTool(),
        TODOToolsList(send_msg),
    )


def build_full_tools_list(
    send_msg: Callable[[str], None],
    build_sub_agent: Callable[[], "ReActAgent"],
    destroy_sub_agent: Optional[Callable[["ReActAgent"], None]] = None,
):
    return ConcatToolsList(
        build_basic_tools_list(send_msg),
        CallSubAgentTool(build_sub_agent, destroy_sub_agent),
    )
