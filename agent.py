import argparse
import requests
import json
import platform
import os
import os.path as osp
import re

from bs4 import BeautifulSoup, Tag


from tools import NATIVE_TOOLS_LIST


class Logger:
    def __init__(self, filename):
        self.f = open(filename, "w")

    def log(self, section, content):
        self.f.write(
            json.dumps({"section": section, "content": content}, ensure_ascii=False)
            + "\n"
        )
        self.f.flush()

    def __del__(self):
        self.f.close()


def call_llm(config, messages, callback):
    payload = {
        "model": config["model"],
        "messages": messages,
        "stream": True,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config['key']}",
    }
    with requests.post(
        config["url"], json=payload, headers=headers, stream=True
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
                delta_reasoning_content = chunk["choices"][0]["delta"].get(
                    "reasoning_content", ""
                )
                if delta_reasoning_content is None:
                    delta_reasoning_content = ""
                delta_content = chunk["choices"][0]["delta"].get("content", "")
                if delta_content is None:
                    delta_content = ""
                callback(delta_reasoning_content, delta_content)


def execute_action(action: Tag) -> str:
    tools_dic = {i["name"]: i["func"] for i in NATIVE_TOOLS_LIST}

    root = action.find()
    tool_name = root.name
    dic = {}
    for j in root.children:
        if not isinstance(j, Tag):
            continue
        argument_name = j.name
        argument_value = j.text
        dic[argument_name] = argument_value
    func = tools_dic[tool_name]
    func_args_str = ",".join([f'{k}="{v}"' for k, v in dic.items()])
    func_invoke_str = f"{tool_name}({func_args_str})"

    soup = BeautifulSoup(features="xml")
    node = soup.new_tag("observation")
    node.string = f"工具调用：\n{func_invoke_str}\n\n工具调用结果：{func(**dic)}\n"
    return str(node)


def agent(config, question, log):
    logger = Logger(log)

    with open(osp.join(osp.dirname(__file__), "agent_system_prompt.md"), "r") as f:
        agent_system_prompt = f.read()
    dic = {
        "os": platform.platform(),
        "tools_list": "\n\n".join([i["desc"] for i in NATIVE_TOOLS_LIST]),
        "pwd": os.getcwd(),
    }
    agent_system_prompt = agent_system_prompt.format(**dic)

    soup = BeautifulSoup(features="xml")
    node = soup.new_tag("question")
    node.string = question
    messages = [
        {"role": "system", "content": agent_system_prompt},
        {
            "role": "user",
            "content": str(node),
        },
    ]
    logger.log("用户提问", str(node))

    while True:
        reasoning_content = ""
        content = ""

        def callback(r, c):
            nonlocal reasoning_content
            nonlocal content
            reasoning_content += r
            content += c

        call_llm(config, messages, callback)

        soup = BeautifulSoup(content, features="lxml")
        logger.log("思考", str(soup.thought))

        if soup.final_answer is not None:
            logger.log("最终答案", str(soup.final_answer))
            break

        logger.log("行动", str(soup.action))

        observation = execute_action(soup.action)
        logger.log("观察结果", observation)
        messages.append({"role": "user", "content": observation})


if __name__ == "__main__":
    parser = argparse.ArgumentParser("agent")
    parser.add_argument("--config")
    parser.add_argument("--question")
    parser.add_argument("--log")
    args = parser.parse_args()

    with open(args.config, "r") as f:
        config = json.load(f)

    agent(config, args.question, args.log)
