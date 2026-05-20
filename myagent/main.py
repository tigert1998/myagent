import argparse
import json

from myagent.llm_client import LLMClient
from myagent.agent import PlanAndExecuteAgent, ReActAgent
from myagent.loggers import JsonlLogger, TerminalLogger

if __name__ == "__main__":
    parser = argparse.ArgumentParser("MyAgent")
    parser.add_argument("--config")
    parser.add_argument("--query")
    parser.add_argument("--log")
    parser.add_argument("--plan-mode", action="store_true")
    args = parser.parse_args()

    with open(args.config, "r") as f:
        config = json.load(f)
    llm_client = LLMClient.build(config)

    logger = JsonlLogger(args.log)

    if args.plan_mode:
        agent = PlanAndExecuteAgent(
            "PlanAndExecuteAgent",
            llm_client,
            logger,
            num_retries=3,
        )
    else:
        agent = ReActAgent(
            "ReActAgent",
            llm_client,
            logger,
            num_retries=3,
        )

    TerminalLogger.instance().prompt("User queries", args.query)
    answer = agent.run(args.query)
