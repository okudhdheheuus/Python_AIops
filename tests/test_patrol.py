"""巡检与仪表盘模块测试"""

import pytest


@pytest.mark.asyncio
async def test_patrol_records_empty(client, auth_headers):
    """空巡检记录"""
    resp = await client.get("/api/patrol/records", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_patrol_summary_empty(client, auth_headers):
    """空巡检摘要"""
    resp = await client.get("/api/patrol/summary", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_dashboard_stats(client, auth_headers):
    """仪表盘统计"""
    # 创建一些数据
    await client.post("/api/servers", json={
        "name": "dash-srv", "host": "10.0.0.10", "port": 22, "username": "root"
    }, headers=auth_headers)

    resp = await client.get("/api/dashboard/stats", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["servers"] >= 1
    assert "agents" in data
    assert "workflows" in data


@pytest.mark.asyncio
async def test_alert_silence_rule_crud(client, auth_headers):
    """告警静默规则CRUD"""
    # 创建
    create_resp = await client.post("/api/alerts/silence", json={
        "name": "test-silence",
        "match_labels": {"alertname": "TestAlert"},
        "duration_minutes": 60,
    }, headers=auth_headers)
    assert create_resp.status_code == 200

    # 列表
    list_resp = await client.get("/api/alerts/silence", headers=auth_headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1

    # 删除
    rule_id = create_resp.json()["id"]
    del_resp = await client.delete(f"/api/alerts/silence/{rule_id}", headers=auth_headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "deleted"


@pytest.mark.asyncio
async def test_remediation_policies(client):
    """修复策略CRUD"""
    # 创建
    create_resp = await client.post("/api/remediation/policies", json={
        "name": "test-policy",
        "match_labels": {"severity": "critical"},
        "command": "systemctl restart nginx",
        "timeout_seconds": 30,
    })
    assert create_resp.status_code == 201

    # 列表
    list_resp = await client.get("/api/remediation/policies")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_remediation_logs(client):
    """修复日志查询"""
    resp = await client.get("/api/remediation/logs")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "items" in data
