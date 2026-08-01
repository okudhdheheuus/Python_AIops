from typing import Any

from ...config import settings
from .base import BaseLLMProvider
from .deepseek_provider import DeepSeekProvider
from .glm_provider import GLMProvider
from .openai_provider import OpenAIProvider

_providers: dict[str, BaseLLMProvider] = {}


def get_llm_provider(user_config: Any = None) -> BaseLLMProvider:
    """获取LLM Provider实例。

    每个用户必须配置自己的 API Key，不再使用全局共享 Key。
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
        elif provider_name == "glm":
            return GLMProvider(
                api_key=user_config.api_key,
                api_base=getattr(user_config, "api_base", None) or None,
                model=getattr(user_config, "model", None) or None,
            )
        else:
            raise ValueError(f"不支持的LLM Provider: {provider_name}")

    raise ValueError(
        "请先在 API 设置页面配置您的 LLM API Key。"
        "可以前往 https://open.bigmodel.cn/ 免费申请 GLM-4-Flash API Key。"
    )
