from typing import Any

from .llm import get_llm_provider


async def call_llm(
    prompt: str,
    system_prompt: str = "You are a helpful assistant.",
    temperature: float = 0.7,
    max_tokens: int = 2000,
    user_llm_config: Any = None,
) -> str:
    provider = get_llm_provider(user_llm_config)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]
    return await provider.chat(messages, temperature=temperature, max_tokens=max_tokens)


async def call_deepseek(prompt: str, system_prompt: str = "", temperature: float = 0.7) -> str:
    return await call_llm(prompt, system_prompt)


async def call_openai(prompt: str, system_prompt: str = "You are a helpful assistant.") -> str:
    return await call_llm(prompt, system_prompt)
