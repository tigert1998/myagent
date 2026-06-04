from myagent.tools.basic_tools import (
    ReadFileTool,
    WriteFileTool,
    EditFileTool,
    BashTool,
    LoadSkillTool,
)
from myagent.tools.todo_tool import WriteTODOTool
from myagent.tools.tools_list import ConcatToolsList


def build_basic_tools_list() -> ConcatToolsList:
    return ConcatToolsList(
        ReadFileTool(),
        WriteFileTool(),
        EditFileTool(),
        BashTool(),
        LoadSkillTool(),
        WriteTODOTool(),
    )
