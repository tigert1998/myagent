import subprocess
import json
import inspect
import traceback


NATIVE_TOOLS_LIST = []


def register(f):
    name = f.__name__
    sig = inspect.signature(f)
    doc = f.__doc__
    text = f"def {name}{sig}"
    if doc is not None:
        text = f"{text}\n\t'''{doc}'''"
    NATIVE_TOOLS_LIST.append({"name": name, "func": f, "desc": text})

    return f


@register
def read_file(path: str) -> str:
    """Read file from specific path into text.
    Returns a serialized JSON object containing content (file content) and result ("success" or exception traceback).
    """
    try:
        with open(path, "r") as f:
            content = f.read()
        return json.dumps({"content": content, "result": "success"}, ensure_ascii=False)
    except Exception:
        return json.dumps({"result": traceback.format_exc()}, ensure_ascii=False)


@register
def write_to_file(path: str, content: str) -> str:
    """Write text content into specific path.
    Returns a serialized JSON object containing the result ("success" or exception traceback).
    """
    try:
        with open(path, "w") as f:
            f.write(content)
        return json.dumps({"result": "success"}, ensure_ascii=False)
    except Exception:
        return json.dumps({"result": traceback.format_exc()}, ensure_ascii=False)


@register
def execute_os_command(cmd: str) -> str:
    """Execute specific OS command.
    Returns a serialized JSON object containing stdout, stderr and return code."""
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
