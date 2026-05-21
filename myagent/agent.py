import json
import platform
import os
from datetime import datetime
import traceback

from myagent.tools import ToolsList
from myagent.llm_client import LLMClient
from myagent.idsep_parser import IDSepParser


class Agent:
    def __init__(
        self,
        name,
        llm_client: LLMClient,
        tools_list: ToolsList,
        idsep_parser: IDSepParser,
    ):
        self.name = name
        self.llm_client = llm_client
        self.tools_list = tools_list
        self.idsep_parser = idsep_parser
        with open("prompts/soul.md", "r") as f:
            self.soul = f.read()
        with open("prompts/idsep.md", "r") as f:
            self.idsep = f.read().format(
                sepidk=self.idsep_parser.sepidk,
                sepidv=self.idsep_parser.sepidv,
                sepide=self.idsep_parser.sepide,
            )


class ReActAgent(Agent):
    def __init__(
        self,
        name,
        llm_client,
        tools_list,
        idsep_parser,
        logger,
        num_retries,
        summarize_num=128,
        summarize_keep_latest_num=8,
    ):
        super().__init__(name, llm_client, tools_list, idsep_parser)

        self.logger = logger
        self.num_retries = num_retries
        self.summarize_num = summarize_num
        self.summarize_keep_latest_num = summarize_keep_latest_num

    @staticmethod
    def _parse_action(obj: dict):
        ans = {}
        tool = None
        for k, arg_value in obj.items():
            k_parts = k.split(".")
            if "action" not in k_parts:
                continue
            if tool is None:
                tool = k_parts[1]
            elif tool != k_parts[1]:
                raise ValueError(
                    f"Two different tool invocation in a same action: {obj}"
                )
            arg_name = k_parts[2]
            ans[arg_name] = arg_value
        return tool, ans

    def _summarize(self, history):
        with open("prompts/summarizer.md", "r") as f:
            summarizer_prompt = f.read()

        dic = {
            "os": platform.platform(),
            "pwd": os.getcwd(),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "history": json.dumps(history, indent=4),
        }
        summarizer_prompt = summarizer_prompt.format(**dic)

        messages = [
            {
                "role": "user",
                "content": summarizer_prompt,
            },
        ]

        _, content = self.llm_client.call(messages)
        self.logger.log(self.name, {"summarization": content})
        return content

    def _try_one_iter(self, messages):
        _, content = self.llm_client.call(messages)

        obj = self.idsep_parser.parse(content)

        if "final_answer" in obj:
            self.logger.log(self.name, {"thought": obj.get("thought", "")})
            self.logger.log(self.name, {"final_answer": obj["final_answer"]})
            return None, obj["final_answer"]

        if not any(["action." in k for k in obj.keys()]):
            raise ValueError(f"Invalid content format: {obj}")

        tool, args = self._parse_action(obj)
        self.logger.log(self.name, {"thought": obj.get("thought", "")})
        self.logger.log(self.name, {"action": {"tool": tool, "args": args}})
        try:
            observation, pin = self.tools_list.execute_tool(tool, args)
        except:
            observation = traceback.format_exc()
            pin = False
        observation_obj = {"observation": observation}
        self.logger.log(self.name, observation_obj)
        messages = messages + [
            {
                "role": "assistant",
                "content": self.idsep_parser.build(obj),
                "meta": {"pin": pin},
            },
            {
                "role": "user",
                "content": self.idsep_parser.build(observation_obj),
                "meta": {"pin": pin},
            },
        ]

        if len(messages) >= self.summarize_num:
            content = self._summarize(messages)
            messages = [
                m
                for i, m in enumerate(messages)
                if m["meta"]["pin"]
                or (len(messages) - i <= self.summarize_keep_latest_num)
            ] + [
                {
                    "role": "assistant",
                    "content": content,
                    "meta": {"pin": False},
                }
            ]

        return messages, None

    def _retry_one_iter(self, messages):
        for _ in range(self.num_retries + 1):
            try:
                return self._try_one_iter(messages)
            except Exception as e:
                exception = e
        raise exception

    def run(self, query) -> str:
        with open("prompts/react.md", "r") as f:
            react_prompt = f.read()
        dic = {
            "os": platform.platform(),
            "pwd": os.getcwd(),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "tools_list": self.tools_list.tools_list_desc(),
            "soul": self.soul,
            "idsep": self.idsep,
            "sepidk": self.idsep_parser.sepidk,
            "sepidv": self.idsep_parser.sepidv,
            "sepide": self.idsep_parser.sepide,
        }
        react_prompt = react_prompt.format(**dic)

        question_obj = {"question": query}
        messages = [
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
            messages, final_answer = self._retry_one_iter(messages)
            if final_answer is not None:
                self.tools_list.execute_tool("notify_user", {"content": final_answer})
                return final_answer
