from typing import Literal, Callable

from myagent.tools.tool import Tool, json_md
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
    rounds_since_update: int
    reminder_rounds: int

    def __init__(self) -> None:
        self.items = []
        self.rounds_since_update = 1
        self.reminder_rounds = 5

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
        if len(self.items) == 0:
            return
        count_in_progress: int = 0
        for i in self.items:
            if i.status == "in_progress":
                count_in_progress += 1
        if count_in_progress != 1:
            raise ValueError(
                f"There are {count_in_progress} TODO items in progress. Only one is allowed."
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

    def invoke(self) -> str:
        return self.render_for_agent()


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

    def __init__(
        self, planning_state: PlanningState, send_msg: Callable[[str], None]
    ) -> None:
        super().__init__(planning_state)
        self.send_msg = send_msg

    def invoke(self, todo_items: list[dict[str, str]]) -> str:
        self.planning_state.update(todo_items)
        self.planning_state.rounds_since_update = 0
        self.send_msg(self.render_for_user())
        return json_md({"success": True})

    def inject(self) -> str:
        if (
            self.planning_state.rounds_since_update
            >= self.planning_state.reminder_rounds
        ):
            if len(self.planning_state.items) == 0:
                output = f"REMINDER: You have not created a todo list yet. Create one with `{self.name}` tool if your task is complicated or involves multiple steps."
            else:
                output = f"REMINDER: There are {self.planning_state.rounds_since_update} rounds since last plan update. Update your plan with `{self.name}` tool ASAP."
        else:
            output = ""

        self.planning_state.rounds_since_update += 1
        return output


class TODOToolsList(ToolsList):
    def __init__(self, send_msg: Callable[[str], None]) -> None:
        planning_state = PlanningState()
        super().__init__(
            [
                ReadTODOTool(planning_state),
                WriteTODOTool(planning_state, send_msg),
            ]
        )
