import argparse
import json

from agent import ReActAgent


class Logger:
    def __init__(self, filename):
        self.f = open(filename, "w")

    def log(self, section, content):
        self.f.write(
            json.dumps({"section": section, "content": content}, ensure_ascii=False)
            + "\n"
        )
        self.f.flush()

    def __del__(self):
        self.f.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser("agent")
    parser.add_argument("--config")
    parser.add_argument("--query")
    parser.add_argument("--log")
    args = parser.parse_args()

    with open(args.config, "r") as f:
        config = json.load(f)

    logger = Logger(args.log)

    agent = ReActAgent(config["url"], config["model"], config["key"], logger)
    agent.run(args.query)
