from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..database import get_db
from ..models import NotificationChannel, User
from ..utils.security import get_current_active_user
from ..services.notification_service import ALLOWED_TYPES, _dispatch

router = APIRouter()

CHANNEL_TYPE_LABELS = {
    "wecom": "企业微信",
    "dingtalk": "钉钉",
    "feishu": "飞书",
    "email": "邮件",
}


def _mask_url(url: str) -> str:
    """脱敏 webhook URL，仅显示首尾各 12 字符"""
    if len(url) <= 28:
        return url[:12] + "***"
    return url[:12] + "****" + url[-12:]


def _serialize_channel(c) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "channel_type": c.channel_type,
        "channel_type_label": CHANNEL_TYPE_LABELS.get(c.channel_type, c.channel_type),
        "webhook_url": _mask_url(c.webhook_url),
        "has_sign_secret": bool(c.sign_secret),
        "enabled": c.enabled,
        "created_at": str(c.created_at) if c.created_at else None,
    }


@router.get("/channels")
async def list_channels(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """列出通知渠道"""
    result = await db.execute(
        select(NotificationChannel).order_by(NotificationChannel.created_at.desc())
    )
    channels = result.scalars().all()
    return {
        "total": len(channels),
        "items": [_serialize_channel(c) for c in channels],
    }


@router.post("/channels", status_code=201)
async def create_channel(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """创建通知渠道"""
    if current_user.role not in ["admin"]:
        raise HTTPException(status_code=403, detail="仅管理员可操作")

    channel_type = body.get("channel_type", "")
    if channel_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"不支持的渠道类型: {channel_type}，可选: {', '.join(sorted(ALLOWED_TYPES))}",
        )

    channel = NotificationChannel(
        name=body["name"],
        channel_type=channel_type,
        webhook_url=body["webhook_url"],
        sign_secret=body.get("sign_secret"),
        enabled=body.get("enabled", True),
    )
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    return {
        "id": channel.id,
        "name": channel.name,
        "channel_type": channel.channel_type,
    }


@router.get("/channels/{channel_id}")
async def get_channel(
    channel_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取单个渠道详情（含完整 webhook_url，供编辑使用）"""
    channel = await db.get(NotificationChannel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="渠道不存在")
    return {
        "id": channel.id,
        "name": channel.name,
        "channel_type": channel.channel_type,
        "channel_type_label": CHANNEL_TYPE_LABELS.get(channel.channel_type, channel.channel_type),
        "webhook_url": channel.webhook_url,
        "has_sign_secret": bool(channel.sign_secret),
        "enabled": channel.enabled,
        "created_at": str(channel.created_at) if channel.created_at else None,
    }


@router.delete("/channels/{channel_id}")
async def delete_channel(
    channel_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """删除通知渠道"""
    if current_user.role not in ["admin"]:
        raise HTTPException(status_code=403, detail="仅管理员可操作")

    channel = await db.get(NotificationChannel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="渠道不存在")
    await db.delete(channel)
    await db.commit()
    return {"status": "deleted"}


@router.put("/channels/{channel_id}")
async def update_channel(
    channel_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """更新通知渠道"""
    if current_user.role not in ["admin"]:
        raise HTTPException(status_code=403, detail="仅管理员可操作")

    channel = await db.get(NotificationChannel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="渠道不存在")

    if "channel_type" in body and body["channel_type"] not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"不支持的渠道类型: {body['channel_type']}，可选: {', '.join(sorted(ALLOWED_TYPES))}",
        )

    for field in ("name", "channel_type", "webhook_url", "enabled", "sign_secret"):
        if field in body:
            # sign_secret 为空字符串时清空
            if field == "sign_secret" and body[field] == "":
                setattr(channel, field, None)
            else:
                setattr(channel, field, body[field])
    await db.commit()
    return {"status": "updated"}


@router.post("/channels/{channel_id}/test")
async def test_channel(
    channel_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """发送测试消息到指定渠道"""
    if current_user.role not in ["admin"]:
        raise HTTPException(status_code=403, detail="仅管理员可操作")

    channel = await db.get(NotificationChannel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="渠道不存在")

    test_content = (
        f"✅ **ITOps 测试消息**\n\n"
        f"> 渠道名称: {channel.name}\n"
        f"> 渠道类型: {CHANNEL_TYPE_LABELS.get(channel.channel_type, channel.channel_type)}\n"
        f"> 发送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"> 状态: 配置正常，消息发送成功！\n"
    )

    try:
        await _dispatch(channel, test_content)
        return {"status": "success", "message": "测试消息发送成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送失败: {str(e)}")
