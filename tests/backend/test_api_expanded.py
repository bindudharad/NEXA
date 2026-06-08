from fastapi.testclient import TestClient
from pathlib import Path

from backend.database.models import FocusSession
from backend.database.session import SessionLocal
from backend.main import app


client = TestClient(app)


def clear_active_focus_sessions():
    with SessionLocal() as db:
        for row in db.query(FocusSession).filter(FocusSession.status.in_(["active", "paused"])).all():
            row.status = "completed"
        db.commit()


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


def test_focus_mode_api_lifecycle():
    clear_active_focus_sessions()
    start = client.post(
        "/api/evolution/focus/start",
        json={
            "title": "API Study Focus",
            "session_type": "study",
            "duration_minutes": 30,
            "break_minutes": 5,
            "subject": "DBMS",
            "chapter": "Transactions",
            "topic": "Locks",
            "current_goal": "Complete one chapter",
            "blocked_websites": ["youtube.com", "reddit.com"],
            "blocked_apps": ["game.exe"],
        },
    )
    assert start.status_code == 200
    session_id = start.json()["id"]

    status = client.get("/api/evolution/focus/status")
    assert status.status_code == 200
    assert status.json()["active"] is True
    assert status.json()["detail"]["session_type"] == "study"

    blocked = client.post("/api/evolution/focus/distraction-check", json={"url": "https://www.youtube.com/watch?v=test"})
    assert blocked.status_code == 200
    assert blocked.json()["blocked"] is True
    assert blocked.json()["title"] == "Focus Mode Active"

    pause = client.post("/api/evolution/focus/pause", json={"session_id": session_id, "reason": "test"})
    assert pause.status_code == 200
    assert pause.json()["status"] == "paused"

    resume = client.post("/api/evolution/focus/resume", json={"session_id": session_id})
    assert resume.status_code == 200
    assert resume.json()["status"] == "active"

    extended = client.post("/api/evolution/focus/extend", json={"session_id": session_id, "minutes": 10, "reason": "test"})
    assert extended.status_code == 200
    assert extended.json()["detail"]["planned_minutes"] == 40
    assert extended.json()["detail"]["pomodoro"]["focus_minutes"] == 40

    break_state = client.post("/api/evolution/focus/break", json={"session_id": session_id, "minutes": 5})
    assert break_state.status_code == 200
    assert break_state.json()["detail"]["pomodoro"]["state"] == "break"

    goal = client.post(
        "/api/evolution/focus/goals",
        json={"title": "Study 30 minutes", "goal_type": "study", "target_minutes": 30, "session_id": session_id},
    )
    assert goal.status_code == 200
    updated_goal = client.put(f"/api/evolution/focus/goals/{goal.json()['id']}", json={"completed_minutes": 30})
    assert updated_goal.status_code == 200
    assert updated_goal.json()["status"] == "completed"

    ended = client.post(
        "/api/evolution/focus/end",
        json={"session_id": session_id, "tasks_completed": 1, "distraction_count": 1, "goal_completion_percent": 100},
    )
    assert ended.status_code == 200
    assert ended.json()["status"] == "completed"
    assert ended.json()["productivity_score"] > 0

    dashboard = client.get("/api/evolution/focus/dashboard")
    assert dashboard.status_code == 200
    assert any(item["id"] == session_id for item in dashboard.json()["recent_sessions"])


def test_study_assistant_api_lifecycle():
    subject = client.post(
        "/api/evolution/study/subjects",
        json={"name": "DBMS API", "priority": "high", "difficulty": "hard", "exam_date": "2099-02-01", "target_score": 95},
    )
    assert subject.status_code == 200
    subject_id = subject.json()["id"]

    chapter = client.post(
        "/api/evolution/study/chapters",
        json={"subject_id": subject_id, "title": "Transactions", "unit": "Unit 3", "topics": ["Locks", "Recovery"]},
    )
    assert chapter.status_code == 200
    chapter_id = chapter.json()["id"]

    plan = client.post(
        "/api/evolution/study/plans",
        json={"title": "DBMS API Exam Plan", "subject_name": "DBMS API", "exam_date": "2099-02-01", "topics": ["ER Model", "Transactions"], "availability_minutes_per_day": 90},
    )
    assert plan.status_code == 200
    assert plan.json()["daily_plan"]

    progress = client.put(f"/api/evolution/study/chapters/{chapter_id}/progress", json={"completion_percent": 100, "status": "completed"})
    assert progress.status_code == 200
    assert progress.json()["status"] == "completed"

    session = client.post(
        "/api/evolution/study/sessions",
        json={"subject_id": subject_id, "chapter_id": chapter_id, "topic": "Locks", "duration_minutes": 30, "session_type": "revision"},
    )
    assert session.status_code == 200
    assert session.json()["duration_seconds"] == 1800

    goal = client.post("/api/evolution/study/goals", json={"title": "Study DBMS API", "target_value": 2, "unit": "hours", "subject_id": subject_id})
    assert goal.status_code == 200
    goal_update = client.put(f"/api/evolution/study/goals/{goal.json()['id']}", json={"current_value": 2})
    assert goal_update.status_code == 200
    assert goal_update.json()["status"] == "completed"

    dashboard = client.get("/api/evolution/study/dashboard")
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert body["offline_ready"] is True
    assert any(item["name"] == "DBMS API" for item in body["subjects"])
    assert body["recommendations"]


def test_ai_memory_timeline_api():
    event = client.post(
        "/api/evolution/timeline",
        json={"event_type": "coding", "title": "Completed API timeline test", "description": "Timeline endpoint coverage", "source": "test", "duration_seconds": 3600, "metadata": {"important": True}},
    )
    assert event.status_code == 200
    assert event.json()["metadata"]["importance"] >= 80

    listed = client.get("/api/evolution/timeline", params={"q": "timeline test"})
    assert listed.status_code == 200
    assert any(item["id"] == event.json()["id"] for item in listed.json())

    natural = client.post("/api/evolution/timeline/search", json={"query": "show last week's coding", "limit": 50})
    assert natural.status_code == 200
    assert "summary" in natural.json()

    summary = client.get("/api/evolution/timeline/summary", params={"period": "week"})
    assert summary.status_code == 200
    assert summary.json()["stats"]["total_events"] >= 1

    dashboard = client.get("/api/evolution/timeline/dashboard", params={"view": "today"})
    assert dashboard.status_code == 200
    assert dashboard.json()["offline_ready"] is True
    assert "insights" in dashboard.json()


def test_project_guardian_api_lifecycle(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "app.py").write_text("print('safe')", encoding="utf-8")
    (project / ".env").write_text("SECRET=hidden", encoding="utf-8")

    snapshot = client.post("/api/evolution/project-guardian/snapshot", json={"project_path": str(project), "action": "api_snapshot"})
    assert snapshot.status_code == 200
    body = snapshot.json()
    assert Path(body["backup_path"]).exists()
    assert not (Path(body["backup_path"]) / ".env").exists()

    protected = client.post("/api/evolution/project-guardian/protect", json={"project_path": str(project), "operation": "delete", "reason": "test"})
    assert protected.status_code == 200
    assert protected.json()["approval"]["requires_approval"] is True

    git_status = client.get("/api/evolution/project-guardian/git-status", params={"project_path": str(project)})
    assert git_status.status_code == 200
    assert git_status.json()["is_git_repo"] is False

    dashboard = client.get("/api/evolution/project-guardian/dashboard", params={"project_path": str(project)})
    assert dashboard.status_code == 200
    assert dashboard.json()["offline_ready"] is True
    project_id = dashboard.json()["projects"][0]["id"]

    health = client.post(f"/api/evolution/project-guardian/projects/{project_id}/health")
    assert health.status_code == 200
    assert "recommendations" in health.json()


def test_smart_download_manager_api(tmp_path: Path):
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    (downloads / "notes.pdf").write_bytes(b"pdf")
    (downloads / "notes-copy.pdf").write_bytes(b"pdf")
    (downloads / "movie.mp4").write_bytes(b"x" * (2 * 1024 * 1024))

    scan = client.post("/api/evolution/downloads/scan", json={"folder": str(downloads), "large_file_mb": 1})
    assert scan.status_code == 200
    assert scan.json()["count"] == 3

    dashboard = client.get("/api/evolution/downloads/dashboard", params={"folder": str(downloads)})
    assert dashboard.status_code == 200
    assert dashboard.json()["offline_ready"] is True

    search = client.post("/api/evolution/downloads/search", json={"query": "find PDFs", "limit": 10})
    assert search.status_code == 200
    assert search.json()["results"]

    duplicates = client.get("/api/evolution/downloads/duplicates")
    assert duplicates.status_code == 200
    assert len(duplicates.json()) >= 1

    rule = client.post("/api/evolution/downloads/rules", json={"name": "PDF Rule", "pattern": ".pdf", "category": "PDF"})
    assert rule.status_code == 200
    assert rule.json()["category"] == "PDF"


def test_screenshot_assistant_api(tmp_path: Path):
    screenshot = tmp_path / "screen.png"
    screenshot.write_bytes(b"png")
    text = "npm ERR! build failed\nReact TypeError in App.tsx line 12"

    created = client.post("/api/evolution/screenshots", json={"file_path": str(screenshot), "source": "api_test", "extracted_text": text})
    assert created.status_code == 200
    body = created.json()
    assert "error" in body["tags"]
    assert body["error_analysis"] is not None

    dashboard = client.get("/api/evolution/screenshots/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["offline_ready"] is True

    search = client.post("/api/evolution/screenshots/search", json={"query": "find coding errors", "limit": 10})
    assert search.status_code == 200
    assert search.json()["results"]

    action = client.post(f"/api/evolution/screenshots/{body['id']}/actions", json={"action_type": "save_notes", "payload": {"source": "api"}})
    assert action.status_code == 200
    assert action.json()["action_type"] == "save_notes"

    settings = client.put("/api/evolution/screenshots/settings", json={"cloud_ai_enabled": False, "require_cloud_approval": True})
    assert settings.status_code == 200
    assert settings.json()["require_cloud_approval"] is True
