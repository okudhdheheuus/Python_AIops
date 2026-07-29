from fastapi.security import HTTPBearer
from fastapi.params import Depends
from fastapi.security import HTTPAuthorizationCredentials
# 导入所需的库和模块
import bcrypt  # 直接使用 bcrypt，替代已停更的 passlib
from jose import jwt, JWTError  # 用于处理JWT (JSON Web Tokens) 的库
from datetime import datetime,timedelta  # 用于处理日期和时间
import hashlib
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings  # 导入配置模块中的设置
from ..database import get_db
from ..models import User
from fastapi import HTTPException,status
from sqlalchemy import select
def hash_password(password: str) -> str:
    # 先用 SHA-256 哈希，再传给 bcrypt（绕过 72 字节限制）
    prehashed = hashlib.sha256(password.encode('utf-8')).hexdigest()
    return bcrypt.hashpw(prehashed.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain: str, hashed: str) -> bool:
    prehashed = hashlib.sha256(plain.encode('utf-8')).hexdigest()
    return bcrypt.checkpw(prehashed.encode('utf-8'), hashed.encode('utf-8'))

def create_access_token(data: dict,expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expires_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode,settings.secret_key,algorithm=settings.algorithms)

security = HTTPBearer()
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    token  = credentials.credentials
    try:
        payload = jwt.decode(token,settings.secret_key,algorithms=[settings.algorithms])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401,detail="Invalide token")
    except JWTError:
        raise HTTPException(status_code=401,detail="Invalid token")

    stmt = select(User).where(User.username == username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401,detail="User not found")
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user))->User:
    if not current_user.is_active:
        raise HTTPException(status_code=403,detail="Inactive user")
    return current_user