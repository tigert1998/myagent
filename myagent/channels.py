import json
import threading
import asyncio
import argparse

import discord

from myagent.agent import PlanAndExecuteAgent
from myagent.llm_client import LLMClient
from myagent.loggers import JsonlLogger
from myagent.tools import ToolsList


class Discord:
    def __init__(self, llm_config, token, log_path):
        self.token = token

        self.channel = None
        self.message_queue = []
        self.condition = threading.Condition()

        intents = discord.Intents.default()
        intents.message_content = True
        self.client = discord.Client(intents=intents)

        llm_client = LLMClient.build(llm_config)
        tools_list = ToolsList(self.send_msg, self.request_msg)
        logger = JsonlLogger(log_path)
        self.agent = PlanAndExecuteAgent(
            "PlanAndExecuteAgent",
            llm_client,
            tools_list,
            logger,
            num_retries=3,
        )

        self.client.event(self.on_message)

    def request_msg(self):
        with self.condition:
            self.message_queue = []
            self.condition.wait_for(lambda: len(self.message_queue) >= 1)
            message = self.message_queue.pop(0)
        return message.content

    def send_msg(self, content):
        if self.channel is not None:
            asyncio.run_coroutine_threadsafe(
                self.channel.send(content), self.client.loop
            )

    async def on_message(self, message):
        if message.author == self.client.user:
            return
        with self.condition:
            self.message_queue.append(message)
            self.condition.notify_all()

    def event_loop(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda: len(self.message_queue) >= 1)
                message = self.message_queue.pop(0)

            self.channel = message.channel
            self.agent.run(message.content)

    def run(self):
        thread = threading.Thread(target=self.event_loop)
        thread.start()
        self.client.run(self.token)


if __name__ == "__main__":
    parser = argparse.ArgumentParser("MyAgent discord channel")
    parser.add_argument("--config")
    args = parser.parse_args()

    with open(args.config, "r") as f:
        config = json.load(f)
    discord = Discord(config["llm"], config["channels"]["discord"], config["log"])
    discord.run()
