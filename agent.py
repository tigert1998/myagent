import requests
import json
import platform
import os.path as osp
import os

from bs4 import BeautifulSoup, Tag

from tools import execute_tool, tools_list_desc


class Agent:
    def __init__(self, url, model, key):
        self.url = url
        self.model = model
        self.key = key

    def call_llm(self, messages, callback):
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
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


class ReActAgent(Agent):
    def __init__(self, url, model, key, logger):
        super().__init__(url, model, key)

        self.logger = logger

    @staticmethod
    def parse_action_tag(action: Tag):
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
    def build_single_node_xml(name, content):
        soup = BeautifulSoup(features="xml")
        node = soup.new_tag(name)
        node.string = content
        return node

    def run(self, query):
        with open(osp.join(osp.dirname(__file__), "react_prompt.md"), "r") as f:
            react_prompt = f.read()
        dic = {
            "os": platform.platform(),
            "tools_list": tools_list_desc(),
            "pwd": os.getcwd(),
        }
        react_prompt = react_prompt.format(**dic)

        node = ReActAgent.build_single_node_xml("question", query)
        messages = [
            {"role": "system", "content": react_prompt},
            {
                "role": "user",
                "content": str(node),
            },
        ]
        self.logger.log("用户提问", str(node))

        while True:
            reasoning_content = ""
            content = ""

            def callback(r, c):
                nonlocal reasoning_content
                nonlocal content
                reasoning_content += r
                content += c

            while True:
                self.call_llm(messages, callback)
                soup = BeautifulSoup(content, features="lxml")
                if soup.thought is not None and (
                    soup.action is not None or soup.final_answer is not None
                ):
                    break

            self.logger.log("思考", str(soup.thought))

            if soup.final_answer is not None:
                self.logger.log("最终答案", str(soup.final_answer))
                break

            self.logger.log("行动", str(soup.action))

            name, args = ReActAgent.parse_action_tag(soup.action)
            output = execute_tool(name, args)
            observation = ReActAgent.build_single_node_xml("observation", output)

            self.logger.log("观察结果", str(observation))
            messages.append(
                {"role": "assistant", "content": str(soup.thought) + str(soup.action)}
            )
            messages.append({"role": "user", "content": str(observation)})
