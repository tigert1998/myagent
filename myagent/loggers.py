import json
import colorama
from datetime import datetime
import os.path as osp
import os


class JsonlLogger:
    def __init__(self, filename):
        os.makedirs(osp.dirname(filename), exist_ok=True)
        self.f = open(filename, "w")

    def log(self, agent, content):
        self.f.write(
            json.dumps(
                {"agent": agent, "content": content},
                ensure_ascii=False,
            )
            + "\n"
        )
        self.f.flush()

    def __del__(self):
        self.f.close()


class TerminalLogger:
    _instance = None

    @staticmethod
    def instance():
        if TerminalLogger._instance is None:
            TerminalLogger._instance = TerminalLogger()
        return TerminalLogger._instance

    def prompt(self, prompt, text):
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(
            f"[{time_str}] {colorama.Fore.RED}{prompt}:{colorama.Fore.RESET} ",
            end="",
        )
        if text is None:
            return input()
        else:
            print(text)
