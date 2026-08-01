"""GLM (智谱) Provider —— 基于 OpenAI 兼容 API，默认使用免费 glm-4-flash 模型"""
from ...config import settings
from .openai_provider import OpenAIProvider


class GLMProvider(OpenAIProvider):
    def __init__(self, api_key: str | None = None, api_base: str | None = None, model: str | None = None):
        super().__init__(
            api_key=api_key or settings.glm_api_key,
            api_base=api_base or "https://open.bigmodel.cn/api/paas/v4",
            model=model or "glm-4-flash",
        )

    def get_provider_name(self) -> str:
        return "glm"
