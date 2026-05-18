import subprocess
import json
import inspect
import sys


class ExecPythonTool:
    name = "exec_python"
    desc = "Execute the given Python code. Returns stdout, stderr and returncode of the program."

    def invoke(self, code: str):
        p = subprocess.Popen(
            [sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
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

def _register_tools():
    ls = []
    tools = [
        ExecPythonTool()
    ]
    for tool in tools:
        desc = f"def {tool.name}{inspect.signature(tool.invoke)}\n\t{tool.desc}"
        ls.append({"name": tool.name, "desc": desc, "func": tool.invoke})
    return ls


NATIVE_TOOLS_LIST = _register_tools()
