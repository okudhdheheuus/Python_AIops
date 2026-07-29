from typing import Any

from ...config import settings
from .base import BaseLLMProvider
from .deepseek_provider import DeepSeekProvider
from .openai_provider import OpenAIProvider

_providers: dict[str, BaseLLMProvider] = {}


def get_llm_provider(user_config: Any = None) -> BaseLLMProvider:
    """获取LLM Provider实例。

    user_config 有 api_key 时创建独立 provider（按用户计费），
    否则回退到全局单例（共享 key）。
    """
    if user_config and user_config.api_key:
        provider_name = getattr(user_config, "provider", None) or settings.llm_provider
        if provider_name == "deepseek":
            return DeepSeekProvider(
                api_key=user_config.api_key,
                api_base=getattr(user_config, "api_base", None) or None,
                model=getattr(user_config, "model", None) or None,
            )
        elif provider_name == "openai":
            return OpenAIProvider(
                api_key=user_config.api_key,
                api_base=getattr(user_config, "api_base", None) or None,
                model=getattr(user_config, "model", None) or None,
            )
        else:
            raise ValueError(f"不支持的LLM Provider: {provider_name}")

    # 全局单例（缓存）
    provider_name = settings.llm_provider
    if provider_name not in _providers:
        if provider_name == "deepseek":
            _providers[provider_name] = DeepSeekProvider()
        elif provider_name == "openai":
            _providers[provider_name] = OpenAIProvider()
        else:
            raise ValueError(f"不支持的LLM Provider: {provider_name}")
    return _providers[provider_name]
