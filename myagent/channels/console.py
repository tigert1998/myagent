import argparse
import json
import os.path as osp
from time import time
from typing import Any

from myagent.llm_client import LLMClient
from myagent.tools.build_tools_lists import (
    build_full_tools_list,
    build_basic_tools_list,
)
from myagent.agent import ReActAgent
from myagent.loggers import JsonlLogger, TerminalPrompter


def send_msg(content: str) -> None:
    TerminalPrompter.instance().prompt_notify("MyAgent", "\n" + content)


def request_msg() -> str:
    try:
        return TerminalPrompter.instance().prompt_input("User")
    except (EOFError, KeyboardInterrupt) as _:
        print()
        exit(0)


if __name__ == "__main__":
    parser: argparse.ArgumentParser = argparse.ArgumentParser("MyAgent console")
    parser.add_argument("--config")
    args: argparse.Namespace = parser.parse_args()

    with open(args.config, "r") as f:
        config: dict[str, Any] = json.load(f)
    llm_client: LLMClient = LLMClient.build(config["llm"])

    logger: JsonlLogger = JsonlLogger(
        osp.join(config["channels"]["console"]["log"], f"{time():.3f}.jsonl")
    )

    basic_tools_list = build_basic_tools_list()

    num_sub_agents = 0

    def build_sub_agent() -> ReActAgent:
        global num_sub_agents
        num_sub_agents += 1
        return ReActAgent(
            f"SubAgent #{num_sub_agents}",
            llm_client,
            send_msg,
            basic_tools_list,
            logger,
        )

    full_tools_list = build_full_tools_list(build_sub_agent)

    agent: ReActAgent = ReActAgent(
        "ReActAgent",
        llm_client,
        send_msg,
        full_tools_list,
        logger,
    )

    messages = None
    while True:
        agent.append_user_new_msg(request_msg())
        messages, _ = agent.run(messages)
