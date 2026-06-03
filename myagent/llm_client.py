from typing import Any
import requests


class LLMUsage:
    completion_tokens: int
    prompt_cache_hit_tokens: int
    prompt_cache_miss_tokens: int

    def __init__(self) -> None:
        self.completion_tokens = 0
        self.prompt_cache_hit_tokens = 0
        self.prompt_cache_miss_tokens = 0

    @property
    def prompt_tokens(self) -> int:
        return self.prompt_cache_hit_tokens + self.prompt_cache_miss_tokens

    def report(self) -> str:
        return "\n".join(
            [
                "## Usage",
                f"- completion tokens: {self.completion_tokens}",
                f"- prompt tokens: {self.prompt_tokens}",
                f"- cache hit rate: {self.prompt_cache_hit_tokens / self.prompt_tokens * 100:.2f}%",
            ]
        )


class LLMResponse:
    reasoning_content: str
    content: str
    tool_calls: list[dict[str, Any]]
    usage: LLMUsage

    def __init__(self) -> None:
        self.reasoning_content = ""
        self.content = ""
        self.tool_calls = []
        self.usage = LLMUsage()


class LLMClient:
    def call(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMResponse:
        raise NotImplementedError()

    @staticmethod
    def build(config: dict[str, Any]) -> "LLMClient":
        provider: str = config.get("provider", "")
        if provider == "deepseek":
            return DeepSeekClient(
                config["url"],
                config["model"],
                config["key"],
                config.get("other_configs", {}),
            )
        raise ValueError(f"Invalid LLM provider: {provider}")


class DeepSeekClient(LLMClient):
    def __init__(
        self, url: str, model: str, key: str, other_configs: dict[str, Any]
    ) -> None:
        self.url: str = url
        self.model: str = model
        self.key: str = key
        self.other_configs: dict[str, Any] = other_configs

    def call(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "tools": tools,
            **self.other_configs,
        }
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.key}",
        }
        response: requests.Response = requests.post(
            url=self.url, headers=headers, json=payload
        )
        response.raise_for_status()
        response_data: dict[str, Any] = response.json()
        message: dict[str, Any] = response_data["choices"][0]["message"]
        usage: dict[str, Any] = response_data["usage"]

        output = LLMResponse()
        output.reasoning_content = message.get("reasoning_content", "")
        output.content = message.get("content", "")
        output.tool_calls = message.get("tool_calls", [])
        output.usage.completion_tokens = usage["completion_tokens"]
        output.usage.prompt_cache_hit_tokens = usage["prompt_cache_hit_tokens"]
        output.usage.prompt_cache_miss_tokens = usage["prompt_cache_miss_tokens"]
        return output
