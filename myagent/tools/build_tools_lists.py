from myagent.tools.basic_tools import (
    ReadFileTool,
    WriteFileTool,
    EditFileTool,
    BashTool,
    LoadSkillTool,
)
from myagent.tools.todo_tools_list import TODOToolsList
from myagent.tools.tools_list import ConcatToolsList


def build_basic_tools_list() -> ConcatToolsList:
    return ConcatToolsList(
        ReadFileTool(),
        WriteFileTool(),
        EditFileTool(),
        BashTool(),
        LoadSkillTool(),
        TODOToolsList(),
    )
