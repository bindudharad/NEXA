from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "nexa"


def test_memory_command_requires_approval_before_execution():
    response = client.post("/api/commands", json={"command": "remember this preference"})
    assert response.status_code == 200
    approval = response.json()
    assert approval["status"] == "pending"
    assert approval["corrected_text"] == "Remember this preference"
    approved = client.post(f"/api/task-approvals/{approval['id']}/approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["task"]["status"] == "completed"


def test_dangerous_delete_endpoint_requires_confirmation():
    response = client.post("/api/files/delete", json={"path": "missing.txt"})
    assert response.status_code == 409


def test_memory_persistence_endpoint():
    response = client.post("/api/memory", json={"key": "editor", "value": "VS Code"})
    assert response.status_code == 200
    rows = client.get("/api/memory").json()
    assert any(row["key"] == "editor" for row in rows)
