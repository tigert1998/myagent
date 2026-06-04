import colorama
from datetime import datetime
from typing import Optional


class TerminalPrompter:
    _instance: Optional["TerminalPrompter"] = None

    @staticmethod
    def instance() -> "TerminalPrompter":
        if TerminalPrompter._instance is None:
            TerminalPrompter._instance = TerminalPrompter()
        return TerminalPrompter._instance

    def _prompt(self, prompt: str) -> None:
        time_str: str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(
            f"[{time_str}] {colorama.Fore.RED}{prompt}:{colorama.Fore.RESET} ",
            end="",
        )

    def prompt_input(self, prompt: str) -> str:
        self._prompt(prompt)
        return input()

    def prompt_notify(self, prompt: str, content: str) -> None:
        self._prompt(prompt)
        print(content)
