from abc import ABC, abstractmethod


class BaseLLMClient(ABC):
    @abstractmethod
    async def chat(self, system: str, messages: list[dict]) -> tuple[str, str]:
        """Возвращает (raw ответ модели, название модели)."""
        pass
