from typing import Literal, Optional

from myagent.tools.tool import Tool, json_md, ToolResult
from myagent.tools.tools_list import ToolsList

from pydantic import BaseModel


class PlanItem:
    status: str
    content: str

    def __init__(self, status: str, content: str) -> None:
        self.content: str = content
        self.status: str = status
        self.check()

    def check(self) -> None:
        if self.status not in ["pending", "in_progress", "completed"]:
            raise ValueError(
                f'Invalid status "{self.status}" for TODO item: "{self.content}"'
            )


class PlanningState:
    items: list[PlanItem]
    last_update_round_index: Optional[int]
    reminder_rounds: int

    def __init__(self) -> None:
        self.items = []
        self.last_update_round_index = None
        self.reminder_rounds = 32

    def update(self, todo_items: list[dict[str, str]]) -> None:
        self.items = [
            PlanItem(status=i["status"], content=i["content"]) for i in todo_items
        ]
        try:
            self.check()
        except Exception as e:
            self.items = []
            raise e

    def check(self) -> None:
        count_in_progress: int = 0
        count_completed: int = 0
        count_pending: int = 0
        for i in self.items:
            if i.status == "in_progress":
                count_in_progress += 1
            elif i.status == "completed":
                count_completed += 1
            elif i.status == "pending":
                count_pending += 1
        if count_in_progress == 1 or count_completed == len(self.items):
            return
        raise ValueError(
            f"Invalid TODO state: expected either exactly one item in progress or all items completed. "
            f"Current status: {count_in_progress} in progress, {count_completed} completed, {count_pending} pending."
        )


class TODOTool(Tool):
    planning_state: PlanningState

    def __init__(self, planning_state: PlanningState) -> None:
        self.planning_state: PlanningState = planning_state

    def render_for_agent(self) -> str:
        lines: list[str] = []
        for i, item in enumerate(self.planning_state.items):
            lines.append(f"- [Plan Item #{i + 1}: {item.status}] {item.content}")
        return "\n".join(lines) + "\n"

    def render_for_user(self) -> str:
        renders: list[str] = []
        for i in self.planning_state.items:
            if i.status == "pending":
                s: str = " "
            elif i.status == "in_progress":
                s = ">"
            elif i.status == "completed":
                s = "x"
            renders.append(f"[{s}] {i.content}")
        return "\n".join(renders)


class ReadTODOTool(TODOTool):
    name: str = "read_todo"

    desc: str = (
        "Reads the current state of the TODO list. "
        "Use this tool to check the status of tasks, see what has been completed, "
        "and decide the next steps. This tool does not modify the list."
    )

    class Parameters(BaseModel): ...

    def __init__(self, planning_state: PlanningState) -> None:
        super().__init__(planning_state)

    def invoke(self) -> ToolResult:
        return ToolResult(self.render_for_agent())


class WriteTODOTool(TODOTool):
    name: str = "write_todo"

    desc: str = (
        "You have access to TODO tools to help you manage and plan tasks. "
        "Use these tools VERY frequently to ensure that you are tracking your "
        "and giving the user visibility into your progress. "
        "These tools are also EXTREMELY helpful for planning tasks, and for breaking "
        "down larger complex tasks into smaller steps. If you do not use this tool "
        "when planning, you may forget to do important tasks - and that is unacceptable. "
        'There should always be one and only one "in_progress" task in the TODO list. '
        "This action clears all previous items and replaces them with the new parsed items. "
    )

    class Parameters(BaseModel):
        class Item(BaseModel):
            status: Literal["pending", "in_progress", "completed"]
            content: str

        todo_items: list[Item]

    def __init__(self, planning_state: PlanningState) -> None:
        super().__init__(planning_state)

    def invoke(self, todo_items: list[dict[str, str]]) -> ToolResult:
        self.planning_state.update(todo_items)
        self.planning_state.last_update_round_index = len(self.agent_env["messages"])
        return ToolResult(json_md({"success": True}), self.render_for_user())

    def inject(self) -> Optional[str]:
        if self.planning_state.last_update_round_index is None:
            return f"REMINDER: You have not created a todo list yet. Create one with `{self.name}` tool if your task is complicated or involves multiple steps."

        if (
            self.planning_state.last_update_round_index
            + self.planning_state.reminder_rounds
            <= len(self.agent_env["messages"])
        ):
            delta = (
                len(self.agent_env["messages"])
                - self.planning_state.last_update_round_index
            )
            return f"REMINDER: There are {delta} rounds since last plan update. Update your plan with `{self.name}` tool ASAP."

        return None


class TODOToolsList(ToolsList):
    def __init__(self) -> None:
        planning_state = PlanningState()
        super().__init__(
            [
                ReadTODOTool(planning_state),
                WriteTODOTool(planning_state),
            ]
        )
