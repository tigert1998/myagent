import requests


class LLMClient:
    @staticmethod
    def build(config):
        provider = config.get("provider")
        if provider == "deepseek":
            return DeepSeekClient(
                config["url"],
                config["model"],
                config["key"],
                config.get("other_configs", {}),
            )
        raise ValueError(f"Invalid LLM provider: {provider}")


class DeepSeekClient(LLMClient):
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
