"""AI 聊天API —— SSE 流式响应 + 会话管理"""
import uuid
import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import User
from ..utils.security import get_current_active_user
from ..services.llm import get_llm_provider
from ..services.chat_service import get_session,save_session,delete_session,list_user_sessions
from ..core.logging import request_id_var

router = APIRouter()
logger = logging.getLogger("itops")


@router.get("/sessions")
async def list_sessions(
    current_user: User = Depends(get_current_active_user),
):
    """获取当前用户的会话列表"""
    sessions = await list_user_sessions(current_user.username)
    return {"sessions": sessions}


@router.get("/session/{session_id}")
async def get_chat_session(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """获取指定会话的历史记录"""
    messages = await get_session(session_id)
    return {"session_id": session_id, "messages": messages}


@router.delete("/session/{session_id}")
async def delete_chat_session(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """删除指定会话"""
    await delete_session(session_id)
    return {"message": "Session deleted successfully"}

@router.post("/send")
async def send_message(
    body: dict,
    current_user: User = Depends(get_current_active_user),
):
    user_message = body.get("message", "").strip()
    if not user_message:
        raise HTTPException(status_code=422, detail="消息不能为空")
    session_id = body.get("session_id", str(uuid.uuid4()))
    # 获取历史消息
    history = await get_session(session_id) if body.get("session_id") else []
    history.append({"role": "user", "content": user_message})
    # 选择provider
    provider = get_llm_provider()
    async def event_stream():
        full_response = ""
        try:
            async for token in provider.chat_stream(history):
                full_response += token
                yield f"data: {json.dumps({'type':'token','content':token},ensure_ascii=False)}\n\n"

            history.append({"role": "assistant", "content": full_response})
            await save_session(session_id, history)
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception("chat streaming error")
            yield f"data: {json.dumps({'type':'done','session_id':session_id},ensure_ascii=False)}\n\n"
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
            "X-Request-ID": request_id_var.get(),
        },
    )