import argparse
import json

from myagent.llm_client import LLMClient
from myagent.agent import PlanAndExecuteAgent
from myagent.loggers import JsonlLogger, TerminalLogger

if __name__ == "__main__":
    parser = argparse.ArgumentParser("agent")
    parser.add_argument("--config")
    parser.add_argument("--query")
    parser.add_argument("--log")
    args = parser.parse_args()

    with open(args.config, "r") as f:
        config = json.load(f)

    logger = JsonlLogger(args.log)

    agent = PlanAndExecuteAgent(
        "PlanAndExecuteAgent",
        LLMClient.build(config),
        logger,
        num_retries=3,
    )

    TerminalLogger.instance().prompt("User query", args.query)
    answer = agent.run(args.query)
    TerminalLogger.instance().prompt("Answer", answer)
