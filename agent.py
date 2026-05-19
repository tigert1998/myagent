import requests
import json
import platform
import os.path as osp
import os
from datetime import datetime
import traceback

from bs4 import BeautifulSoup, Tag

from tools import execute_tool, tools_list_desc


class Agent:
    def __init__(self, name, url, model, key, other_configs):
        self.name = name
        self.url = url
        self.model = model
        self.key = key
        self.other_configs = other_configs

    def call_llm(self, messages, callback):
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


class ReActAgent(Agent):
    def __init__(
        self,
        name,
        url,
        model,
        key,
        other_configs,
        logger,
        num_retries,
        summarize_num=24,
        summarize_num_keep_latest=6,
    ):
        super().__init__(name, url, model, key, other_configs)

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

        reasoning_content = ""
        content = ""

        def callback(r, c):
            nonlocal reasoning_content
            nonlocal content
            reasoning_content += r
            content += c

        self.call_llm(messages, callback)

        summarization = ReActAgent._build_single_node_xml("summarization", content)
        self.logger.log(self.name, "阶段总结", str(summarization))
        return content

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

        reasoning_content = ""
        content = ""

        def callback(r, c):
            nonlocal reasoning_content
            nonlocal content
            reasoning_content += r
            content += c

        while True:
            success = False
            fail_reason = None

            for _ in range(self.num_retries + 1):
                reasoning_content = ""
                content = ""
                self.call_llm(messages, callback)

                soup = BeautifulSoup(content, features="lxml")
                if soup.action is None and soup.final_answer is None:
                    fail_reason = f"Content format is incorrect:\n{content}"
                    continue
                if soup.thought is None:
                    thought = ReActAgent._build_single_node_xml("thought", "")
                else:
                    thought = soup.thought

                if soup.final_answer is not None:
                    self.logger.log(self.name, "思考", str(thought))
                    self.logger.log(self.name, "最终答案", str(soup.final_answer))
                    return soup.final_answer.text

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
                messages.append(
                    {
                        "role": "assistant",
                        "content": str(thought) + str(soup.action),
                        "meta": {"pin": pin},
                    }
                )
                messages.append(
                    {
                        "role": "user",
                        "content": str(observation),
                        "meta": {"pin": pin},
                    }
                )

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

                success = True
                break

            if not success:
                raise ValueError(fail_reason)


class PlanAndExecuteAgent(Agent):
    def __init__(self, name, url, model, key, other_configs, logger, num_retries):
        super().__init__(name, url, model, key, other_configs)

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

        reasoning_content = ""
        content = ""

        def callback(r, c):
            nonlocal reasoning_content
            nonlocal content
            reasoning_content += r
            content += c

        success = False
        fail_reason = None
        for _ in range(self.num_retries + 1):
            reasoning_content = ""
            content = ""
            self.call_llm(messages, callback)

            soup = BeautifulSoup(content, features="lxml")
            if soup.thought is not None and soup.plan is not None:
                success = True
                break
            else:
                fail_reason = f"Content format is incorrect:\n{content}"

        if not success:
            raise ValueError(fail_reason)

        self.logger.log(self.name, "思考", str(soup.thought))
        self.logger.log(self.name, "计划", str(soup.plan))

        return PlanAndExecuteAgent._parse_plan_tag(soup.plan)

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
                self.url,
                self.model,
                self.key,
                self.other_configs,
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
