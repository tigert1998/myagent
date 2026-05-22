import argparse
import json
import os.path as osp
from time import time
from typing import Any

from myagent.llm_client import LLMClient
from myagent.tools import ToolsList
from myagent.agent import ReActAgent
from myagent.loggers import JsonlLogger, TerminalPrompter
from myagent.idsep_parser import IDSepParser


def send_msg(content: str) -> None:
    TerminalPrompter.instance().prompt("MyAgent updates", content)


def request_msg() -> str:
    return TerminalPrompter.instance().prompt("User replies", None) or ""


if __name__ == "__main__":
    parser: argparse.ArgumentParser = argparse.ArgumentParser("MyAgent console")
    parser.add_argument("--config")
    args: argparse.Namespace = parser.parse_args()

    with open(args.config, "r") as f:
        config: dict[str, Any] = json.load(f)
    llm_client: LLMClient = LLMClient.build(config["llm"])
    tools_list: ToolsList = ToolsList(send_msg, request_msg)
    idsep_parser: IDSepParser = IDSepParser()

    logger: JsonlLogger = JsonlLogger(
        osp.join(config["channels"]["console"]["log"], f"{time():.3f}.jsonl")
    )
    agent: ReActAgent = ReActAgent(
        "ReActAgent",
        llm_client,
        tools_list,
        idsep_parser,
        logger,
        num_retries=3,
    )

    query: str = TerminalPrompter.instance().prompt("User queries", None) or ""
    answer: str = agent.run(query)
