import json
import threading
import asyncio
import argparse
import traceback
import os.path as osp
from time import time

import discord

from myagent.agent import PlanAndExecuteAgent
from myagent.llm_client import LLMClient
from myagent.loggers import JsonlLogger
from myagent.tools import ToolsList


class DiscordChannel:
    def __init__(self, llm_config, token, log_path):
        self.llm_client = LLMClient.build(llm_config)
        self.token = token
        self.log_path = log_path

        self.agents_running = {}

        intents = discord.Intents.default()
        intents.message_content = True
        self.client = discord.Client(intents=intents)
        self.client.event(self.on_message)

    def request_msg(self, channel, user_id):
        async def get_next_user_message():
            def check(m: discord.Message):
                return (
                    m.channel.id == channel.id
                    and m.author.id == user_id
                    and self.client.user in m.mentions
                )

            msg = await self.client.wait_for("message", check=check)
            return msg.content

        future = asyncio.run_coroutine_threadsafe(
            get_next_user_message(), self.client.loop
        )
        return future.result()

    def send_msg(self, channel, user_id, content):
        future = asyncio.run_coroutine_threadsafe(
            channel.send(f"<@{user_id}> {content}"), self.client.loop
        )
        future.result()

    async def on_message(self, message: discord.Message):
        if (
            message.author == self.client.user
            or self.client.user not in message.mentions
        ):
            return

        if self.agents_running.get(message.author.id, False):
            return

        def run_agent_in_thread():
            self.agents_running[message.author.id] = True
            send_msg = lambda content: self.send_msg(
                channel=message.channel, user_id=message.author.id, content=content
            )
            request_msg = lambda: self.request_msg(
                channel=message.channel, user_id=message.author.id
            )
            try:
                logger = JsonlLogger(
                    osp.join(self.log_path, f"{message.author.id}-{time():.3f}.jsonl")
                )
                tools_list = ToolsList(send_msg, request_msg)
                agent = PlanAndExecuteAgent(
                    "PlanAndExecuteAgent",
                    self.llm_client,
                    tools_list,
                    logger,
                    num_retries=3,
                )
                agent.run(message.content)
            except:
                error_msg = traceback.format_exc()
                error_msg = error_msg[-1900:]
                send_msg(f"**MyAgent crashes:**\n```\n{error_msg}\n```\n")
            finally:
                self.agents_running[message.author.id] = False

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
        config["llm"],
        config["channels"]["discord"]["token"],
        config["channels"]["discord"]["log"],
    )
    discord_channel.run()
