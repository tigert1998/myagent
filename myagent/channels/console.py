import argparse
import json
import os.path as osp
from time import time
from typing import Any

from myagent.llm_client import LLMClient
from myagent.tools.full_tools_list import FullToolsList
from myagent.agent import ReActAgent
from myagent.loggers import JsonlLogger, TerminalPrompter
from myagent.idsep_parser import IDSepParser


def send_msg(content: str) -> None:
    TerminalPrompter.instance().prompt_notify("MyAgent updates", content)


def request_msg() -> str:
    return TerminalPrompter.instance().prompt_input("User replies")


if __name__ == "__main__":
    parser: argparse.ArgumentParser = argparse.ArgumentParser("MyAgent console")
    parser.add_argument("--config")
    args: argparse.Namespace = parser.parse_args()

    with open(args.config, "r") as f:
        config: dict[str, Any] = json.load(f)
    llm_client: LLMClient = LLMClient.build(config["llm"])

    num_sub_agents = 0

    def sub_agent_name_builder():
        global num_sub_agents
        num_sub_agents += 1
        return f"SubAgent #{num_sub_agents}"

    logger: JsonlLogger = JsonlLogger(
        osp.join(config["channels"]["console"]["log"], f"{time():.3f}.jsonl")
    )

    full_tools_list = FullToolsList(
        send_msg,
        request_msg,
        sub_agent_name_builder,
        llm_client,
        lambda name: logger,
    )

    idsep_parser: IDSepParser = IDSepParser()

    agent: ReActAgent = ReActAgent(
        "ReActAgent",
        llm_client,
        full_tools_list,
        idsep_parser,
        logger,
    )

    query: str = TerminalPrompter.instance().prompt_input("User queries")
    answer: str = agent.run(query)
