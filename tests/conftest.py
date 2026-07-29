"""测试配置和共享 fixture"""

import os
import tempfile
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

from backend.main import app
from backend.database import Base, get_db

TEST_DB = os.getenv("TEST_DATABASE_URL", f"sqlite+aiosqlite:///{tempfile.gettempdir()}/itops_test.db")


@pytest_asyncio.fixture(loop_scope="session")
async def engine():
    eng = create_async_engine(TEST_DB, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def test_session(engine):
    async with engine.connect() as conn:
        txn = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        yield session
        await session.close()
        await txn.rollback()


@pytest_asyncio.fixture
async def client(test_session):
    app.dependency_overrides[get_db] = lambda: test_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_headers(client):
    await client.post("/api/auth/register", json={
        "username": "testadmin",
        "password": "admin123",
        "role": "admin",
    })
    login_resp = await client.post("/api/auth/login", json={
        "username": "testadmin",
        "password": "admin123",
    })
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
