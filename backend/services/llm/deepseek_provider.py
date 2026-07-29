
import time
import logging
import httpx
from typing import AsyncIterator

from httpx import AsyncClient

from .base import BaseLLMProvider
from ...config import settings
from ...metrics import llm_requests_total,llm_request_duration_seconds,llm_tokens_total
logger = logging.getLogger("itops")
class DeepSeekProvider(BaseLLMProvider):
    def __init__(self):
        self.api_key = settings.deepseek_api_key
        self.api_base = settings.deepseek_api_base.rstrip("/")
        self.model = settings.deepseek_model
        self._client: httpx.AsyncClient | None = None

    def get_provider_name(self) -> str:
        return "DeepSeek"
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.api_base,
                headers={
                    "Authorization":f"Bearer {self.api_key}",
                    "Content-Type":"application/json",
                },
                timeout = 60.0
            )
        return self._client

    async def chat(
        self,messages: list[dict],temperature:float = 0.7,max_tokens:int=2000
    ) -> str:
        provider = self.get_provider_name()
        start = time.perf_counter()
        try:
            client = await self._get_client()
            resp = await client.post("/chat/completions",
                json={
                    "model":self.model,
                    "messages":messages,
                    "temperature":temperature,
                    "max_tokens":max_tokens,
                    "stream":False
                })
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            # 记录指标
            llm_requests_total.labels(provider=provider, status="success").inc()
            llm_request_duration_seconds.labels(provider=provider).observe(time.perf_counter() - start)
            usage = data.get("usage",{})
            llm_tokens_total.labels(provider=provider,type="completion").inc(
                usage.get("completion_tokens",0)
            )
            return content
        except Exception:
            llm_requests_total.labels(provider=provider, status="error").inc().inc()
            logger.exception(f"{provider} API call failed")
            raise

    async def chat_stream(
        self,messages:list[dict],temperature:float = 0.7,
        max_tokens:int = 2000
    )-> AsyncIterator[str]:
        provider = self.get_provider_name()
        start = time.perf_counter()
        try:
            client = await self._get_client()
            async with client.stream("POST","/chat/completions",json={
                "model":self.model,
                "messages":messages,
                "temperature":temperature,
                "max_tokens":max_tokens,
                "stream":True
            }) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        import json
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content

            llm_requests_total.labels(provider=provider, status="success").inc()
            llm_request_duration_seconds.labels(provider=provider).observe(time.perf_counter() - start)
        except Exception:
            llm_requests_total.labels(provider=provider, status="error").inc()
            logger.exception(f"{provider} streaming failed")
            raise




















