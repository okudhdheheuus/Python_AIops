"""告警模块测试"""

import pytest


@pytest.mark.asyncio
async def test_webhook_receive(client):
    """接收 Prometheus webhook 告警"""
    payload = {
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "HighCPU",
                    "severity": "critical",
                    "instance": "192.168.1.10:9090",
                },
                "annotations": {
                    "summary": "CPU usage > 90%"
                }
            }
        ]
    }
    resp = await client.post("/api/alerts/webhook", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"


@pytest.mark.asyncio
async def test_empty_webhook(client):
    """空告警列表"""
    resp = await client.post("/api/alerts/webhook", json={"alerts": []})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ignored"


@pytest.mark.asyncio
async def test_list_alerts(client):
    """告警列表"""
    for i in range(3):
        await client.post("/api/alerts/webhook", json={
            "alerts": [{
                "status": "firing",
                "labels": {
                    "alertname": f"Alert-{i}",
                    "severity": "warning",
                    "instance": "10.0.0.1:9090",
                },
                "annotations": {"summary": f"Test alert {i}"}
            }]
        })

    resp = await client.get("/api/alerts")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 3
    assert "items" in data
    assert "page" in data
    assert "page_size" in data


@pytest.mark.asyncio
async def test_alert_stats(client):
    """告警统计"""
    for i in range(2):
        await client.post("/api/alerts/webhook", json={
            "alerts": [{
                "status": "firing",
                "labels": {
                    "alertname": f"StatsAlert-{i}",
                    "severity": "critical" if i == 0 else "warning",
                    "instance": f"10.0.0.{i}:9090",
                },
                "annotations": {"summary": "Stats test"}
            }]
        })

    resp = await client.get("/api/alerts/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    assert data["critical_firing"] >= 1
    assert data["warning_firing"] >= 1


@pytest.mark.asyncio
async def test_alert_dedup(client):
    """告警去重"""
    payload = {
        "alerts": [{
            "status": "firing",
            "labels": {
                "alertname": "DedupTest",
                "severity": "warning",
                "instance": "10.0.0.1:9090",
            },
            "annotations": {"summary": "Dedup check"}
        }]
    }
    resp1 = await client.post("/api/alerts/webhook", json=payload)
    assert resp1.status_code == 200

    resp2 = await client.post("/api/alerts/webhook", json=payload)
    assert resp2.status_code == 200
    results = resp2.json()["results"]
    assert results[0].get("duplicate") is True


@pytest.mark.asyncio
async def test_alert_lifecycle(client):
    """告警状态流转: firing -> acknowledged -> resolved"""
    webhook_resp = await client.post("/api/alerts/webhook", json={
        "alerts": [{
            "status": "firing",
            "labels": {"alertname": "LifecycleTest", "severity": "info", "instance": "10.0.0.1:9090"},
            "annotations": {"summary": "Lifecycle test"}
        }]
    })
    alert_id = webhook_resp.json()["results"][0]["alert_id"]

    # acknowledged
    ack_resp = await client.put(f"/api/alerts/{alert_id}", json={"status": "acknowledged"})
    assert ack_resp.status_code == 200

    # resolved
    res_resp = await client.put(f"/api/alerts/{alert_id}", json={"status": "resolved"})
    assert res_resp.status_code == 200


@pytest.mark.asyncio
async def test_alert_not_found(client):
    """更新不存在的告警"""
    resp = await client.put("/api/alerts/nonexistent-id", json={"status": "acknowledged"})
    assert resp.status_code == 404
