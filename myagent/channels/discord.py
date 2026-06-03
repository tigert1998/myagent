import json
import threading
import asyncio
import argparse
import traceback
import os.path as osp
from time import time
from concurrent.futures import Future
from typing import Any, Optional

import discord

from myagent.agent import ReActAgent
from myagent.llm_client import LLMClient
from myagent.loggers import JsonlLogger
from myagent.tools.build_tools_lists import (
    build_basic_tools_list,
    build_full_tools_list,
)


class DiscordChannel:
    class Session:
        agents: list[ReActAgent]
        condition: threading.Condition

        def __init__(self) -> None:
            self.agents = []
            self.condition = threading.Condition()

        def append_user_new_msg(self, message: str) -> None:
            with self.condition:
                for agent in self.agents:
                    agent.append_user_new_msg(message)
                self.condition.notify_all()

        def wait_for_user_new_msgs(self) -> None:
            with self.condition:
                self.condition.wait_for(
                    lambda: any(
                        [len(agent._get_user_new_msgs()) > 0 for agent in self.agents]
                    )
                )

    def __init__(
        self,
        llm_config: dict[str, Any],
        token: str,
        log_path: str,
        proxy: Optional[str],
    ) -> None:
        self.llm_client: LLMClient = LLMClient.build(llm_config)
        self.token: str = token
        self.log_path: str = log_path

        self.messages_to_session: dict[int, DiscordChannel.Session] = {}

        intents: discord.Intents = discord.Intents.default()
        intents.message_content = True
        self.client: discord.Client = discord.Client(intents=intents, proxy=proxy)
        self.client.event(self.on_message)

    def send_msg(
        self, channel: discord.TextChannel, user_id: int, content: str
    ) -> list[int]:
        content = f"<@{user_id}>\n{content}"
        message_ids = []
        while len(content) > 0:
            content_to_send = content[:1900]
            future: Future[discord.Message] = asyncio.run_coroutine_threadsafe(
                channel.send(content_to_send), self.client.loop
            )
            message_ids.append(future.result().id)
            content = content[1900:]
        return message_ids

    async def on_message(self, message: discord.Message) -> None:
        if (
            message.author == self.client.user
            or self.client.user not in message.mentions
        ):
            return

        channel = message.channel
        if not isinstance(channel, discord.TextChannel):
            return

        if message.reference is not None and message.reference.message_id is not None:
            # reply
            if message.reference.message_id in self.messages_to_session:
                self.messages_to_session[
                    message.reference.message_id
                ].append_user_new_msg(message.clean_content)
                self.messages_to_session[message.id] = self.messages_to_session[
                    message.reference.message_id
                ]
            return

        def run_agent_in_thread() -> None:
            session = DiscordChannel.Session()
            self.messages_to_session[message.id] = session

            def send_msg(content: str) -> None:
                message_ids = self.send_msg(
                    channel=channel, user_id=message.author.id, content=content
                )
                for message_id in message_ids:
                    self.messages_to_session[message_id] = session

            try:
                logger: JsonlLogger = JsonlLogger(
                    osp.join(self.log_path, f"{message.author.id}-{time():.3f}.jsonl")
                )

                num_sub_agents = 0

                def build_sub_agent() -> ReActAgent:
                    nonlocal num_sub_agents
                    num_sub_agents += 1
                    sub_agent = ReActAgent(
                        f"SubAgent #{num_sub_agents}",
                        self.llm_client,
                        send_msg,
                        build_basic_tools_list(),
                        logger,
                    )
                    session.agents.append(sub_agent)
                    return sub_agent

                def destroy_sub_agent(sub_agent: ReActAgent) -> None:
                    session.agents.remove(sub_agent)

                full_tools_list = build_full_tools_list(
                    build_sub_agent, destroy_sub_agent
                )

                agent: ReActAgent = ReActAgent(
                    "ReActAgent",
                    self.llm_client,
                    send_msg,
                    full_tools_list,
                    logger,
                )

                session.agents = [agent]

                agent.append_user_new_msg(message.clean_content)
                messages, _ = agent.run()
                while True:
                    session.wait_for_user_new_msgs()
                    messages, _ = agent.run(messages)

            except:
                error_msg: str = traceback.format_exc()
                error_msg = error_msg[-1900:]
                send_msg(f"## MyAgent crashes\n```\n{error_msg}\n```\n")
            finally:
                session.agents = []

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
        config["channels"]["discord"].get("proxy"),
    )
    discord_channel.run()
