from typing import Any
import requests


class LLMClient:
    def call(
        self, messages: list[dict[str, Any]]
    ) -> tuple[str, str, list[dict[str, Any]]]:
        """Returns (reasoning_content, content)."""
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
        self, messages: list[dict[str, Any]]
    ) -> tuple[str, str, list[dict[str, Any]]]:
        messages = [{"role": m["role"], "content": m["content"]} for m in messages]
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
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
        return (
            message.get("reasoning_content", ""),
            message.get("content", ""),
            message.get("tool_calls", []),
        )
