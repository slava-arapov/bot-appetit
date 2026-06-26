from openrouter import OpenRouter

from .base import BaseLLMClient


class OpenRouterClient(BaseLLMClient):
    def __init__(self, api_key: str, models: list[str]):
        self.api_key = api_key
        self.models = models

    async def chat(self, system: str, messages: list[dict]) -> tuple[str, str]:
        async with OpenRouter(api_key=self.api_key) as client:
            response = await client.chat.send_async(
                models=self.models,
                provider={"sort": "throughput", "data_collection": "allow"},
                messages=[{"role": "system", "content": system}] + messages,
                response_format={"type": "json_object"},
                stream=False,
            )
        return response.choices[0].message.content, response.model
