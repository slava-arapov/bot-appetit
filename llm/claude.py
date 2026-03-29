import asyncio
import anthropic

from .base import BaseLLMClient


class ClaudeClient(BaseLLMClient):
    def __init__(self, api_key: str, model: str = "claude-haiku-4-5-20251001"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    async def chat(self, system: str, messages: list[dict]) -> str:
        def _call():
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=system,
                messages=messages,
            )
            return response.content[0].text

        return await asyncio.to_thread(_call)
