import json
import threading
import asyncio
import argparse
import traceback

import discord

from myagent.agent import PlanAndExecuteAgent
from myagent.llm_client import LLMClient
from myagent.loggers import JsonlLogger
from myagent.tools import ToolsList


class DiscordChannel:
    def __init__(self, llm_config, token, log_path):
        llm_client = LLMClient.build(llm_config)
        self.token = token
        self.log_path = log_path

        self.agent_running = False
        self.channel = None

        intents = discord.Intents.default()
        intents.message_content = True
        self.client = discord.Client(intents=intents)

        tools_list = ToolsList(self.send_msg, self.request_msg)
        logger = JsonlLogger(self.log_path)
        self.agent = PlanAndExecuteAgent(
            "PlanAndExecuteAgent",
            llm_client,
            tools_list,
            logger,
            num_retries=3,
        )

        self.client.event(self.on_message)

    def request_msg(self):
        async def get_next_user_message():
            def check(m):
                return m.channel.id == self.channel.id and m.author != self.client.user

            msg = await self.client.wait_for("message", check=check)
            return msg.content

        future = asyncio.run_coroutine_threadsafe(
            get_next_user_message(), self.client.loop
        )
        return future.result()

    def send_msg(self, content):
        if self.channel is not None:
            future = asyncio.run_coroutine_threadsafe(
                self.channel.send(content), self.client.loop
            )
            future.result()

    async def on_message(self, message):
        if message.author == self.client.user:
            return

        if self.agent_running:
            return

        self.channel = message.channel

        def run_agent_in_thread():
            self.agent_running = True
            try:
                self.agent.logger = JsonlLogger(self.log_path)
                self.agent.run(message.content)
            except:
                error_msg = traceback.format_exc()
                error_msg = error_msg[-1900:]
                future = asyncio.run_coroutine_threadsafe(
                    self.channel.send(f"MyAgent crashes:\n```\n{error_msg}\n```\n"),
                    self.client.loop,
                )
                future.result()
            finally:
                self.agent_running = False

        threading.Thread(target=run_agent_in_thread, daemon=True).start()

    def run(self):
        self.client.run(self.token)


if __name__ == "__main__":
    parser = argparse.ArgumentParser("MyAgent discord channel")
    parser.add_argument("--config")
    args = parser.parse_args()

    with open(args.config, "r") as f:
        config = json.load(f)
    discord_channel = DiscordChannel(
        config["llm"], config["channels"]["discord"], config["log"]
    )
    discord_channel.run()
