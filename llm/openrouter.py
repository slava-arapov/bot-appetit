import asyncio
from openai import OpenAI

from .base import BaseLLMClient


class OpenRouterClient(BaseLLMClient):
    def __init__(self, api_key: str, model: str = "anthropic/claude-haiku-4-5"):
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )
        self.model = model

    async def chat(self, system: str, messages: list[dict]) -> str:
        def _call():
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system}] + messages,
                max_tokens=1024,
            )
            return response.choices[0].message.content

        return await asyncio.to_thread(_call)
