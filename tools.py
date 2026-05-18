import subprocess
import json
import inspect
import os
import os.path as osp

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
        return json.dumps(
            {
                "stdout": stdout,
                "stderr": stderr,
                "returncode": p.returncode,
            },
            ensure_ascii=False,
        )


class GetSkillsListTool:
    name = "get_skills_list"

    desc = """Read metadata from all installed skills.

A skill is a reusable capability package for you, usually containing
a `SKILL.md` file that describes what the skill does, when it should be used,
and any related instructions or requirements.

This tool scans all skills, extracts their metadata, and returns
a combined list of skill metadata for skill discovery and selection.
"""

    def invoke(self) -> str:
        ls = []
        folder = osp.expanduser("~/.myagent/skills")
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
        return "\n\n".join(ls)


class LoadSkillTool:
    name = "load_skill"

    desc = """Load the full content of a specific skill by name.

A skill contains detailed instructions, workflows, examples, or domain knowledge
that help the agent perform a particular task. After discovering available skills
through their metadata, this tool can be used to retrieve the complete content
from the skill for execution or reference.
"""

    def invoke(self, name: str) -> str:
        folder = osp.expanduser(osp.join("~/.myagent/skills", name))
        skill_md_path = osp.join(folder, "SKILL.md")
        with open(skill_md_path, "r") as f:
            md = frontmatter.load(f)
        return md.content


def _register_tools():
    ls = []
    tools = [
        BashTool(),
        GetSkillsListTool(),
        LoadSkillTool(),
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
