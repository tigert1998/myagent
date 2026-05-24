import traceback
from typing import Any, Optional
import threading

from myagent.loggers import Logger
from myagent.tools.tools_list import ToolsList
from myagent.llm_client import LLMClient
from myagent.prompt import load_prompt


class Agent:
    def __init__(
        self,
        name: str,
        llm_client: LLMClient,
        tools_list: ToolsList,
    ) -> None:
        self.name: str = name
        self.llm_client: LLMClient = llm_client
        self.tools_list: ToolsList = tools_list


class ReActAgent(Agent):
    def __init__(
        self,
        name: str,
        llm_client: LLMClient,
        tools_list: ToolsList,
        logger: Logger,
        num_retries: int = 3,
    ) -> None:
        super().__init__(name, llm_client, tools_list)

        self.logger: Logger = logger
        self.num_retries = num_retries

        self.user_new_msgs_lock = threading.Lock()
        self.user_new_msgs: list[str] = []

    def append_user_new_msg(self, message):
        self.user_new_msgs_lock.acquire()
        self.user_new_msgs.append(message)
        self.user_new_msgs_lock.release()

    def _get_user_new_msgs(self) -> list[str]:
        self.user_new_msgs_lock.acquire()
        user_new_msgs = self.user_new_msgs.copy()
        self.user_new_msgs_lock.release()
        return user_new_msgs

    def _clear_user_new_msgs(self, length: int):
        self.user_new_msgs_lock.acquire()
        self.user_new_msgs = self.user_new_msgs[length:]
        self.user_new_msgs_lock.release()

    def _try_one_iter(
        self, messages: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], Optional[str]]:
        # append new user messages
        # call llm
        # tool calls and observation

        user_new_msgs = self._get_user_new_msgs()
        if len(user_new_msgs) > 0:
            user_new_msg = "\n".join(user_new_msgs)
            self.logger.log(self.name, {"user": user_new_msg})
            messages = messages + [
                {
                    "role": "user",
                    "content": user_new_msg,
                }
            ]

        reasoning_content, content, tool_calls = self.llm_client.call(
            messages, self.tools_list.schema()
        )
        self.logger.log(self.name, {"think": reasoning_content})
        self.logger.log(self.name, {"assistant": content})

        messages_to_append = [
            {
                "role": "assistant",
                "reasoning_content": reasoning_content,
                "content": content,
                **({"tool_calls": tool_calls} if len(tool_calls) > 0 else {}),
            }
        ]

        if len(tool_calls) == 0:
            self._clear_user_new_msgs(len(user_new_msgs))
            messages = messages + messages_to_append
            return messages, content

        for tool_call in tool_calls:
            call_id = tool_call["id"]
            name = tool_call["function"]["name"]
            try:
                args = self.tools_list.parse_args(
                    name, tool_call["function"]["arguments"]
                ).model_dump()
                self.logger.log(
                    self.name,
                    {"action": {"tool": name, "args": args}},
                )
                observation = self.tools_list.execute_tool(name, args)
            except:
                observation = traceback.format_exc()
            self.logger.log(self.name, {"observation": observation})
            messages_to_append.append(
                {"role": "tool", "tool_call_id": call_id, "content": observation}
            )

        self._clear_user_new_msgs(len(user_new_msgs))
        messages = messages + messages_to_append
        return messages, None

    def _retry_one_iter(
        self, messages: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], Optional[str]]:
        for _ in range(self.num_retries + 1):
            try:
                return self._try_one_iter(messages)
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
