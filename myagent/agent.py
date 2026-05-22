import json
import platform
import os
from datetime import datetime
import traceback
from typing import Any

from myagent.loggers import Logger
from myagent.tools import ToolsList
from myagent.llm_client import LLMClient
from myagent.idsep_parser import IDSepParser
from myagent.prompt import load_prompt


class Agent:
    def __init__(
        self,
        name: str,
        llm_client: LLMClient,
        tools_list: ToolsList,
        idsep_parser: IDSepParser,
    ) -> None:
        self.name: str = name
        self.llm_client: LLMClient = llm_client
        self.tools_list: ToolsList = tools_list
        self.idsep_parser: IDSepParser = idsep_parser


class ReActAgent(Agent):
    def __init__(
        self,
        name: str,
        llm_client: LLMClient,
        tools_list: ToolsList,
        idsep_parser: IDSepParser,
        logger: Logger,
        num_retries: int,
        summarize_num: int = 128,
        summarize_keep_latest_num: int = 8,
    ) -> None:
        super().__init__(name, llm_client, tools_list, idsep_parser)

        self.logger: Logger = logger
        self.num_retries: int = num_retries
        self.summarize_num: int = summarize_num
        self.summarize_keep_latest_num: int = summarize_keep_latest_num

    def _parse_idsep(self, content: str) -> dict[str, Any]:
        obj: dict[str, str] = self.idsep_parser.parse(content)

        ans: dict[str, Any] = {}

        for k, v in obj.items():
            k_parts: list[str] = k.split(".")
            node: dict[str, Any] = ans
            for k_part in k_parts[:-1]:
                if node.get(k_part) is None:
                    node[k_part] = {}
                node = node[k_part]
            node[k_parts[-1]] = v

        return ans

    def _summarize(self, history: list[dict[str, Any]]) -> str:
        history_objs: list[dict[str, Any]] = []
        for m in history[1:]:
            obj: dict[str, Any] = self._parse_idsep(m["content"])
            history_objs.append({"role": m["role"], "content": obj})

        summarizer_prompt = load_prompt(
            "prompts/summarizer.md",
            {
                "history": json.dumps(history_objs, indent=4, ensure_ascii=False),
            },
        )

        messages: list[dict[str, str]] = [
            {
                "role": "user",
                "content": summarizer_prompt,
            },
        ]

        _, content = self.llm_client.call(messages)
        self.logger.log(self.name, {"summarization": content})
        return content

    def _try_one_iter(
        self, messages: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]] | None, str | None]:
        _, content = self.llm_client.call(messages)

        obj: dict[str, Any] = self._parse_idsep(content)

        if "final_answer" in obj:
            self.logger.log(self.name, {"thought": obj.get("thought", "")})
            self.logger.log(self.name, {"final_answer": obj["final_answer"]})
            return None, obj["final_answer"]

        if "action" not in obj:
            raise ValueError(f"Invalid content format: {obj}")

        tool: str = ""
        args: dict[str, Any] = {}
        for tool, args in obj["action"].items():
            break

        self.logger.log(self.name, {"thought": obj.get("thought", "")})
        self.logger.log(self.name, {"action": {"tool": tool, "args": args}})
        try:
            observation, pin = self.tools_list.execute_tool(tool, args)
        except:
            observation: str = traceback.format_exc()
            pin = False
        observation_obj: dict[str, str] = {"observation": observation}
        self.logger.log(self.name, observation_obj)
        messages = messages + [
            {
                "role": "assistant",
                "content": content,
                "meta": {"pin": pin},
            },
            {
                "role": "user",
                "content": self.idsep_parser.build(observation_obj),
                "meta": {"pin": pin},
            },
        ]

        if len(messages) >= self.summarize_num:
            summarization_content: str = self._summarize(messages)
            summarization_obj: dict[str, str] = {"summarization": summarization_content}
            messages = [
                m
                for i, m in enumerate(messages)
                if m["meta"]["pin"]
                or (len(messages) - i <= self.summarize_keep_latest_num)
            ] + [
                {
                    "role": "assistant",
                    "content": self.idsep_parser.build(summarization_obj),
                    "meta": {"pin": False},
                }
            ]

        return messages, None

    def _retry_one_iter(
        self, messages: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]] | None, str | None]:
        for _ in range(self.num_retries + 1):
            try:
                return self._try_one_iter(messages)
            except Exception as e:
                exception: Exception = e
        raise exception

    def run(self, query: str) -> str:
        react_prompt = load_prompt(
            "prompts/react.md",
            {
                "tools_list": self.tools_list.tools_list_desc(),
                "sepidk": self.idsep_parser.sepidk,
                "sepidv": self.idsep_parser.sepidv,
                "sepide": self.idsep_parser.sepide,
            },
        )

        question_obj: dict[str, str] = {"question": query}
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": react_prompt,
                "meta": {"pin": True},
            },
            {
                "role": "user",
                "content": self.idsep_parser.build(question_obj),
                "meta": {"pin": True},
            },
        ]
        self.logger.log(self.name, question_obj)

        while True:
            result_messages, final_answer = self._retry_one_iter(messages)
            if final_answer is not None:
                self.tools_list.execute_tool("notify_user", {"content": final_answer})
                return final_answer
            if result_messages is not None:
                messages = result_messages
