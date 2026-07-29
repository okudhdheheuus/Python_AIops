from ...config import settings
from .base import BaseLLMProvider
from .deepseek_provider import DeepSeekProvider
from .openai_provider import OpenAIProvider

_providers = {}

def get_llm_provider() -> BaseLLMProvider:
    """获取LLM Provider实例（单例模式，每个provider只创建一个示例）"""
    provider_name = settings.llm_provider
    if provider_name not in _providers:
        if provider_name == "deepseek":
            _providers[provider_name] = DeepSeekProvider()
        elif provider_name == "openai":
            _providers[provider_name] = OpenAIProvider()
        else:
            raise ValueError(f"不支持的LLM Provider: {provider_name}")
    return _providers[provider_name]