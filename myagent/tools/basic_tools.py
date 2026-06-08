import os
import os.path as osp
import subprocess
import signal
from typing import Optional

from pydantic import BaseModel, Field
import frontmatter

from myagent.utils import shorten
from myagent.tools.tool import json_md, Tool, ToolResult


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
        if offset <= 0:
            raise ValueError("Offset must be a positive integer greater than 0.")
        if limit <= 0:
            raise ValueError("Limit must be a positive integer greater than 0.")
        max_length: int = 1 << 16
        with open(path, "r", encoding="utf-8") as f:
            content: str = f.read()
        content_lines: list[str] = content.split("\n")
        l: int = offset - 1
        if l >= len(content_lines):
            return ToolResult(
                "The requested offset exceeds the total number of lines in the file.",
                f'File "{path}" is empty or offset out of range.',
            )
        r: int = min(l + limit, len(content_lines))

        lines: list[str] = []
        length = 0
        new_line_len = 0
        for i in range(l, r):
            truncate = max_length < length + new_line_len + len(content_lines[i])
            lines.append(content_lines[i][: max_length - length - new_line_len])
            length += new_line_len + len(lines[-1])
            new_line_len = 1
            if length >= max_length:
                break
        notices = []
        if i < r - 1:
            notices.append(
                f"Only the first {len(lines)} lines were read because the tool's maximum size limit ({max_length} characters) was reached."
            )
        if truncate:
            notices.append("The last line was truncated due to length limitations.")
        notice = " ".join(notices)

        num_digits = len(str(i + 1))
        return ToolResult(
            f"File: {path}\n```\n"
            + "\n".join(
                [
                    f"{str(i + l + 1).rjust(num_digits)} | {line}"
                    for i, line in enumerate(lines)
                ]
            )
            + f"\n```\n{notice}",
            f'Successfully read "{path}".',
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
        return ToolResult(json_md({"success": True}), f'Successfully write "{path}".')


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
                json_md(
                    {
                        "success": False,
                        "num_matches": num_matches,
                        "num_replaces": 0,
                    }
                ),
                f'Failed to edit "{path}": found {num_matches} matches.',
            )

        content = content.replace(old_str, new_str)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return ToolResult(
            json_md(
                {
                    "success": True,
                    "num_matches": num_matches,
                    "num_replaces": num_matches,
                }
            ),
            f'Successfully edit "{path}".',
        )


class BashTool(Tool):
    name: str = "bash"
    desc: str = (
        "Executes a bash command with timeout from the command line. "
        "Returns the standard output, standard error, and return code in a JSON block."
    )

    class Parameters(BaseModel):
        cmd: str
        timeout: float = Field(
            default=10,
            description="Timeout in seconds before the command is terminated.",
        )

    def _message_for_user(
        self, stdout: str, stderr: str, returncode: int, comment: Optional[str]
    ) -> str:
        def preview(title: str, content: str, width: int) -> str:
            if len(content) <= width:
                header = f"--- {title} (All {len(content)} chars) ---"
            else:
                header = f"--- {title} (First {width} of {len(content)} chars) ---"
            content_display = shorten(content, width)
            return header + "\n" + content_display + "\n\n"

        return (
            f"Execution finished with code {returncode}.\n"
            + (f"Comment: {comment}\n\n" if comment is not None else "\n")
            + preview("STDOUT", stdout, 512)
            + preview("STDERR", stderr, 512)
        )

    def invoke(self, cmd: str, timeout: float) -> ToolResult:
        p: subprocess.Popen[str] = subprocess.Popen(
            cmd,
            shell=True,
            executable="/bin/bash",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=os.setsid,
        )

        try:
            stdout, stderr = p.communicate(timeout=timeout)
            comment = None
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(p.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = p.communicate()
            comment = "timeout"

        return ToolResult(
            json_md(
                {
                    "stdout": stdout,
                    "stderr": stderr,
                    "returncode": p.returncode,
                    "comment": comment,
                }
            ),
            self._message_for_user(stdout, stderr, p.returncode, comment),
        )


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
        if not osp.isdir(folder):
            return "Skill list is empty."
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
        return ToolResult(content, f'Successfully load skill "{skill_name}".')
