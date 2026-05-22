import json
import colorama
from datetime import datetime
import os.path as osp
import os
from typing import Any, Optional, TextIO


class Logger:
    def log(self, agent: str, content: Any) -> None:
        raise NotImplementedError()


class JsonlLogger(Logger):
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


class TerminalPrompter:
    _instance: Optional["TerminalPrompter"] = None

    @staticmethod
    def instance() -> "TerminalPrompter":
        if TerminalPrompter._instance is None:
            TerminalPrompter._instance = TerminalPrompter()
        return TerminalPrompter._instance

    def prompt(self, prompt: str, text: Optional[str]) -> Optional[str]:
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
