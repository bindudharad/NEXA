from fastapi.testclient import TestClient

from backend.database.models import AIInterpretation, ApprovalHistory, CorrectionHistory, TaskApproval
from backend.database.session import SessionLocal
from backend.main import app


client = TestClient(app)


def test_task_approval_corrects_and_extracts_reminder():
    response = client.post("/api/commands", json={"command": "remid me submit assigment tomorow 9"})
    assert response.status_code == 200
    approval = response.json()
    assert approval["status"] == "pending"
    assert approval["task_type"] == "Reminder"
    assert approval["confidence"] >= 80
    assert approval["corrected_text"] == "Remind me to submit my assignment tomorrow at 9:00 AM."
    assert approval["structured_task"]["date"] == "tomorrow"
    assert approval["structured_task"]["time"] == "9:00 AM"


def test_high_risk_command_requires_approval_and_then_executes():
    approval_response = client.post("/api/commands", json={"command": "shutdown after 5 minutes"})
    assert approval_response.status_code == 200
    approval = approval_response.json()
    assert approval["high_risk"] is True
    assert approval["status"] == "pending"
    tasks_before = client.get("/api/tasks").json()
    approved = client.post(f"/api/task-approvals/{approval['id']}/approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["task"]["agent"] == "scheduler"
    tasks_after = client.get("/api/tasks").json()
    assert len(tasks_after) >= len(tasks_before)


def test_low_confidence_requires_edit_before_approval():
    response = client.post("/api/commands", json={"command": "remember unclear thing tomorrow"})
    assert response.status_code == 200
    approval = response.json()
    assert approval["clarification_required"] is True
    blocked = client.post(f"/api/task-approvals/{approval['id']}/approve")
    assert blocked.status_code == 409
    edited = client.put(
        f"/api/task-approvals/{approval['id']}/edit",
        json={"task_title": "Remind me to review unclear thing", "date": "tomorrow", "time": "9:00 AM"},
    )
    assert edited.status_code == 200
    assert edited.json()["status"] == "pending"
    approved = client.post(f"/api/task-approvals/{approval['id']}/approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"


def test_reject_stores_history_and_prevents_execution():
    response = client.post("/api/commands", json={"command": "open Chrome"})
    approval_id = response.json()["id"]
    rejected = client.post(f"/api/task-approvals/{approval_id}/reject", json={"reason": "not now"})
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    blocked = client.post(f"/api/task-approvals/{approval_id}/approve")
    assert blocked.status_code == 404


def test_approval_database_history_is_stored():
    response = client.post("/api/commands", json={"command": "open chrom and search pythn tutorials"})
    approval_id = response.json()["id"]
    with SessionLocal() as db:
        assert db.get(TaskApproval, approval_id) is not None
        assert db.query(AIInterpretation).filter(AIInterpretation.approval_id == approval_id).count() >= 1
        assert db.query(ApprovalHistory).filter(ApprovalHistory.approval_id == approval_id).count() >= 1
        assert db.query(CorrectionHistory).filter(CorrectionHistory.original_text.like("%chrom%")).count() >= 1
