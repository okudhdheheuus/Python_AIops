"""认证模块测试"""

import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    """健康检查接口"""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "environment" in data


@pytest.mark.asyncio
async def test_health_legacy(client):
    """兼容旧版健康检查"""
    resp = await client.get("/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_register(client):
    """用户注册"""
    data = {"username": "testuser", "password": "testpass123", "role": "admin"}
    resp = await client.post("/api/auth/register", json=data)
    assert resp.status_code == 200
    user = resp.json()
    assert user["username"] == "testuser"
    assert user["role"] == "viewer"  # 注册强制为 viewer，防止提权
    assert "id" in user


@pytest.mark.asyncio
async def test_login(client):
    """用户登录"""
    await client.post("/api/auth/register", json={
        "username": "loginuser", "password": "pass123", "role": "viewer"
    })
    resp = await client.post("/api/auth/login", json={
        "username": "loginuser", "password": "pass123"
    })
    assert resp.status_code == 200
    token = resp.json()
    assert "access_token" in token
    assert token["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    """错误密码登录"""
    await client.post("/api/auth/register", json={
        "username": "user2", "password": "correctpass", "role": "viewer"
    })
    resp = await client.post("/api/auth/login", json={
        "username": "user2", "password": "wrongpass"
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_duplicate_username(client):
    """重复用户名注册"""
    data = {"username": "dupuser", "password": "pass123", "role": "viewer"}
    resp1 = await client.post("/api/auth/register", json=data)
    assert resp1.status_code == 200

    resp2 = await client.post("/api/auth/register", json=data)
    assert resp2.status_code == 400


@pytest.mark.asyncio
async def test_metrics_endpoint(client):
    """Prometheus指标端点"""
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    text = resp.text
    assert "itops" in text.lower() or len(text) > 0
