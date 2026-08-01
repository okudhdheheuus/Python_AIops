"""用户个人配置 —— LLM API Key + Agent 偏好"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import User, UserAgentConfig, UserLLMConfig
from ..schemas import (
    UserAgentConfigOut,
    UserAgentConfigUpdate,
    UserLLMConfigOut,
    UserLLMConfigUpdate,
)
from ..utils.security import get_current_active_user

router = APIRouter()
logger = logging.getLogger("itops")


def _mask_api_key(key: str | None) -> str | None:
    """遮盖 API Key，只显示后4位"""
    if not key:
        return None
    if len(key) <= 4:
        return "****"
    return "****" + key[-4:]


# ── LLM 配置 ──

@router.get("/llm-config", response_model=UserLLMConfigOut)
async def get_llm_config(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserLLMConfig).where(UserLLMConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()
    if config:
        out = UserLLMConfigOut.model_validate(config)
        out.api_key = _mask_api_key(config.api_key)
        return out
    return UserLLMConfigOut(
        id="",
        user_id=current_user.id,
        provider="glm",
        api_key=None,
        api_base=None,
        model=None,
    )


@router.put("/llm-config", response_model=UserLLMConfigOut)
async def upsert_llm_config(
    body: UserLLMConfigUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserLLMConfig).where(UserLLMConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()

    if config:
        if body.provider is not None:
            config.provider = body.provider
        if body.api_key is not None:
            config.api_key = body.api_key
        if body.api_base is not None:
            config.api_base = body.api_base
        if body.model is not None:
            config.model = body.model
    else:
        config = UserLLMConfig(
            user_id=current_user.id,
            provider=body.provider,
            api_key=body.api_key,
            api_base=body.api_base,
            model=body.model,
        )
        db.add(config)

    await db.commit()
    await db.refresh(config)

    out = UserLLMConfigOut.model_validate(config)
    out.api_key = _mask_api_key(config.api_key)
    return out


# ── Agent 配置 ──

@router.get("/agent-config", response_model=UserAgentConfigOut)
async def get_agent_config(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserAgentConfig).where(UserAgentConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()
    if config:
        return UserAgentConfigOut.model_validate(config)
    return UserAgentConfigOut(
        id="",
        user_id=current_user.id,
        active_agents=[],
        default_agent="generic",
        preferences={},
    )


@router.put("/agent-config", response_model=UserAgentConfigOut)
async def upsert_agent_config(
    body: UserAgentConfigUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserAgentConfig).where(UserAgentConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()

    if config:
        if body.active_agents is not None:
            import json
            config.active_agents = json.dumps(body.active_agents, ensure_ascii=False)
        if body.default_agent is not None:
            config.default_agent = body.default_agent
        if body.preferences is not None:
            import json
            config.preferences = json.dumps(body.preferences, ensure_ascii=False)
    else:
        import json
        config = UserAgentConfig(
            user_id=current_user.id,
            active_agents=json.dumps(body.active_agents, ensure_ascii=False) if body.active_agents else None,
            default_agent=body.default_agent,
            preferences=json.dumps(body.preferences, ensure_ascii=False) if body.preferences else None,
        )
        db.add(config)

    await db.commit()
    await db.refresh(config)
    return UserAgentConfigOut.model_validate(config)
