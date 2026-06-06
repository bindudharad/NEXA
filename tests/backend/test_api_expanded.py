from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_dashboard_and_tasks_endpoints():
    dashboard = client.get("/api/dashboard")
    assert dashboard.status_code == 200
    system = dashboard.json()["system"]
    assert "disk_percent" in system
    assert "health_score" in system
    assert "context" in system
    assert client.get("/api/tasks").status_code == 200


def test_coding_endpoints():
    assert client.get("/api/coding/report").status_code == 200
    assert client.get("/api/coding/weekly-report").status_code == 200
    assert client.post("/api/coding/snapshot").status_code == 200


def test_automation_metric_endpoint():
    created = client.post(
        "/api/automations",
        json={
            "name": "CPU test",
            "condition": {"metric": "cpu", "operator": ">", "value": -1},
            "action": {"type": "notify", "message": "CPU above -1"},
        },
    )
    assert created.status_code == 200
    fired = client.post("/api/automations/evaluate")
    assert fired.status_code == 200
    assert isinstance(fired.json(), list)
    toggled = client.put(f"/api/automations/{created.json()['id']}/toggle", json={"enabled": False})
    assert toggled.status_code == 200
    assert toggled.json()["enabled"] is False


def test_task_cancel_and_retry_endpoints():
    approval = client.post("/api/commands", json={"command": "delete file C:/definitely-not-real.txt"})
    assert approval.status_code == 200
    created = client.post(f"/api/task-approvals/{approval.json()['id']}/approve")
    assert created.status_code == 200
    task_id = created.json()["task"]["id"]
    cancelled = client.post(f"/api/tasks/{task_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] in {"cancelled", "failed", "completed"}
    retried = client.post(f"/api/tasks/{task_id}/retry")
    assert retried.status_code == 200
    pause_approval = client.post("/api/commands", json={"command": "Shutdown after 5 minutes"})
    assert pause_approval.status_code == 200
    pause_candidate = client.post(f"/api/task-approvals/{pause_approval.json()['id']}/approve")
    assert pause_candidate.status_code == 200
    paused = client.post(f"/api/tasks/{pause_candidate.json()['task']['id']}/pause")
    assert paused.status_code == 200
    resumed = client.post(f"/api/tasks/{pause_candidate.json()['task']['id']}/resume")
    assert resumed.status_code == 200


def test_event_endpoint():
    created = client.post(
        "/api/automations",
        json={
            "name": "Codex done",
            "condition": {"event_type": "codex_queue_finished"},
            "action": {"type": "notify", "message": "Codex finished"},
        },
    )
    assert created.status_code == 200
    fired = client.post("/api/events", json={"event_type": "codex_queue_finished", "payload": {}})
    assert fired.status_code == 200
    assert any(item["message"] == "Codex finished" for item in fired.json())


def test_file_search_validation():
    response = client.post("/api/files/search", json={"path": ".", "query": ""})
    assert response.status_code == 422


def test_notification_endpoint():
    response = client.post("/api/notifications", json={"title": "Test", "message": "Done"})
    assert response.status_code == 200


def test_battery_alert_endpoints():
    settings = client.get("/api/battery-alert/settings")
    assert settings.status_code == 200
    updated = client.put("/api/battery-alert/settings", json={"threshold_percent": 20, "repeat_interval_seconds": 120})
    assert updated.status_code == 200
    simulated = client.post("/api/battery-alert/test/simulate", json={"battery_percent": 20, "is_charging": True})
    assert simulated.status_code == 200
    status = client.get("/api/battery-alert/status")
    assert status.status_code == 200
    cleared = client.post("/api/battery-alert/test/clear")
    assert cleared.status_code == 200


def test_gpu_monitor_endpoints():
    settings = client.get("/api/gpu-monitor/settings")
    assert settings.status_code == 200
    updated = client.put("/api/gpu-monitor/settings", json={"threshold_celsius": 50, "repeat_interval_seconds": 300})
    assert updated.status_code == 200
    simulated = client.post("/api/gpu-monitor/test/simulate", json={"temperature_celsius": 55})
    assert simulated.status_code == 200
    assert simulated.json()["alert_active"] is True
    status = client.get("/api/gpu-monitor/status")
    assert status.status_code == 200
    cleared = client.post("/api/gpu-monitor/test/clear")
    assert cleared.status_code == 200
