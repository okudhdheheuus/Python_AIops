import logging

from fastapi import (  # 引入APIRouter,Depends,HTTPException
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import User
from ..schemas import LoginRequest, Token, UserCreate, UserOut
from ..utils.security import create_access_token, hash_password, verify_password

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# 创建路由实例，用于main.py导入
router = APIRouter()
@router.post("/register",response_model=UserOut)
async def register(user_data: UserCreate,db: AsyncSession = Depends(get_db)):
    # 检查用户名是否存在
    stmt = select(User).where(User.username == user_data.username)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400,detail="Username already exists")
    new_user = User(
        username = user_data.username,
        email = user_data.email,
        hashed_password= hash_password(user_data.password),
        role = user_data.role
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    # 使用UserOut模型验证并返回新创建的用户对象
    # model_validate是Pydantic v2中的方法，用于验证数据是否符合模型定义
    return UserOut.model_validate(new_user)

@router.post("/login",response_model=Token)
async def login(login_data:LoginRequest,db: AsyncSession = Depends(get_db)):
    try:
        logger.debug(f"Login attempt for username: {login_data.username}")
        stmt = select(User).where(User.username == login_data.username)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            logger.warning(f"User not found: {login_data.username}")
            raise HTTPException(status_code=401,detail="User not found")
        if not verify_password(login_data.password,user.hashed_password):
            logger.warning(f"Invalid password for user: {login_data.username}")
            raise HTTPException(status_code=401,detail="Invalid password")
        if not user.is_active:
            logger.warning(f"Inactive user: {login_data.username}")
            raise HTTPException(status_code=403,detail="Inactive user")
        access_token = create_access_token(data={"sub" : user.username,"role":user.role})
        logger.info(f"Login successful for user: {login_data.username}")
        return Token(access_token=access_token)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Login error")
        raise HTTPException(status_code=500,detail=f"Internal server error: {e!s}")

