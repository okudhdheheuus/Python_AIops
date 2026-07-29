
import json

from ..core.redis import get_redis

SESSION_TTL = 3600
MAX_HISTORY = 50
async def get_session(session_id: str) -> list[dict]:
    """从Redis获取会话历史"""
    r = await get_redis()
    data = await r.get(f"chat:session:{session_id}")
    if data:
        return json.loads(data)
    return []

async def save_session(session_id:str,messages:list[dict]):
    """将会话历史保存到Redis"""
    r = await get_redis()
    # 限制历史长度，防止无限增长
    if len(messages) > MAX_HISTORY:
        messages = messages[-MAX_HISTORY:]
    await r.setex(
        f"chat:session:{session_id}",
        SESSION_TTL,
        json.dumps(messages,ensure_ascii=False),
    )
async def delete_session(session_id:str):
    """删除会话"""
    r = await get_redis()
    await r.delete(f"chat:session:{session_id}")
async def list_user_sessions(username: str)->list[dict]:
    """列出用户的所有会话（不含具体消息内容，只列元数据）"""
    r = await get_redis()
    # 使用Redis的SCAN查找该用户的所有会话
    sessions = []
    cursor = 0
    pattern = "chat:session:*"
    while True:
        cursor,keys = await r.scan(cursor,match=pattern,count=100)
        for key in keys:
            data = await r.get(key)
            if data:
                messages = json.loads(data)
                # 查找用户的第一条消息
                first_user_msg = next(
                    (m for m in messages if m.get("role") == "user"),None
                )
                session_id = key.replace("chat:session:","")
                sessions.append({
                    "session_id":session_id,
                    "title":(first_user_msg.get("content","")[:50]+"...") if first_user_msg else "新回话",
                    "message_count":len(messages),
                })
        if cursor == 0:
            break
    return sessions




