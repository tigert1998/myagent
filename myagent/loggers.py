import json
import colorama


class JsonlLogger:
    def __init__(self, filename):
        self.f = open(filename, "w")

    def log(self, agent, section, content):
        self.f.write(
            json.dumps(
                {"agent": agent, "section": section, "content": content},
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
        print(colorama.Fore.RED + prompt + ": " + colorama.Fore.RESET, end="")
        if text is None:
            return input()
        else:
            print(text)
