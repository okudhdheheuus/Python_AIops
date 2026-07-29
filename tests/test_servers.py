"""服务器管理模块测试"""

import pytest


@pytest.mark.asyncio
async def test_create_server(client, auth_headers):
    """创建服务器"""
    server_data = {
        "name": "test-server",
        "host": "192.168.1.100",
        "port": 22,
        "username": "root",
        "tags": "test,dev",
    }
    resp = await client.post("/api/servers", json=server_data, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test-server"
    assert data["host"] == "192.168.1.100"
    assert data["enabled"] is True


@pytest.mark.asyncio
async def test_list_servers(client, auth_headers):
    """列出服务器"""
    for i in range(3):
        await client.post("/api/servers", json={
            "name": f"srv-{i}", "host": f"10.0.0.{i}", "port": 22, "username": "root"
        }, headers=auth_headers)

    resp = await client.get("/api/servers", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3


@pytest.mark.asyncio
async def test_get_server(client, auth_headers):
    """获取单个服务器"""
    create_resp = await client.post("/api/servers", json={
        "name": "single-srv", "host": "10.0.0.99", "port": 22, "username": "root"
    }, headers=auth_headers)
    server_id = create_resp.json()["id"]

    resp = await client.get(f"/api/servers/{server_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "single-srv"


@pytest.mark.asyncio
async def test_update_server(client, auth_headers):
    """更新服务器"""
    create_resp = await client.post("/api/servers", json={
        "name": "update-srv", "host": "10.0.0.88", "port": 22, "username": "root"
    }, headers=auth_headers)
    server_id = create_resp.json()["id"]

    resp = await client.put(f"/api/servers/{server_id}", json={
        "name": "updated-name", "tags": "prod,critical"
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "updated-name"
    assert data["tags"] == "prod,critical"


@pytest.mark.asyncio
async def test_delete_server(client, auth_headers):
    """删除服务器"""
    create_resp = await client.post("/api/servers", json={
        "name": "delete-srv", "host": "10.0.0.77", "port": 22, "username": "root"
    }, headers=auth_headers)
    server_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/servers/{server_id}", headers=auth_headers)
    assert resp.status_code == 204

    get_resp = await client.get(f"/api/servers/{server_id}", headers=auth_headers)
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_create_server_forbidden(client):
    """非admin创建服务器应返回403"""
    await client.post("/api/auth/register", json={
        "username": "viewer", "password": "pass123", "role": "viewer"
    })
    login_resp = await client.post("/api/auth/login", json={
        "username": "viewer", "password": "pass123"
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post("/api/servers", json={
        "name": "srv", "host": "10.0.0.1", "port": 22, "username": "root"
    }, headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_tag_filter(client, auth_headers):
    """标签筛选"""
    await client.post("/api/servers", json={
        "name": "web-01", "host": "10.0.0.1", "tags": "web,prod", "port": 22, "username": "root"
    }, headers=auth_headers)
    await client.post("/api/servers", json={
        "name": "db-01", "host": "10.0.0.2", "tags": "db,prod", "port": 22, "username": "root"
    }, headers=auth_headers)

    resp = await client.get("/api/servers?tag=web", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "web-01"


@pytest.mark.asyncio
async def test_export_csv(client, auth_headers):
    """导出CSV"""
    await client.post("/api/servers", json={
        "name": "export-srv", "host": "10.0.0.3", "tags": "test"
    }, headers=auth_headers)

    resp = await client.get("/api/servers/export-csv", headers=auth_headers)
    assert resp.status_code == 200
    assert "name,host" in resp.text
