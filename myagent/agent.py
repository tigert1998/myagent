import json
import platform
import os
from datetime import datetime
import traceback

from bs4 import BeautifulSoup, Tag

from myagent.tools import ToolsList
from myagent.llm_client import LLMClient


class Agent:
    def __init__(self, name, llm_client: LLMClient, tools_list: ToolsList):
        self.name = name
        self.llm_client = llm_client
        self.tools_list = tools_list


class ReActAgent(Agent):
    def __init__(
        self,
        name,
        llm_client,
        tools_list,
        logger,
        num_retries,
        summarize_num=64,
        summarize_keep_latest_num=8,
    ):
        super().__init__(name, llm_client, tools_list)

        self.logger = logger
        self.num_retries = num_retries
        self.summarize_num = summarize_num
        self.summarize_keep_latest_num = summarize_keep_latest_num

    @staticmethod
    def _parse_action_tag(action: Tag):
        root = action.find()
        tool_name = root.name
        dic = {}
        for j in root.children:
            if not isinstance(j, Tag):
                continue
            argument_name = j.name
            argument_value = j.text
            dic[argument_name] = argument_value
        return tool_name, dic

    @staticmethod
    def _build_single_node_xml(name, content):
        soup = BeautifulSoup(features="xml")
        node = soup.new_tag(name)
        node.string = content
        return node

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
        summarization = ReActAgent._build_single_node_xml("summarization", content)
        self.logger.log(self.name, "阶段总结", str(summarization))
        return content

    def _try_one_iter(self, messages):
        _, content = self.llm_client.call(messages)

        soup = BeautifulSoup(content, features="lxml")
        if soup.action is None and soup.final_answer is None:
            raise ValueError(f"Content format is incorrect:\n{content}")

        if soup.thought is None:
            thought = ReActAgent._build_single_node_xml("thought", "")
        else:
            thought = soup.thought

        if soup.final_answer is not None:
            self.logger.log(self.name, "思考", str(thought))
            self.logger.log(self.name, "最终答案", str(soup.final_answer))
            return None, soup.final_answer.text.strip()

        name, args = ReActAgent._parse_action_tag(soup.action)
        try:
            output, pin = self.tools_list.execute_tool(name, args)
        except:
            output = traceback.format_exc()
            pin = False

        self.logger.log(self.name, "思考", str(thought))
        self.logger.log(self.name, "行动", str(soup.action))
        observation = ReActAgent._build_single_node_xml("observation", output)
        self.logger.log(self.name, "观察结果", str(observation))
        messages = messages + [
            {
                "role": "assistant",
                "content": str(thought) + str(soup.action),
                "meta": {"pin": pin},
            },
            {
                "role": "user",
                "content": str(observation),
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
            except:
                exception = traceback.format_exc()
        raise exception

    def run(self, query) -> str:
        with open("prompts/react.md", "r") as f:
            react_prompt = f.read()
        dic = {
            "os": platform.platform(),
            "pwd": os.getcwd(),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "tools_list": self.tools_list.tools_list_desc(),
        }
        react_prompt = react_prompt.format(**dic)

        node = ReActAgent._build_single_node_xml("question", query)
        messages = [
            {
                "role": "system",
                "content": react_prompt,
                "meta": {"pin": True},
            },
            {
                "role": "user",
                "content": str(node),
                "meta": {"pin": True},
            },
        ]
        self.logger.log(self.name, "用户提问", str(node))

        while True:
            messages, final_answer = self._retry_one_iter(messages)
            if final_answer is not None:
                self.tools_list.execute_tool("notify_user", {"content": final_answer})
                return final_answer


class PlanAndExecuteAgent(Agent):
    def __init__(self, name, llm_client, tools_list, logger, num_retries):
        super().__init__(name, llm_client, tools_list)

        self.logger = logger
        self.num_retries = num_retries

    @staticmethod
    def _build_single_node_xml(name, content):
        soup = BeautifulSoup(features="xml")
        node = soup.new_tag(name)
        node.string = content
        return node

    @staticmethod
    def _parse_plan_tag(plan: Tag):
        steps = []
        for j in plan.children:
            if not isinstance(j, Tag):
                continue
            if j.name != "step":
                continue
            steps.append(j.text)
        return steps

    def _try_one_iter(self, messages):
        _, content = self.llm_client.call(messages)
        soup = BeautifulSoup(content, features="lxml")
        if soup.plan is None and soup.final_plan is None:
            raise ValueError(f"Content format is incorrect:\n{content}")
        thought = soup.thought
        if thought is None:
            thought = PlanAndExecuteAgent._build_single_node_xml("thought", "")
        if soup.final_plan is not None:
            self.logger.log(self.name, "思考", str(thought))
            self.logger.log(self.name, "最终计划", str(soup.final_plan))
            return None, PlanAndExecuteAgent._parse_plan_tag(soup.final_plan)

        parsed_plan = PlanAndExecuteAgent._parse_plan_tag(soup.plan)
        if len(parsed_plan) == 0:
            return None, []
        plan_text = "\n".join([f"- {step}" for step in parsed_plan])
        plan_text = f"Review MyAgent's plan and suggest improvements:\n{plan_text}"
        audit, _ = self.tools_list.execute_tool("ask_user", {"question": plan_text})

        node = PlanAndExecuteAgent._build_single_node_xml("audit", audit)
        messages = messages + [
            {"role": "assistant", "content": str(thought) + (str(soup.plan))},
            {"role": "user", "content": str(node)},
        ]

        self.logger.log(self.name, "思考", str(thought))
        self.logger.log(self.name, "计划", str(soup.plan))
        self.logger.log(self.name, "审计", str(node))
        return messages, None

    def _retry_one_iter(self, messages):
        for _ in range(self.num_retries + 1):
            try:
                return self._try_one_iter(messages)
            except:
                exception = traceback.format_exc()
        raise exception

    def _plan(self, query):
        with open("prompts/planner.md", "r") as f:
            planner_prompt = f.read()

        dic = {
            "os": platform.platform(),
            "pwd": os.getcwd(),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "tools_list": self.tools_list.tools_list_desc(),
        }
        planner_prompt = planner_prompt.format(**dic)

        node = PlanAndExecuteAgent._build_single_node_xml("question", query)
        messages = [
            {"role": "system", "content": planner_prompt},
            {
                "role": "user",
                "content": str(node),
            },
        ]
        self.logger.log(self.name, "用户提问", str(node))

        while True:
            messages, final_plan = self._retry_one_iter(messages)
            if final_plan is not None:
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
