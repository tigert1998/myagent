import traceback
from typing import Any, Optional, Callable
import threading
import json

from myagent.utils import shorten
from myagent.loggers import Logger
from myagent.tools.tools_list import ToolsList
from myagent.llm_client import LLMClient, LLMUsage
from myagent.prompt import load_prompt


class Agent:
    def __init__(
        self,
        name: str,
        llm_client: LLMClient,
        send_msg: Callable[[str], None],
        tools_list: ToolsList,
    ) -> None:
        self.name: str = name
        self.llm_client: LLMClient = llm_client
        self.send_msg = send_msg
        self.tools_list: ToolsList = tools_list

        self.usage: LLMUsage = LLMUsage()
        self.report_usage_every_n_tokens = 1 << 14
        self.report_usage_limit = self.report_usage_every_n_tokens

    def try_report_usage(self) -> None:
        if self.usage.prompt_tokens >= self.report_usage_limit:
            self.send_msg(self.usage.report())
            self.report_usage_limit = (
                (self.usage.prompt_tokens + self.report_usage_every_n_tokens - 1)
                // self.report_usage_every_n_tokens
                * self.report_usage_every_n_tokens
            )


class ReActAgent(Agent):
    def __init__(
        self,
        name: str,
        llm_client: LLMClient,
        send_msg: Callable[[str], None],
        tools_list: ToolsList,
        logger: Logger,
        num_retries: int = 3,
    ) -> None:
        super().__init__(name, llm_client, send_msg, tools_list)

        self.logger: Logger = logger
        self.num_retries = num_retries

        self.user_new_msgs_lock = threading.Lock()
        self.user_new_msgs: list[str] = []

        self.round_index = 0

    def append_user_new_msg(self, message: str) -> None:
        with self.user_new_msgs_lock:
            self.user_new_msgs.append(message)

    def _get_user_new_msgs(self) -> list[str]:
        with self.user_new_msgs_lock:
            return self.user_new_msgs.copy()

    def _clear_user_new_msgs(self, length: int) -> None:
        with self.user_new_msgs_lock:
            self.user_new_msgs = self.user_new_msgs[length:]

    def _try_one_iter(
        self, messages: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], Optional[str]]:
        # append new user messages
        # call llm
        # tool calls and observation

        user_new_msgs = self._get_user_new_msgs()
        if len(user_new_msgs) > 0:
            self.logger.log(self.name, {"user": user_new_msgs})
            messages = messages + [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": s} for s in user_new_msgs],
                }
            ]

        response = self.llm_client.call(messages, self.tools_list.schema())
        reasoning_content = response.reasoning_content
        content = response.content
        tool_calls = response.tool_calls
        self.usage.add(response.usage)

        self.logger.log(self.name, {"think": reasoning_content})
        self.logger.log(self.name, {"assistant": content})
        if len(content) > 0:
            self.send_msg(content)
        self.try_report_usage()

        messages_to_append: list[dict[str, Any]] = [
            {
                "role": "assistant",
                "reasoning_content": reasoning_content,
                "content": content,
            }
        ]

        if len(tool_calls) == 0:
            self._clear_user_new_msgs(len(user_new_msgs))
            messages = messages + messages_to_append
            return messages, content

        for tool_call_idx in range(len(tool_calls)):
            if len(self._get_user_new_msgs()) > len(user_new_msgs):
                tool_calls = tool_calls[:tool_call_idx]
                break

            tool_call = tool_calls[tool_call_idx]
            call_id = tool_call["id"]
            name = tool_call["function"]["name"]
            try:
                args = self.tools_list.parse_args(
                    name, tool_call["function"]["arguments"]
                )
                tool_use_obj = {"tool": name, "args": args}
                self.logger.log(self.name, {"action": tool_use_obj})
                tool_use_obj_str = shorten(
                    json.dumps(tool_use_obj, indent=4, ensure_ascii=False), 1024
                )
                self.send_msg(f"## TOOL USE\n```json\n{tool_use_obj_str}\n```\n")
                result = self.tools_list.execute_tool(
                    tool=name,
                    args=args,
                    agent_env={"usage": self.usage, "round_index": self.round_index},
                )
                observation = result.for_agent
                msg_to_send = result.for_user
            except:
                observation = [traceback.format_exc()]
                msg_to_send = None
            self.logger.log(self.name, {"observation": observation})
            messages_to_append.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": [{"type": "text", "text": s} for s in observation],
                }
            )
            if msg_to_send is not None:
                self.send_msg(f"## TOOL USE RESULT\n```\n{msg_to_send}\n```\n")

        self._clear_user_new_msgs(len(user_new_msgs))
        if len(tool_calls) > 0:
            messages_to_append[0]["tool_calls"] = tool_calls
        messages = messages + messages_to_append
        return messages, None

    def _retry_one_iter(
        self, messages: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], Optional[str]]:
        for _ in range(self.num_retries + 1):
            try:
                ret = self._try_one_iter(messages)
                self.round_index += 1
                return ret
            except Exception as e:
                exception = e
        raise exception

    def run(
        self,
        prev_messages: Optional[list[dict[str, Any]]] = None,
    ) -> tuple[list[dict[str, Any]], str]:
        if prev_messages is None:
            react_prompt = load_prompt("prompts/react.md", {})
            messages: list[dict[str, Any]] = [
                {
                    "role": "system",
                    "content": react_prompt,
                }
            ]
        else:
            messages = prev_messages

        while True:
            messages, final_answer = self._retry_one_iter(messages)
            if final_answer is not None:
                return messages, final_answer
