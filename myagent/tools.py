import subprocess
import json
import inspect
import os
import os.path as osp
from typing import Any, Callable, Dict, List, Optional, Sequence
import csv
import io

import frontmatter


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


class PlanItem:
    content: str
    status: str

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
    items: List[PlanItem]
    rounds_since_update: int
    reminder_rounds: int

    def __init__(self) -> None:
        self.items = []
        self.rounds_since_update = 1
        self.reminder_rounds = 5

    def update(self, todo_csv: str) -> None:
        f: io.StringIO = io.StringIO(todo_csv)
        reader: csv.DictReader[str] = csv.DictReader(f)
        self.items.clear()
        for row in reader:
            self.items.append(PlanItem(row["status"], row["content"]))
        self.check()

    def check(self) -> None:
        count_in_progress: int = 0
        for i in self.items:
            if i.status == "in_progress":
                count_in_progress += 1
        if count_in_progress != 1:
            raise ValueError(
                f"There are {count_in_progress} TODO items in progress. Only one is allowed."
            )


class TODOTool:
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
            else:
                s = "?"
            renders.append(f"[{s}] {i.content}")
        return "\n".join(renders)


class ReadTODOTool(TODOTool):
    name: str = "read_todo"

    desc: str = """Reads the current state of the TODO list.

Use this tool to check the status of tasks, see what has been completed,
and decide the next steps. This tool does not modify the list.
"""

    pin: bool = False

    def __init__(self, planning_state: PlanningState) -> None:
        super().__init__(planning_state)

    def invoke(self) -> str:
        return self.render_for_agent()


class WriteTODOTool(TODOTool):
    name: str = "write_todo"

    desc: str = """You have access to TODO tools to help you manage and plan tasks.
Use these tools VERY frequently to ensure that you are tracking your tasks 
and giving the user visibility into your progress.

These tools are also EXTREMELY helpful for planning tasks, and for breaking 
down larger complex tasks into smaller steps. If you do not use this tool 
when planning, you may forget to do important tasks - and that is unacceptable.

The input MUST be a valid CSV formatted string containing exactly two columns: 'status' and 'content'. 
Example format: 'status,content\\ncompleted,Task A\\npending,Task B\\nin_progress,Task C'.
There should always be one and only one "in_progress" task in the TODO list. 
This action clears all previous items and replaces them with the new parsed items. 
"""

    pin: bool = False
    send_msg: Callable[[str], None]

    def __init__(self, planning_state: PlanningState, send_msg: Callable[[str], None]) -> None:
        super().__init__(planning_state)
        self.send_msg = send_msg

    def invoke(self, todo_csv: str) -> str:
        self.planning_state.update(todo_csv)
        self.planning_state.rounds_since_update = 0
        self.send_msg(self.render_for_user())
        return _json_returns({"success": True})

    def inject(self) -> str:
        if (
            self.planning_state.rounds_since_update
            >= self.planning_state.reminder_rounds
        ):
            output: str = f"REMINDER: there are {self.planning_state.rounds_since_update} rounds since last plan update. Update your plan with {self.name} tool ASAP."
        else:
            output = ""

        self.planning_state.rounds_since_update += 1
        return output


class TODO:
    planning_state: PlanningState
    send_msg: Callable[[str], None]

    def __init__(self, send_msg: Callable[[str], None]) -> None:
        self.planning_state = PlanningState()
        self.send_msg = send_msg

    def tools(self) -> list[ReadTODOTool | WriteTODOTool]:
        return [
            ReadTODOTool(self.planning_state),
            WriteTODOTool(self.planning_state, self.send_msg),
        ]


class ReadFileTool:
    name: str = "read_file"
    desc: str = """Reads and returns a specific chunk of lines from a text file.

Supports pagination by specifying 'offset' (starting line number, 0-based) and 'limit' (number of lines to read). 
Defaults to reading the first 2000 lines. Ideal for inspecting large files, configurations,
or code without loading the entire content into memory. Handles UTF-8 encoding.
"""
    pin: bool = False

    def invoke(self, path: str, offset: str = "0", limit: str = "2000") -> str:
        offset_int: int = int(offset)
        limit_int: int = int(limit)
        with open(path, "r", encoding="utf-8") as f:
            content: str = f.read()
            lines: list[str] = content.split("\n")
            return "```\n" + "\n".join(lines[offset_int : offset_int + limit_int]) + "\n```\n"


class WriteFileTool:
    name: str = "write_file"
    desc: str = """Overwrites a file with the provided text content.
WARNING: This will replace the entire file content."""
    pin: bool = False

    def invoke(self, path: str, content: str) -> str:
        with open(path, "w") as f:
            f.write(content)
        return _json_returns({"success": True})


class EditFileTool:
    name: str = "edit_file"

    desc: str = """Use this tool to replace a specific section of text within a file with new content.
This is the primary way to modify code or text files.

CRITICAL INSTRUCTIONS:
Exact Match: The old_str must be an exact, character-for-character match of a unique block in the file.
Include surrounding whitespace or indentation if necessary to ensure uniqueness.
Uniqueness: Ensure the old_str appears only ONCE in the file to avoid accidental mass replacements.
If the string appears multiple times, include more context (e.g., surrounding lines) in old_str.
No Partial Matches: Do not guess; copy the exact text from the file reading tools.
Path: Provide the relative or absolute path to the target file.
"""

    pin: bool = False

    def invoke(self, path: str, old_str: str, new_str: str) -> str:
        with open(path, "r") as f:
            content: str = f.read()
        num_matches: int = content.count(old_str)
        if num_matches != 1:
            return _json_returns(
                {
                    "success": False,
                    "num_matches": num_matches,
                    "num_replaces": 0,
                }
            )
        content = content.replace(old_str, new_str)
        with open(path, "w") as f:
            f.write(content)
        return _json_returns(
            {
                "success": True,
                "num_matches": num_matches,
                "num_replaces": num_matches,
            }
        )


class BashTool:
    name: str = "bash"
    desc: str = """Executes a bash command with timeout from the command line.
Returns the standard output, standard error, and return code in a JSON block.
"""
    pin: bool = False

    def invoke(self, cmd: str, timeout: str = "10") -> str:
        timeout_num: float = float(timeout)
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
        stdout, stderr = p.communicate(timeout=timeout_num)
        return _json_returns(
            {
                "stdout": stdout,
                "stderr": stderr,
                "returncode": p.returncode,
            }
        )


class AskUserTool:
    name: str = "ask_user"

    desc: str = """Request additional input or clarification directly from the user.

This tool pauses the current workflow and waits for the user to provide
instructions, missing information, confirmation, or feedback required to
continue the task.
"""

    pin: bool = False
    send_msg: Callable[[str], None]
    request_msg: Callable[[], str]

    def __init__(self, send_msg: Callable[[str], None], request_msg: Callable[[], str]) -> None:
        self.send_msg = send_msg
        self.request_msg = request_msg

    def invoke(self, question: str) -> str:
        self.send_msg(question)
        return "> " + self.request_msg() + "\n"


class NotifyUserTool:
    name: str = "notify_user"

    desc: str = """Send an informational message or progress update to the user.

This tool is used to communicate important status updates, execution results,
next steps, warnings, or other non-interactive messages during task execution.
Unlike `ask_user`, this tool does not wait for a response and simply informs
the user about the current state of the workflow.
"""

    pin: bool = False
    send_msg: Callable[[str], None]

    def __init__(self, send_msg: Callable[[str], None]) -> None:
        self.send_msg = send_msg

    def invoke(self, content: str) -> str:
        self.send_msg(content)
        return _json_returns(
            {
                "success": True,
            }
        )


def _skill_doc_inject_envs(content: str, skill_dir: str) -> str:
    return content.replace("${CLAUDE_SKILL_DIR}", skill_dir)


class LoadSkillTool:
    name: str = "load_skill"

    @property
    def desc(self) -> str:
        return f"""Load the `SKILL.md` of a specific skill by name.

A skill is a reusable capability package that typically includes a `SKILL.md` file
describing what the skill does, when it should be used, and any related instructions or requirements.
It contains detailed workflows, examples, domain knowledge,
or execution guidance that help the agent perform specific tasks.
You can retrieve and reference the full contents of the skill’s `SKILL.md` file
for execution or further guidance.

The list of skills:

{self.list_of_skills()}
"""

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
            ls.append(f"{skill_path}\n{metadata}")
        return "\n\n".join(ls) + "\n"

    pin: bool = True

    def invoke(self, skill_name: str) -> str:
        folder: str = osp.expanduser(osp.join("~/.agents/skills", skill_name))
        skill_md_path: str = osp.join(folder, "SKILL.md")
        with open(skill_md_path, "r") as f:
            md: frontmatter.Post = frontmatter.load(f)
        content: str = _skill_doc_inject_envs(md.content, folder)
        return content


class ToolsList:
    _tools_list: list[dict[str, Any]]

    @staticmethod
    def _register_tools(
        send_msg: Callable[[str], None], request_msg: Callable[[], str]
    ) -> list[dict[str, Any]]:
        ls: list[dict[str, Any]] = []
        tools: list[Any] = [
            ReadFileTool(),
            WriteFileTool(),
            EditFileTool(),
            AskUserTool(send_msg, request_msg),
            NotifyUserTool(send_msg),
            LoadSkillTool(),
            BashTool(),
        ] + TODO(send_msg).tools()
        for tool in tools:
            desc: str = f'def {tool.name}{inspect.signature(tool.invoke)}\n\t"""{tool.desc}"""\n\tpass\n'
            ls.append(
                {
                    "name": tool.name,
                    "desc": desc,
                    "func": tool.invoke,
                    "inject": getattr(tool, "inject", None),
                    "pin": tool.pin,
                }
            )
        return ls

    def __init__(self, send_msg: Callable[[str], None], request_msg: Callable[[], str]) -> None:
        self._tools_list = ToolsList._register_tools(send_msg, request_msg)

    def tools_list_desc(self) -> str:
        return (
            "```python\n" + "\n\n".join([i["desc"] for i in self._tools_list]) + "```"
        )

    def execute_tool(self, name: str, args: dict[str, Any]) -> tuple[str, bool]:
        tool_found: bool = False
        func: Optional[Callable[..., str]] = None
        pin: bool = False
        output: str = ""
        for tool in self._tools_list:
            if name == tool["name"]:
                func = tool["func"]
                output = func(**args)
                pin = tool["pin"]
                tool_found = True
                break

        if not tool_found:
            raise ValueError(f'Invalid tool name "{name}"')

        additional_output: list[str] = []
        for tool in self._tools_list:
            if tool["inject"] is not None:
                additional_output.append(tool["inject"]())

        output = output + "\n\n" + "\n\n".join(additional_output)

        return output, pin
