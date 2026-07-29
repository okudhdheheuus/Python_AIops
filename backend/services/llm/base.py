
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class BaseLLMProvider(ABC):
    """所有 LLM Provider 必须实现此接口"""

    @abstractmethod
    async def chat(self,messages:list[dict],temperature:float=0.7,max_tokens:int=2000) -> str:
        """同步调用 —— 等待完整响应后返回"""
        ...
    @abstractmethod
    async def chat_stream(self, messages:list[dict], temperature:float=0.7, max_tokens:int=2000) -> AsyncIterator[str]:
        """流式调用 —— 逐个返回响应片段"""
        ...
    @abstractmethod
    def get_provider_name(self) -> str:
        """返回provider 名称，用于日志和指标"""
        ...

