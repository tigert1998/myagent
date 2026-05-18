import subprocess
import json
import inspect


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


def _register_tools():
    ls = []
    tools = [BashTool()]
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
