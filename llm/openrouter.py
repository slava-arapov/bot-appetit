import asyncio
from openai import OpenAI

from .base import BaseLLMClient


class OpenRouterClient(BaseLLMClient):
    def __init__(self, api_key: str, models: list[str]):
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )
        self.models = models

    async def chat(self, system: str, messages: list[dict]) -> tuple[str, str]:
        def _call():
            response = self.client.chat.completions.create(
                model=self.models[0],
                extra_body={
                    "models": self.models,
                    "provider": {"sort": "price", "data_collection": "allow"},
                },
                messages=[{"role": "system", "content": system}] + messages,
                max_tokens=1024,
            )
            return response.choices[0].message.content, response.model

        return await asyncio.to_thread(_call)
