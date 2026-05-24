import traceback
from typing import Any, Optional

from myagent.loggers import Logger
from myagent.tools.tools_list import (
    ToolsList,
    AttemptCompletionTool,
    AskFollowupQuestionTool,
)
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
    ) -> tuple[list[dict[str, Any]], Optional[str]]:
        reasoning_content, _, tool_calls = self.llm_client.call(
            messages, self.tools_list.schema()
        )
        self.logger.log(self.name, {"thought": reasoning_content})

        messages_to_append = [
            {
                "role": "assistant",
                "reasoning_content": reasoning_content,
                "tool_calls": tool_calls,
            }
        ]

        final_answer = None
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
                result = self.tools_list.execute_tool(name, args)
                observation = result.content
                final_answer = final_answer or result.final_answer
            except:
                observation = traceback.format_exc()
                final_answer = final_answer or None
            self.logger.log(self.name, {"observation": observation})
            messages_to_append.append(
                {"role": "tool", "tool_call_id": call_id, "content": observation}
            )

        messages = messages + messages_to_append
        return messages, final_answer

    def run(self, query: str) -> str:
        react_prompt = load_prompt(
            "prompts/react.md",
            {
                "attempt_completion_tool_name": AttemptCompletionTool.name,
                "ask_followup_question_tool_name": AskFollowupQuestionTool.name,
            },
        )

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
                return final_answer
