from datetime import datetime
import re
import os.path as osp
import platform
import os


def load_prompt(path: str, args: dict[str, str]) -> str:
    var_pattern = r"@\{MYAGENT:([^}]+)\}"
    file_pattern = r"@\{MYAGENT_FILE:([^}]+)\}"

    with open(path, "r") as f:
        content = f.read()

    for match in re.findall(file_pattern, content):
        filepath = osp.join(osp.dirname(path), match)
        file_content = load_prompt(filepath, args)
        content = content.replace(f"@{{MYAGENT_FILE:{match}}}", file_content)

    args = {
        **args,
        "TIME": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "OS": platform.platform(),
        "PWD": os.getcwd(),
    }

    for match in re.findall(var_pattern, content):
        value = args[match.strip()]
        content = content.replace(f"@{{MYAGENT:{match}}}", value)

    return content
