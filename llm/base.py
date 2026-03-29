from abc import ABC, abstractmethod


class BaseLLMClient(ABC):
    @abstractmethod
    async def chat(self, system: str, messages: list[dict]) -> str:
        """Возвращает строку — raw ответ модели."""
        pass
