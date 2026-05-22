import json
import threading
import asyncio
import argparse
import traceback
import os.path as osp
from time import time
from concurrent.futures import Future
from typing import Any, Callable

import discord

from myagent.agent import ReActAgent
from myagent.llm_client import LLMClient
from myagent.loggers import JsonlLogger
from myagent.tools import ToolsList
from myagent.idsep_parser import IDSepParser


class DiscordChannel:
    def __init__(self, llm_config: dict[str, Any], token: str, log_path: str) -> None:
        self.llm_client: LLMClient = LLMClient.build(llm_config)
        self.token: str = token
        self.log_path: str = log_path

        self.agents_running: dict[int, bool] = {}

        intents: discord.Intents = discord.Intents.default()
        intents.message_content = True
        self.client: discord.Client = discord.Client(intents=intents)
        self.client.event(self.on_message)

    def request_msg(self, channel: discord.TextChannel, user_id: int) -> str:
        async def get_next_user_message() -> str:
            def check(m: discord.Message) -> bool:
                return (
                    m.channel.id == channel.id
                    and m.author.id == user_id
                    and self.client.user in m.mentions
                )

            msg: discord.Message = await self.client.wait_for("message", check=check)
            return msg.content

        future: Future[str] = asyncio.run_coroutine_threadsafe(
            get_next_user_message(), self.client.loop
        )
        return future.result()

    def send_msg(self, channel: discord.TextChannel, user_id: int, content: str) -> None:
        future: Future[discord.Message] = asyncio.run_coroutine_threadsafe(
            channel.send(f"<@{user_id}> {content}"), self.client.loop
        )
        future.result()

    async def on_message(self, message: discord.Message) -> None:
        if (
            message.author == self.client.user
            or self.client.user not in message.mentions
        ):
            return

        if self.agents_running.get(message.author.id, False):
            return

        def run_agent_in_thread() -> None:
            self.agents_running[message.author.id] = True
            send_msg: Callable[[str], None] = lambda content: self.send_msg(
                channel=message.channel, user_id=message.author.id, content=content
            )
            request_msg: Callable[[], str] = lambda: self.request_msg(
                channel=message.channel, user_id=message.author.id
            )
            try:
                logger: JsonlLogger = JsonlLogger(
                    osp.join(self.log_path, f"{message.author.id}-{time():.3f}.jsonl")
                )
                tools_list: ToolsList = ToolsList(send_msg, request_msg)
                idsep_parser: IDSepParser = IDSepParser()
                agent: ReActAgent = ReActAgent(
                    "ReActAgent",
                    self.llm_client,
                    tools_list,
                    idsep_parser,
                    logger,
                    num_retries=3,
                )
                agent.run(message.content)
            except:
                error_msg: str = traceback.format_exc()
                error_msg = error_msg[-1900:]
                send_msg(f"**MyAgent crashes:**\n```\n{error_msg}\n```\n")
            finally:
                self.agents_running[message.author.id] = False

        threading.Thread(target=run_agent_in_thread, daemon=True).start()

    def run(self) -> None:
        self.client.run(self.token)


if __name__ == "__main__":
    parser: argparse.ArgumentParser = argparse.ArgumentParser("MyAgent discord channel")
    parser.add_argument("--config")
    args: argparse.Namespace = parser.parse_args()

    with open(args.config, "r") as f:
        config: dict[str, Any] = json.load(f)
    discord_channel: DiscordChannel = DiscordChannel(
        config["llm"],
        config["channels"]["discord"]["token"],
        config["channels"]["discord"]["log"],
    )
    discord_channel.run()
