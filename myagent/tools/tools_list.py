import subprocess
import json
import os
import os.path as osp
from typing import Any, Callable, Literal

import frontmatter
from pydantic import BaseModel, Field

from myagent.tools.tool import Tool, ToolResult


def _json_returns(obj: Any) -> str:
    return (
        "```json\n"
        + json.dumps(
            obj,
            indent=4,
            ensure_ascii=False,
        )
        + "\n```\n"
    )


class ToolsList:
    tools: list[Tool]

    def __init__(self, tools: list[Tool]):
        self.tools = tools

    def schema(self) -> list[dict[str, Any]]:
        return [t.schema() for t in self.tools]

    def parse_args(self, name: str, args: str):
        for tool in self.tools:
            if name == tool.name:
                return tool.Parameters.model_validate_json(args)

        raise ValueError(f'Invalid tool name "{name}"')

    def execute_tool(self, name: str, args: dict[str, Any]) -> ToolResult:
        tool_found: bool = False
        for tool in self.tools:
            if name == tool.name:
                tool_found = True
                result = tool.invoke(**args)
                output = result.content
                final_answer = result.final_answer
                break

        if not tool_found:
            raise ValueError(f'Invalid tool name "{name}"')

        additional_output: list[str] = []
        for tool in self.tools:
            inject = tool.inject()
            if inject is not None:
                additional_output.append(inject)

        output = output + "\n\n" + "\n\n".join(additional_output)

        return ToolResult(output, final_answer)


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

    def __init__(
        self, planning_state: PlanningState, send_msg: Callable[[str], None]
    ) -> None:
        super().__init__(planning_state)
        self.send_msg = send_msg

    def invoke(self, todo_items: list[dict[str, str]]) -> ToolResult:
        self.planning_state.update(todo_items)
        self.planning_state.rounds_since_update = 0
        self.send_msg(self.render_for_user())
        return ToolResult(_json_returns({"success": True}))

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


class ReadFileTool(Tool):
    name: str = "read_file"
    desc: str = (
        "Reads and returns a specific chunk of lines from a text file. "
        "Supports pagination by specifying 'offset' (starting line number, 1-based) and 'limit' (number of lines to read). "
        "Defaults to reading the first 2000 lines. Ideal for inspecting large files, configurations, "
        "or code without loading the entire content into memory. Handles UTF-8 encoding. "
    )

    class Parameters(BaseModel):
        path: str
        offset: int = 1
        limit: int = 2000

    def invoke(self, path: str, offset: int, limit: int) -> ToolResult:
        l: int = int(offset) - 1
        r: int = l + int(limit)
        with open(path, "r", encoding="utf-8") as f:
            content: str = f.read()
            lines: list[str] = content.split("\n")
            lines = lines[l:r]
            num_digits = len(str(r))
            return ToolResult(
                f"File: {path}\n```\n"
                + "\n".join(
                    [
                        f"{repr(i + l + 1).rjust(num_digits)} | {line}"
                        for i, line in enumerate(lines)
                    ]
                )
                + "\n```\n",
            )


class WriteFileTool(Tool):
    name: str = "write_file"
    desc: str = (
        "Overwrites a file with the provided text content. Handles UTF-8 encoding. "
        "WARNING: This will replace the entire file content."
    )

    class Parameters(BaseModel):
        path: str
        content: str

    def invoke(self, path: str, content: str) -> ToolResult:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return ToolResult(_json_returns({"success": True}))


class EditFileTool(Tool):
    name: str = "edit_file"

    desc: str = (
        "Use this tool to replace a specific section of text within a file with new content. "
        "Handles UTF-8 encoding. This is the primary way to modify code or text files. "
        "CRITICAL INSTRUCTIONS: "
        "Exact Match: The old_str must be an exact, character-for-character match of a unique block in the file. "
        "Include surrounding whitespace or indentation if necessary to ensure uniqueness. "
        "Uniqueness: Ensure the old_str appears only ONCE in the file to avoid accidental mass replacements. "
        "If the string appears multiple times, include more context (e.g., surrounding lines) in old_str. "
        "No Partial Matches: Do not guess; copy the exact text from the file reading tools. "
        "Path: Provide the relative or absolute path to the target file."
    )

    class Parameters(BaseModel):
        path: str
        old_str: str
        new_str: str

    def invoke(self, path: str, old_str: str, new_str: str) -> ToolResult:
        with open(path, "r", encoding="utf-8") as f:
            content: str = f.read()
        num_matches: int = content.count(old_str)
        if num_matches != 1:
            return ToolResult(
                _json_returns(
                    {
                        "success": False,
                        "num_matches": num_matches,
                        "num_replaces": 0,
                    }
                ),
            )
        content = content.replace(old_str, new_str)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return ToolResult(
            _json_returns(
                {
                    "success": True,
                    "num_matches": num_matches,
                    "num_replaces": num_matches,
                }
            ),
        )


class BashTool(Tool):
    name: str = "bash"
    desc: str = (
        "Executes a bash command with timeout from the command line. "
        "Returns the standard output, standard error, and return code in a JSON block."
    )

    class Parameters(BaseModel):
        cmd: str
        timeout: float = 10

    def invoke(self, cmd: str, timeout: float) -> ToolResult:
        p: subprocess.Popen[str] = subprocess.Popen(
            cmd,
            shell=True,
            executable="/bin/bash",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout: str
        stderr: str
        stdout, stderr = p.communicate(timeout=timeout)
        return ToolResult(
            _json_returns(
                {
                    "stdout": stdout,
                    "stderr": stderr,
                    "returncode": p.returncode,
                }
            ),
        )


class AskUserTool(Tool):
    name: str = "ask_user"

    desc: str = (
        "Request additional input or clarification directly from the user. "
        "CRITICAL: This tool is the ONLY mechanism to ask the user for information. "
        "Failure to use this tool when user input is needed will result in a failed request "
        "and an unexpected early session termination.\n\n"
        "Example:\n"
        "User: Schedule a meeting with John.\n"
        'Assistant: ask_user(question="I\'d be happy to help! Could you please specify the date and time for the meeting?")'
    )

    class Parameters(BaseModel):
        question: str

    send_msg: Callable[[str], None]
    request_msg: Callable[[], str]

    def __init__(
        self, send_msg: Callable[[str], None], request_msg: Callable[[], str]
    ) -> None:
        self.send_msg = send_msg
        self.request_msg = request_msg

    def invoke(self, question: str) -> ToolResult:
        self.send_msg(question)
        return ToolResult("> " + self.request_msg() + "\n")


class NotifyUserTool(Tool):
    name: str = "notify_user"

    desc: str = (
        "Sends an informational message or progress update to the user. "
        "This tool enhances workflow transparency by communicating task status, "
        "execution results, upcoming steps, or warnings. Unlike `ask_user`, "
        "this is a one-way communication tool and does not wait for user input."
    )

    send_msg: Callable[[str], None]

    class Parameters(BaseModel):
        content: str = Field(
            description="The descriptive text message to be conveyed to the user."
        )
        finish: bool = Field(
            default=False,
            description="A completion flag. Set to True if and only if the entire task is finished.",
        )

    def __init__(self, send_msg: Callable[[str], None]) -> None:
        self.send_msg = send_msg

    def invoke(self, content: str, finish: bool) -> ToolResult:
        self.send_msg(content)
        return ToolResult(_json_returns({"success": True}), content if finish else None)


def _skill_doc_inject_envs(content: str, skill_dir: str) -> str:
    return content.replace("${CLAUDE_SKILL_DIR}", skill_dir)


class LoadSkillTool(Tool):
    name: str = "load_skill"

    def __init__(self) -> None:
        super().__init__()
        self.desc = (
            "Load the `SKILL.md` of a specific skill by name. "
            "A skill is a reusable capability package that typically includes a `SKILL.md` file "
            "describing what the skill does, when it should be used, and any related instructions or requirements. "
            "It contains detailed workflows, examples, domain knowledge, "
            "or execution guidance that help the agent perform specific tasks. "
            "You can retrieve and reference the full contents of the skill’s `SKILL.md` file "
            "for execution or further guidance. "
            "The list of skills:\n\n"
            f"{self.list_of_skills()}"
        )

    class Parameters(BaseModel):
        skill_name: str

    def list_of_skills(self) -> str:
        ls: list[str] = []
        folder: str = osp.expanduser("~/.agents/skills")
        skills: list[str] = os.listdir(folder)
        for skill in skills:
            skill_md_path: str = osp.join(folder, skill, "SKILL.md")
            if not osp.isfile(skill_md_path):
                continue
            with open(skill_md_path, "r") as f:
                md: frontmatter.Post = frontmatter.load(f)
            metadata: str = (
                "---\n"
                + "\n".join([f"{k}: {v}" for k, v in md.metadata.items()])
                + "\n---\n"
            )
            skill_path: str = osp.join(folder, skill)
            ls.append(f"Skill path: {skill_path}\n{metadata}")
        return "\n\n".join(ls) + "\n"

    def invoke(self, skill_name: str) -> ToolResult:
        folder: str = osp.expanduser(osp.join("~/.agents/skills", skill_name))
        skill_md_path: str = osp.join(folder, "SKILL.md")
        with open(skill_md_path, "r") as f:
            md: frontmatter.Post = frontmatter.load(f)
        content: str = _skill_doc_inject_envs(md.content, folder)
        return ToolResult(content)


class BaseToolsList(ToolsList):
    def __init__(
        self, send_msg: Callable[[str], None], request_msg: Callable[[], str]
    ) -> None:
        super().__init__(
            [
                ReadFileTool(),
                WriteFileTool(),
                EditFileTool(),
                AskUserTool(send_msg, request_msg),
                NotifyUserTool(send_msg),
                LoadSkillTool(),
                BashTool(),
            ]
            + TODOToolsList(send_msg).tools
        )
