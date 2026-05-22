import json
import colorama
from datetime import datetime
import os.path as osp
import os
from typing import Any, Optional, TextIO


class JsonlLogger:
    def __init__(self, filename: str) -> None:
        os.makedirs(osp.dirname(filename), exist_ok=True)
        self.f: TextIO = open(filename, "w")

    def log(self, agent: str, content: Any) -> None:
        self.f.write(
            json.dumps(
                {"agent": agent, "content": content},
                ensure_ascii=False,
            )
            + "\n"
        )
        self.f.flush()

    def __del__(self) -> None:
        self.f.close()


class TerminalLogger:
    _instance: Optional["TerminalLogger"] = None

    @staticmethod
    def instance() -> "TerminalLogger":
        if TerminalLogger._instance is None:
            TerminalLogger._instance = TerminalLogger()
        return TerminalLogger._instance

    def prompt(self, prompt: str, text: Optional[str]) -> str | None:
        time_str: str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(
            f"[{time_str}] {colorama.Fore.RED}{prompt}:{colorama.Fore.RESET} ",
            end="",
        )
        if text is None:
            return input()
        else:
            print(text)
            return None
