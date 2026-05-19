import subprocess
import json
import inspect
import os
import os.path as osp

from loggers import TerminalLogger

import frontmatter


class BashTool:
    name = "bash"
    desc = "Execute the bash command. Returns stdout, stderr and returncode."

    def invoke(self, cmd: str) -> str:
        p = subprocess.Popen(
            cmd,
            shell=True,
            executable="/bin/bash",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = p.communicate()
        return (
            "```json\n"
            + json.dumps(
                {
                    "stdout": stdout,
                    "stderr": stderr,
                    "returncode": p.returncode,
                },
                indent=4,
                ensure_ascii=False,
            )
            + "\n```\n"
        )


class AskUserTool:
    name = "ask_user"

    desc = """Request additional input or clarification directly from the user.

This tool pauses the current workflow and waits for the user to provide
instructions, missing information, confirmation, or feedback required to
continue the task.
"""

    def invoke(self, question: str) -> str:
        TerminalLogger.instance().prompt("myagent asks", question)
        return TerminalLogger.instance().prompt("Your instruction", None)


class LoadSkillTool:
    name = "load_skill"

    @property
    def desc(self) -> str:
        return """Load the full content of a specific skill by name.

A skill is a reusable capability package that typically includes a `SKILL.md` file
describing what the skill does, when it should be used, and any related instructions or requirements.
It contains detailed workflows, examples, domain knowledge,
or execution guidance that help the agent perform specific tasks.
You can retrieve and reference the full contents of the skill’s `SKILL.md` file
for execution or further guidance.

The list of skills:
""" + self.list_of_skills()

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
            ls.append(metadata)
        return "\n\n".join(ls) + "\n"

    def invoke(self, skill_name: str) -> str:
        folder = osp.expanduser(osp.join("~/.agents/skills", skill_name))
        skill_md_path = osp.join(folder, "SKILL.md")
        with open(skill_md_path, "r") as f:
            md = frontmatter.load(f)
        return md.content


class LoadSkillReferenceTool:
    name = "load_skill_reference"

    desc = """Load an additional reference file from a specific skill.

Skills may include supplementary resources such as documentation, templates,
examples, datasets, or configuration files alongside the main `SKILL.md`.
This tool retrieves the content of a referenced file inside the skill directory
so the agent can access supporting materials required for the task.
"""

    def invoke(self, skill_name: str, path: str) -> str:
        folder = osp.expanduser(osp.join("~/.agents/skills", skill_name))
        with open(osp.join(folder, path), "r") as f:
            return f.read()


class ExecuteSkillBashTool:
    name = "execute_skill_bash"

    desc = """Execute a bash command within the context of a specific skill.

Skills may provide scripts, tools, or local resources that need to be executed
from the command line. This tool runs a bash command with the skill directory
exposed through the `CLAUDE_SKILL_DIR` environment variable, allowing commands
to access files and resources bundled with the skill.

The tool returns the command's standard output, standard error, and exit code.
"""

    def invoke(self, skill_name: str, cmd: str) -> str:
        p = subprocess.Popen(
            cmd,
            shell=True,
            executable="/bin/bash",
            env={
                **os.environ,
                "CLAUDE_SKILL_DIR": osp.expanduser(
                    osp.join("~/.agents/skills", skill_name)
                ),
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = p.communicate()
        return (
            "```json\n"
            + json.dumps(
                {
                    "stdout": stdout,
                    "stderr": stderr,
                    "returncode": p.returncode,
                },
                indent=4,
                ensure_ascii=False,
            )
            + "\n```\n"
        )


def _register_tools():
    ls = []
    tools = [
        AskUserTool(),
        BashTool(),
        LoadSkillTool(),
        LoadSkillReferenceTool(),
        ExecuteSkillBashTool(),
    ]
    for tool in tools:
        desc = f'def {tool.name}{inspect.signature(tool.invoke)}\n\t"""{tool.desc}"""\n\tpass\n'
        ls.append({"name": tool.name, "desc": desc, "func": tool.invoke})
    return ls


def tools_list_desc():
    tools_list = _register_tools()
    return "```python\n" + "\n\n".join([i["desc"] for i in tools_list]) + "```"


def execute_tool(name: str, args: dict):
    tools_list = _register_tools()

    for tool in tools_list:
        if name != tool["name"]:
            continue
        func = tool["func"]
        return func(**args)

    raise ValueError(f'Invalid tool name "{name}"')
