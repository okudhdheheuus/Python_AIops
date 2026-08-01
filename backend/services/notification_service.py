"""通知服务 —— 支持企业微信/钉钉/飞书/邮件多渠道告警推送"""

import asyncio
import base64
import hashlib
import hmac
import logging
import smtplib
import time
import urllib.parse
from datetime import datetime, timezone
from email.mime.text import MIMEText

import httpx
from sqlalchemy import select

from ..config import settings
from ..database import AsyncSessionLocal
from ..models import NotificationChannel

logger = logging.getLogger("notification")

MAX_RETRIES = 3
ALLOWED_TYPES = {"wecom", "dingtalk", "feishu", "email"}


async def _get_channels_for_owner(owner_id: str | None = None):
    """获取某用户自己的启用通知渠道（多租户隔离，不含全局渠道）"""
    if not owner_id:
        return []
    async with AsyncSessionLocal() as db:
        stmt = select(NotificationChannel).where(
            NotificationChannel.enabled == True,
            NotificationChannel.owner_id == owner_id,
        )
        result = await db.execute(stmt)
        return result.scalars().all()


async def send_notification(
    alert_name: str, summary: str, severity: str, instance: str,
    owner_id: str | None = None,
):
    """向相关用户的启用的通知渠道发送告警消息"""
    channels = await _get_channels_for_owner(owner_id)

    if not channels:
        logger.debug("没有启用的通知渠道，跳过通知")
        return

    content = _format_message(alert_name, summary, severity, instance)

    for channel in channels:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                await _dispatch(channel, content)
                logger.info(f"通知已发送: channel={channel.name}, alert={alert_name}")
                break
            except Exception as e:
                logger.warning(
                    f"通知发送失败 (attempt {attempt}/{MAX_RETRIES}): "
                    f"channel={channel.name}, error={e}"
                )
                if attempt == MAX_RETRIES:
                    logger.error(f"通知最终失败: channel={channel.name}")


async def send_recovery_notification(
    alert_name: str, instance: str, resolved_at: str,
    owner_id: str | None = None,
):
    """向相关用户的启用的通知渠道发送告警恢复消息"""
    channels = await _get_channels_for_owner(owner_id)

    if not channels:
        return

    content = (
        f"✅ **ITOps 告警恢复**\n\n"
        f"> 告警名称: {alert_name}\n"
        f"> 实例: {instance}\n"
        f"> 恢复时间: {resolved_at}\n"
    )

    for channel in channels:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                await _dispatch(channel, content)
                break
            except Exception as e:
                logger.warning(
                    f"恢复通知发送失败 (attempt {attempt}/{MAX_RETRIES}): "
                    f"channel={channel.name}, error={e}"
                )


def _format_message(alert_name: str, summary: str, severity: str, instance: str) -> str:
    emoji = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(severity, "❓")
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"{emoji} **ITOps 告警通知**\n\n"
        f"> 告警名称: {alert_name}\n"
        f"> 严重级别: {severity}\n"
        f"> 实例: {instance}\n"
        f"> 摘要: {summary}\n"
        f"> 时间: {now}\n"
    )


async def _dispatch(channel: NotificationChannel, content: str):
    """按渠道类型分发消息"""
    channel_type = channel.channel_type
    webhook_url = channel.webhook_url

    if channel_type in ("dingtalk", "dingtalk_webhook"):
        await _send_dingtalk(webhook_url, channel.sign_secret, content)
    elif channel_type in ("wecom", "wecom_webhook"):
        await _send_wecom(webhook_url, content)
    elif channel_type == "feishu":
        await _send_feishu(webhook_url, channel.sign_secret, content)
    elif channel_type == "email":
        await _send_email(webhook_url, content)
    else:
        await _send_generic(webhook_url, content)


# ─── DingTalk ────────────────────────────────────────────────

def _dingtalk_sign(secret: str) -> tuple:
    """生成钉钉加签参数: (timestamp, sign)"""
    ts = str(round(time.time() * 1000))
    sign_str = f"{ts}\n{secret}"
    h = hmac.new(secret.encode("utf-8"), sign_str.encode("utf-8"), hashlib.sha256)
    sign = base64.b64encode(h.digest()).decode("utf-8")
    sign = urllib.parse.quote_plus(sign)  # URL 编码（Base64 含 +/=）
    return ts, sign


async def _send_dingtalk(url: str, secret: str | None, content: str):
    """发送钉钉机器人消息，支持加签"""
    if secret:
        ts, sign = _dingtalk_sign(secret)
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}timestamp={ts}&sign={sign}"

    payload = {
        "msgtype": "markdown",
        "markdown": {"title": "ITOps 告警", "text": content},
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, json=payload)
        _check_webhook_response("钉钉", resp)


# ─── WeCom ───────────────────────────────────────────────────

async def _send_wecom(url: str, content: str):
    """发送企业微信机器人消息"""
    payload = {
        "msgtype": "markdown",
        "markdown": {"content": content},
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, json=payload)
        _check_webhook_response("企业微信", resp)


# ─── Feishu ──────────────────────────────────────────────────

async def _send_feishu(url: str, secret: str | None, content: str):
    """发送飞书机器人消息，支持加签"""
    if secret:
        ts = str(int(time.time()))
        sign_str = f"{ts}\n{secret}"
        h = hmac.new(secret.encode("utf-8"), sign_str.encode("utf-8"), hashlib.sha256)
        sign = base64.b64encode(h.digest()).decode("utf-8")
        sign = urllib.parse.quote_plus(sign)
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}timestamp={ts}&sign={sign}"

    # 使用 markdown 内容（飞书 interactive 卡片内嵌 markdown）
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "ITOps 告警通知"},
                "template": "red",
            },
            "elements": [{"tag": "markdown", "content": content}],
        },
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, json=payload)
        _check_webhook_response("飞书", resp)


# ─── Email ───────────────────────────────────────────────────

async def _send_email(recipients: str, content: str):
    """通过SMTP发送邮件，recipients = 逗号分隔的收件人地址"""
    if not settings.smtp_host:
        raise RuntimeError("SMTP未配置，请在环境变量中设置 smtp_host 等参数")

    subject = "[ITOps] 告警通知"

    # 将 markdown content 转为纯文本（去除 ** 和 > 标记）
    plain = content.replace("**", "").replace("> ", "")

    msg = MIMEText(plain, "plain", "utf-8")
    msg["From"] = settings.smtp_from_email
    msg["To"] = recipients
    msg["Subject"] = subject

    addr_list = [a.strip() for a in recipients.split(",") if a.strip()]

    def _do_send():
        if settings.smtp_use_tls:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15)
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.smtp_from_email, addr_list, msg.as_string())
        server.quit()

    await asyncio.get_event_loop().run_in_executor(None, _do_send)


# ─── Generic fallback ────────────────────────────────────────

async def _send_generic(url: str, content: str):
    """通用 webhook（纯文本）"""
    payload = {"text": content}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()


# ─── Helpers ─────────────────────────────────────────────────

def _check_webhook_response(platform: str, resp: httpx.Response):
    """解析 webhook 响应中的错误码"""
    if resp.status_code >= 500:
        resp.raise_for_status()
    try:
        data = resp.json()
    except Exception:
        resp.raise_for_status()
        return

    errcode = data.get("errcode") or data.get("code") or data.get("StatusCode")
    if errcode is not None and errcode != 0:
        errmsg = data.get("errmsg") or data.get("msg") or "unknown"
        raise RuntimeError(f"{platform} 返回错误: errcode={errcode}, errmsg={errmsg}")
    if resp.status_code >= 400:
        resp.raise_for_status()
