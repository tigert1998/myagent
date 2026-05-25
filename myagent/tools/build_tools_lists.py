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


def build_basic_tools_list():
    return ConcatToolsList(
        ReadFileTool(),
        WriteFileTool(),
        EditFileTool(),
        BashTool(),
        LoadSkillTool(),
        TODOToolsList(),
    )


def build_full_tools_list(
    build_sub_agent: Callable[[], "ReActAgent"],
    destroy_sub_agent: Optional[Callable[["ReActAgent"], None]] = None,
):
    return ConcatToolsList(
        build_basic_tools_list(),
        CallSubAgentTool(build_sub_agent, destroy_sub_agent),
    )
