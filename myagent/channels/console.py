import argparse
import json
import os.path as osp
from time import time

from myagent.llm_client import LLMClient
from myagent.tools import ToolsList
from myagent.agent import PlanAndExecuteAgent, ReActAgent
from myagent.loggers import JsonlLogger, TerminalLogger
from myagent.idsep_parser import IDSepParser


def send_msg(content):
    TerminalLogger.instance().prompt("MyAgent updates", content)


def request_msg():
    return TerminalLogger.instance().prompt("User replies", None)


if __name__ == "__main__":
    parser = argparse.ArgumentParser("MyAgent console")
    parser.add_argument("--config")
    parser.add_argument("--plan-mode", action="store_true")
    args = parser.parse_args()

    with open(args.config, "r") as f:
        config = json.load(f)
    llm_client = LLMClient.build(config["llm"])
    tools_list = ToolsList(send_msg, request_msg)
    idsep_parser = IDSepParser(None)

    logger = JsonlLogger(
        osp.join(config["channels"]["console"]["log"], f"{time():.3f}.jsonl")
    )

    if args.plan_mode:
        agent = PlanAndExecuteAgent(
            "PlanAndExecuteAgent",
            llm_client,
            tools_list,
            idsep_parser,
            logger,
            num_retries=3,
        )
    else:
        agent = ReActAgent(
            "ReActAgent",
            llm_client,
            tools_list,
            idsep_parser,
            logger,
            num_retries=3,
        )

    query = TerminalLogger.instance().prompt("User queries", None)
    answer = agent.run(query)
