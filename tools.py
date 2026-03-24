import subprocess
import json
import inspect
import traceback
import platform
import sys
import os
import os.path as osp
import requests

from markdownify import markdownify as md


class ReadFileTool:
    name = "read_file"

    desc = """Read file from specific path into text.
    Returns a serialized JSON object containing content (file content) and result ("success" or exception traceback).
    """

    def invoke(self, path: str) -> str:
        try:
            with open(path, "r") as f:
                content = f.read()
            return json.dumps(
                {"content": content, "result": "success"}, ensure_ascii=False
            )
        except Exception:
            return json.dumps({"result": traceback.format_exc()}, ensure_ascii=False)


class WriteToFileTool:
    name = "write_to_file"

    desc = """Write text content into specific path.
    Returns a serialized JSON object containing the result ("success" or exception traceback).
    """

    def invoke(self, path: str, content: str) -> str:
        try:
            with open(path, "w") as f:
                f.write(content)
            return json.dumps({"result": "success"}, ensure_ascii=False)
        except Exception:
            return json.dumps({"result": traceback.format_exc()}, ensure_ascii=False)


class ExecuteOSCommandTool:
    name = "execute_os_command"

    @property
    def desc(self):
        return f"""Execute {platform.platform()} shell command (shell: {self._os_default_shell_path()}).
    Returns a serialized JSON object containing stdout, stderr and return code.
    """

    def invoke(self, cmd: str) -> str:
        p = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
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

    def _os_default_shell_path(self):
        if sys.platform.startswith("win"):
            shell_path = os.environ["COMSPEC"]
        else:
            shell_path = "/bin/sh"
        shell_path = osp.realpath(shell_path)
        return shell_path


class WebFetchAsMarkdown:
    name = "web_fetch_as_markdown"

    desc = """Fetch web page content from a specific url via HTTP get method, then convert the retrieved content to Markdown format.
    Returns a serialized JSON object containing content (web page in Markdown format) and result ("success" or exception traceback).
    """

    def invoke(self, url: str) -> str:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
        }
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            markdown_content = md(response.text)
            return json.dumps(
                {"content": markdown_content, "result": "success"}, ensure_ascii=False
            )
        except Exception:
            return json.dumps({"result": traceback.format_exc()}, ensure_ascii=False)


def _register_tools():
    ls = []
    tools = [
        ReadFileTool(),
        WriteToFileTool(),
        ExecuteOSCommandTool(),
        WebFetchAsMarkdown(),
    ]
    for tool in tools:
        desc = f"def {tool.name}{inspect.signature(tool.invoke)}\n\t{tool.desc}"
        ls.append({"name": tool.name, "desc": desc, "func": tool.invoke})
    return ls


NATIVE_TOOLS_LIST = _register_tools()
