import argparse
import requests
import json
import platform
import os.path as osp
import re
import xml.etree.ElementTree as ET

from tools import NATIVE_TOOLS_LIST


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
                delta_content = chunk["choices"][0]["delta"].get("content", "")
                callback(delta_reasoning_content, delta_content)


def execute_action(action: str):
    tools_dic = {i["name"]: i["func"] for i in NATIVE_TOOLS_LIST}

    root = ET.fromstring(action)
    for i in root:
        tool_name = i.tag
        dic = {}
        for j in i:
            argument_name = j.tag
            argument_value = j.text
            dic[argument_name] = argument_value
        func = tools_dic[tool_name]

        func_args_str = ",".join([f'{k}="{v}"' for k, v in dic.items()])
        func_invoke_str = f"{tool_name}({func_args_str})"

        node = ET.Element("observation")
        node.text = f"工具调用：\n{func_invoke_str}\n\n工具调用结果：{func(**dic)}\n"
        return ET.tostring(node)


def agent(config, question, log):
    log_file = open(log, "w")

    with open(osp.join(osp.dirname(__file__), "agent_system_prompt.md"), "r") as f:
        agent_system_prompt = f.read()
    dic = {
        "os": platform.platform(),
        "tools_list": "\n\n".join([i["desc"] for i in NATIVE_TOOLS_LIST]),
    }
    agent_system_prompt = agent_system_prompt.format(**dic)

    messages = [
        {"role": "system", "content": agent_system_prompt},
        {"role": "user", "content": question},
    ]
    log_file.write("【用户提问】\n" + question)
    while True:
        content = ""

        def callback(r, c):
            content += c

        call_llm(config, messages, callback)

        thought_match = re.search(r"<thought>(.*?)</thought>", content, re.DOTALL)
        thought = thought_match.group(1)
        log_file.write("【思考】\n" + thought)

        final_answer_match = re.search(
            r"<final_answer>(.*?)</final_answer>", content, re.DOTALL
        )
        if final_answer_match is not None:
            log_file.write("【最终答案】\n" + final_answer_match.group(1))
            break

        action_match = re.search(r"<action>(.*?)</action>", content, re.DOTALL)
        action = action_match.group(1)
        log_file.write("【行动】\n" + action)

        observation = execute_action(action)
        log_file.write("【观察结果】\n" + observation)
        messages.append({"role": "user", "content": observation})

    log_file.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser("agent")
    parser.add_argument("--config")
    parser.add_argument("--question")
    parser.add_argument("--log")
    args = parser.parse_args()

    with open(args.config, "r") as f:
        config = json.load(f)

    agent(config, args.question, args.log)
