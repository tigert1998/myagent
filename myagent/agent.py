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

    def _parse_idsep(self, content: str):
        obj = self.idsep_parser.parse(content)

        ans = {}

        for k, v in obj.items():
            k_parts = k.split(".")
            node = ans
            for k_part in k_parts[:-1]:
                if node.get(k_part) is None:
                    node[k_part] = {}
                node = node[k_part]
            node[k_parts[-1]] = v

        return ans

    def _summarize(self, history):
        with open("prompts/summarizer.md", "r") as f:
            summarizer_prompt = f.read()

        history_objs = []
        for m in history[1:]:
            obj = self._parse_idsep(m["content"])
            history_objs.append({"role": m["role"], "content": obj})

        dic = {
            "os": platform.platform(),
            "pwd": os.getcwd(),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "history": json.dumps(history_objs, indent=4, ensure_ascii=False),
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

        obj = self._parse_idsep(content)

        if "final_answer" in obj:
            self.logger.log(self.name, {"thought": obj.get("thought", "")})
            self.logger.log(self.name, {"final_answer": obj["final_answer"]})
            return None, obj["final_answer"]

        if "action" not in obj:
            raise ValueError(f"Invalid content format: {obj}")

        for tool, args in obj["action"].items():
            break

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
            content = self._summarize(messages)
            summarization_obj = {"summarization": content}
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
