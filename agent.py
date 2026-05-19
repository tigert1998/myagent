import requests
import json
import platform
import os.path as osp
import os
from datetime import datetime
import traceback

from bs4 import BeautifulSoup, Tag

from tools import execute_tool, tools_list_desc


class DeepSeekClient:
    def __init__(self, url, model, key, other_configs):
        self.url = url
        self.model = model
        self.key = key
        self.other_configs = other_configs

    def call(self, messages):
        messages = [{"role": m["role"], "content": m["content"]} for m in messages]
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            **self.other_configs,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.key}",
        }
        response = requests.post(url=self.url, headers=headers, json=payload)
        response.raise_for_status()
        response_data = response.json()
        message = response_data["choices"][0]["message"]
        return message.get("reasoning_content", ""), message["content"]

    def call_stream(self, messages, callback):
        messages = [{"role": m["role"], "content": m["content"]} for m in messages]
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            **self.other_configs,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.key}",
        }
        with requests.post(
            self.url, json=payload, headers=headers, stream=True
        ) as response:
            for line in response.iter_lines():
                if not line:
                    continue
                decoded_line = line.decode("utf-8")
                if decoded_line.startswith("data:"):
                    json_data = decoded_line[len("data:") :].strip()
                    if json_data == "[DONE]":
                        break
                    chunk = json.loads(json_data)
                    if len(chunk["choices"]) == 0:
                        continue
                    delta_reasoning_content = chunk["choices"][0]["delta"].get(
                        "reasoning_content", ""
                    )
                    if delta_reasoning_content is None:
                        delta_reasoning_content = ""
                    delta_content = chunk["choices"][0]["delta"].get("content", "")
                    if delta_content is None:
                        delta_content = ""
                    callback(delta_reasoning_content, delta_content)
                else:
                    try:
                        obj = json.loads(decoded_line)
                    except:
                        continue

                    if (
                        obj.get("error") is not None
                        and obj["error"].get("message") is not None
                    ):
                        raise ValueError(obj["error"]["message"])


class Agent:
    def __init__(self, name, llm_client):
        self.name = name
        self.llm_client = llm_client


class ReActAgent(Agent):
    def __init__(
        self,
        name,
        llm_client,
        logger,
        num_retries,
        summarize_num=24,
        summarize_num_keep_latest=6,
    ):
        super().__init__(name, llm_client)

        self.logger = logger
        self.num_retries = num_retries
        self.summarize_num = summarize_num
        self.summarize_num_keep_latest = summarize_num_keep_latest

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
        with open(osp.join(osp.dirname(__file__), "prompts/summarizer.md"), "r") as f:
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
            return messages, soup.final_answer.text

        name, args = ReActAgent._parse_action_tag(soup.action)
        try:
            output, pin = execute_tool(name, args)
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
                or (len(messages) - i <= self.summarize_num_keep_latest)
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

    def run(self, query):
        with open(osp.join(osp.dirname(__file__), "prompts/react.md"), "r") as f:
            react_prompt = f.read()
        dic = {
            "os": platform.platform(),
            "pwd": os.getcwd(),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "tools_list": tools_list_desc(),
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
                return final_answer


class PlanAndExecuteAgent(Agent):
    def __init__(self, name, llm_client, logger, num_retries):
        super().__init__(name, llm_client)

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
        if soup.thought is not None and soup.plan is not None:
            return soup.thought, soup.plan
        raise ValueError(f"Content format is incorrect:\n{content}")

    def _retry_one_iter(self, messages):
        for _ in range(self.num_retries + 1):
            try:
                return self._try_one_iter(messages)
            except:
                exception = traceback.format_exc()
        raise exception

    def _plan(self, query):
        with open(osp.join(osp.dirname(__file__), "prompts/planner.md"), "r") as f:
            planner_prompt = f.read()

        dic = {
            "os": platform.platform(),
            "pwd": os.getcwd(),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
        thought, plan = self._retry_one_iter(messages)
        self.logger.log(self.name, "思考", str(thought))
        self.logger.log(self.name, "计划", str(plan))

        return PlanAndExecuteAgent._parse_plan_tag(plan)

    def run(self, query):
        steps_answers = []
        steps = []

        while True:
            planner_query = f"# 当前最终目标\n{query}\n# 已完成的子任务及结果\n"
            for i in range(len(steps_answers)):
                planner_query += f"## 子任务 {i + 1}\n### 任务描述\n{steps[i]}\n### 执行结果\n````markdown\n{steps_answers[i]}\n````\n"

            new_steps = self._plan(planner_query)
            if len(new_steps) == 0:
                return steps_answers[-1]

            react_agent_id = len(steps) + 1
            react_agent = ReActAgent(
                f"{self.name} - subagent #{react_agent_id}",
                self.llm_client,
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
