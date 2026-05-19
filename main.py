import argparse
import json

from agent import PlanAndExecuteAgent, DeepSeekClient
from loggers import JsonlLogger, TerminalLogger

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
        DeepSeekClient(
            config["url"],
            config["model"],
            config["key"],
            config.get("other_configs", {}),
        ),
        logger,
        num_retries=3,
    )
    answer = agent.run(args.query)

    TerminalLogger.instance().prompt("Answer", answer)
