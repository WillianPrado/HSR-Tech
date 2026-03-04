from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional, TypedDict


class ChatMessage(TypedDict):
    role: str
    content: str


class ILLMClient(ABC):
    @abstractmethod
    async def send_message(
        self,
        message: str,
        model: str,
        response_format: Optional[dict] = None,
    ) -> Optional[str]:
        pass

    @abstractmethod
    async def stream_message(
        self,
        message: str,
        model: str,
        response_format: Optional[dict] = None,
    ) -> AsyncGenerator[str, None]:
        pass

    @abstractmethod
    async def stream_messages(
        self,
        messages: list[ChatMessage],
        model: str,
        response_format: Optional[dict] = None,
    ) -> AsyncGenerator[str, None]:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass
