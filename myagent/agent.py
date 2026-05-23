import json
import traceback
from typing import Any

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
    ) -> None:
        super().__init__(name, llm_client, tools_list)

        self.logger: Logger = logger

    def _one_iter(
        self, messages: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], str | None]:
        reasoning_content, content, tool_calls = self.llm_client.call(messages)
        self.logger.log(self.name, {"thought": reasoning_content})

        messages_to_append = [
            {
                "role": "assistant",
                "reasoning_content": reasoning_content,
                "content": content,
                "tool_calls": tool_calls,
            }
        ]

        if len(tool_calls) > 0:
            for tool_call in tool_calls:
                call_id = tool_call["id"]
                name = tool_call["function"]["name"]
                args: dict[str, Any] = json.loads(tool_call["function"]["arguments"])
                self.logger.log(self.name, {"action": {"tool": name, "args": args}})
                try:
                    observation = self.tools_list.execute_tool(name, args)
                except:
                    observation = traceback.format_exc()
                self.logger.log(self.name, {"observation": observation})

                messages_to_append.append(
                    {"role": "tool", "tool_call_id": call_id, "content": observation}
                )

            messages = messages + messages_to_append
            return messages, None
        else:
            self.logger.log(self.name, {"final_answer": content})

            messages = messages + messages_to_append
            return messages, content

    def run(self, query: str) -> str:
        react_prompt = load_prompt("prompts/react.md", {})

        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": react_prompt,
            },
            {
                "role": "user",
                "content": query,
            },
        ]
        self.logger.log(self.name, {"question": query})

        while True:
            messages, final_answer = self._one_iter(messages)
            if final_answer is not None:
                self.tools_list.execute_tool("notify_user", {"content": final_answer})
                return final_answer
