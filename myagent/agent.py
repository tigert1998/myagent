import json
import platform
import os
from datetime import datetime
import traceback
from typing import List

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
        with open("prompts/idsep_desc.md", "r") as f:
            self.idsep_desc = f.read().format(sepid=self.idsep_parser.sepid)


class ReActAgent(Agent):
    def __init__(
        self,
        name,
        llm_client,
        tools_list,
        idsep_parser,
        logger,
        num_retries,
        summarize_num=64,
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
            "idsep_desc": self.idsep_desc,
            "sepid": self.idsep_parser.sepid,
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


class PlanAndExecuteAgent(Agent):
    def __init__(self, name, llm_client, tools_list, idsep_parser, logger, num_retries):
        super().__init__(name, llm_client, tools_list, idsep_parser)

        self.logger = logger
        self.num_retries = num_retries

    @staticmethod
    def _parse_plan(obj: dict):
        steps = []
        for k, v in obj.items():
            k_parts = k.split(".")
            if len(k_parts) <= 1 or "step" != k_parts[1]:
                continue
            steps.append(v)
        return steps

    @staticmethod
    def _plan_to_markdown(prompt, plan: List[str]):
        text = "\n".join([f"{i + 1}. {step}" for i, step in enumerate(plan)])
        return f"**{prompt}**:\n{text}\n"

    def _try_one_iter(self, messages):
        _, content = self.llm_client.call(messages)

        obj = self.idsep_parser.parse(content)

        if any(["final_plan." in k for k in obj.keys()]):
            final_plan_steps = self._parse_plan(obj)
            self.logger.log(self.name, {"thought": obj.get("thought", "")})
            self.logger.log(self.name, {"final_plan": final_plan_steps})
            return None, final_plan_steps

        if not any(["plan." in k for k in obj.keys()]):
            self.logger.log(self.name, {"thought": obj.get("thought", "")})
            self.logger.log(self.name, {"final_plan": []})
            return None, []

        plan_steps = self._parse_plan(obj)

        audit, _ = self.tools_list.execute_tool(
            "ask_user",
            {
                "question": PlanAndExecuteAgent._plan_to_markdown(
                    "Review MyAgent's plan and suggest improvements", plan_steps
                )
            },
        )

        audit_obj = {"audit": audit}
        messages = messages + [
            {"role": "assistant", "content": self.idsep_parser.build(obj)},
            {"role": "user", "content": self.idsep_parser.build(audit_obj)},
        ]

        self.logger.log(self.name, {"thought": obj.get("thought", "")})
        self.logger.log(self.name, {"plan": plan_steps})
        self.logger.log(self.name, audit_obj)
        return messages, None

    def _retry_one_iter(self, messages):
        for _ in range(self.num_retries + 1):
            try:
                return self._try_one_iter(messages)
            except Exception as e:
                exception = e
        raise exception

    def _plan(self, query):
        with open("prompts/planner.md", "r") as f:
            planner_prompt = f.read()

        dic = {
            "os": platform.platform(),
            "pwd": os.getcwd(),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "tools_list": self.tools_list.tools_list_desc(),
            "soul": self.soul,
            "idsep_desc": self.idsep_desc,
            "sepid": self.idsep_parser.sepid,
        }
        planner_prompt = planner_prompt.format(**dic)

        question_obj = {"question": query}
        messages = [
            {"role": "system", "content": planner_prompt},
            {
                "role": "user",
                "content": self.idsep_parser.build(question_obj),
            },
        ]
        self.logger.log(self.name, question_obj)

        while True:
            messages, final_plan = self._retry_one_iter(messages)
            if final_plan is not None:
                if len(final_plan) >= 1:
                    content = self._plan_to_markdown(
                        "MyAgent has finalized the plan and is now moving forward",
                        final_plan,
                    )
                else:
                    content = "**Task finished. MyAgent is standing by.**"
                self.tools_list.execute_tool("notify_user", {"content": content})
                return final_plan

    def run(self, query) -> str:
        steps_answers = []
        steps = []

        while True:
            planner_query = f"# 当前最终目标\n{query}\n# 已完成的子任务及结果\n"
            for i in range(len(steps_answers)):
                planner_query += f"## 子任务 {i + 1}\n### 任务描述\n{steps[i]}\n### 执行结果\n````markdown\n{steps_answers[i]}\n````\n"

            new_steps = self._plan(planner_query)
            if len(new_steps) == 0:
                return steps_answers[-1] if len(steps_answers) >= 1 else ""

            react_agent_id = len(steps) + 1
            react_agent = ReActAgent(
                f"{self.name} - subagent #{react_agent_id}",
                self.llm_client,
                self.tools_list,
                self.idsep_parser,
                self.logger,
                self.num_retries,
            )

            react_agent_query = f"# 当前最终目标\n{query}\n# 已完成的子任务及结果\n"
            for i in range(len(steps_answers)):
                react_agent_query += f"## 子任务 {i + 1}\n### 任务描述\n{steps[i]}\n### 执行结果\n````markdown\n{steps_answers[i]}\n````\n"
            react_agent_query += f"# 当前需要执行的任务\n{new_steps[0]}\n"
            react_agent_query += """# 执行要求

请基于上述已完成任务的结果，继续推进当前任务。执行过程中应：

1. 充分利用已有信息与已有执行结果；
2. 避免重复分析、重复调用工具或重复执行相同步骤；
3. 优先在现有上下文基础上完成当前任务；
4. 若已有结果已包含部分所需信息，应直接复用并在其基础上继续推进。

你当前仅需完成「当前需要执行的任务」，无需直接完成「最终目标」或额外扩展未要求的内容。
"""

            answer = react_agent.run(react_agent_query)
            steps_answers.append(answer)
            steps.append(new_steps[0])
