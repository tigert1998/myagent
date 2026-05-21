import subprocess
import json
import inspect
import os
import os.path as osp

import frontmatter


def _json_returns(obj):
    return (
        "```json\n"
        + json.dumps(
            obj,
            indent=4,
            ensure_ascii=False,
        )
        + "\n```\n"
    )


class ReadFileTool:
    name = "read_file"
    desc = """Reads and returns a specific chunk of lines from a text file.

Supports pagination by specifying 'offset' (starting line number, 0-based) and 'limit' (number of lines to read). 
Defaults to reading the first 2000 lines. Ideal for inspecting large files, configurations,
or code without loading the entire content into memory. Handles UTF-8 encoding.
"""
    pin = False

    def invoke(self, path: str, offset: str = "0", limit: str = "2000") -> str:
        offset = int(offset)
        limit = int(limit)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            lines = content.split("\n")
            return "\n".join(lines[offset : offset + limit])


class WriteFileTool:
    name = "write_file"
    desc = """Overwrites a file with the provided text content.
WARNING: This will replace the entire file content."""
    pin = False

    def invoke(self, path: str, content: str) -> str:
        with open(path, "w") as f:
            f.write(content)
        return _json_returns({"success": True})


class EditFileTool:
    name = "edit_file"

    desc = """Use this tool to replace a specific section of text within a file with new content.
This is the primary way to modify code or text files.

CRITICAL INSTRUCTIONS:
Exact Match: The old_str must be an exact, character-for-character match of a unique block in the file.
Include surrounding whitespace or indentation if necessary to ensure uniqueness.
Uniqueness: Ensure the old_str appears only ONCE in the file to avoid accidental mass replacements.
If the string appears multiple times, include more context (e.g., surrounding lines) in old_str.
No Partial Matches: Do not guess; copy the exact text from the file reading tools.
Path: Provide the relative or absolute path to the target file.
"""

    pin = False

    def invoke(self, path: str, old_str: str, new_str: str) -> str:
        with open(path, "r") as f:
            content = f.read()
        num_matches = content.count(old_str)
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
    name = "bash"
    desc = """Executes a bash command with timeout from the command line.
Returns the standard output, standard error, and return code in a JSON block.
"""
    pin = False

    def invoke(self, cmd: str, timeout: str) -> str:
        timeout_num = float(timeout)
        p = subprocess.Popen(
            cmd,
            shell=True,
            executable="/bin/bash",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = p.communicate(timeout=timeout_num)
        return _json_returns(
            {
                "stdout": stdout,
                "stderr": stderr,
                "returncode": p.returncode,
            }
        )


class AskUserTool:
    name = "ask_user"

    desc = """Request additional input or clarification directly from the user.

This tool pauses the current workflow and waits for the user to provide
instructions, missing information, confirmation, or feedback required to
continue the task.
"""

    pin = False

    def __init__(self, send_msg, request_msg):
        self.send_msg = send_msg
        self.request_msg = request_msg

    def invoke(self, question: str) -> str:
        self.send_msg(question)
        return self.request_msg()


class NotifyUserTool:
    name = "notify_user"

    desc = """Send an informational message or progress update to the user.

This tool is used to communicate important status updates, execution results,
next steps, warnings, or other non-interactive messages during task execution.
Unlike `ask_user`, this tool does not wait for a response and simply informs
the user about the current state of the workflow.
"""

    pin = False

    def __init__(self, send_msg):
        self.send_msg = send_msg

    def invoke(self, content: str) -> str:
        self.send_msg(content)
        return _json_returns(
            {
                "success": True,
            }
        )


def _skill_doc_inject_envs(content, skill_dir):
    return content.replace("${CLAUDE_SKILL_DIR}", skill_dir)


class LoadSkillTool:
    name = "load_skill"

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
        ls = []
        folder = osp.expanduser("~/.agents/skills")
        skills = os.listdir(folder)
        for skill in skills:
            skill_md_path = osp.join(folder, skill, "SKILL.md")
            if not osp.isfile(skill_md_path):
                continue
            with open(skill_md_path, "r") as f:
                md = frontmatter.load(f)
            metadata = (
                "---\n"
                + "\n".join([f"{k}: {v}" for k, v in md.metadata.items()])
                + "\n---\n"
            )
            skill_path = osp.join(folder, skill)
            ls.append(f"{skill_path}\n{metadata}")
        return "\n\n".join(ls) + "\n"

    pin = True

    def invoke(self, skill_name: str) -> str:
        folder = osp.expanduser(osp.join("~/.agents/skills", skill_name))
        skill_md_path = osp.join(folder, "SKILL.md")
        with open(skill_md_path, "r") as f:
            md = frontmatter.load(f)
        content = _skill_doc_inject_envs(md.content, folder)
        return content


class ToolsList:
    @staticmethod
    def _register_tools(send_msg, request_msg):
        ls = []
        tools = [
            ReadFileTool(),
            WriteFileTool(),
            EditFileTool(),
            AskUserTool(send_msg, request_msg),
            NotifyUserTool(send_msg),
            LoadSkillTool(),
            BashTool(),
        ]
        for tool in tools:
            desc = f'def {tool.name}{inspect.signature(tool.invoke)}\n\t"""{tool.desc}"""\n\tpass\n'
            ls.append(
                {
                    "name": tool.name,
                    "desc": desc,
                    "func": tool.invoke,
                    "pin": tool.pin,
                }
            )
        return ls

    def __init__(self, send_msg, request_msg):
        self._tools_list = ToolsList._register_tools(send_msg, request_msg)

    def tools_list_desc(self):
        return (
            "```python\n" + "\n\n".join([i["desc"] for i in self._tools_list]) + "```"
        )

    def execute_tool(self, name: str, args: dict):
        for tool in self._tools_list:
            if name != tool["name"]:
                continue
            func = tool["func"]
            return func(**args), tool["pin"]

        raise ValueError(f'Invalid tool name "{name}"')
