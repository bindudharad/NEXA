import json
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.database.models import WebsiteCredential, WebsiteHistory, WebsiteLearning, WebsiteMonitoring, WebsiteProfile, WebsiteRetryRule, WebsiteSession
from backend.database.session import SessionLocal
from backend.main import app


client = TestClient(app)


HTML = """
<html>
  <body>
    <form id="login">
      <input id="usn" name="usn" placeholder="USN" required />
      <input id="dob" name="dob" placeholder="Date of Birth" />
      <input id="password" name="password" type="password" />
      <select id="semester" name="semester"><option>1</option></select>
      <button id="loginBtn">Login</button>
    </form>
    <div class="g-recaptcha"></div>
    <a href="/dashboard">Dashboard</a>
  </body>
</html>
"""


def test_website_analysis_detects_login_fields_and_captcha():
    response = client.post("/api/website-profiles/analyze", json={"name": "Contineo", "url": "https://contineo.test", "html": HTML})
    assert response.status_code == 200
    data = response.json()
    assert data["captcha_present"] is True
    assert data["field_mapping"]["usn"] == "#usn"
    assert data["field_mapping"]["date_of_birth"] == "#dob"
    assert data["field_mapping"]["password"] == "#password"
    assert data["dropdowns"][0]["selector"] == "#semester"
    assert data["login_forms"][0]["submit_selector"] == "#loginBtn"


def test_profile_creation_encrypts_credentials():
    created = client.post(
        "/api/website-profiles",
        json={
            "name": "KCET",
            "url": "https://kcet.test",
            "field_mapping": {"application_number": "#app", "date_of_birth": "#dob"},
            "login_process": {"submit_selector": "#submit"},
            "credentials": {"application_number": "ABC123", "date_of_birth": "2000-01-01"},
            "retry_policy": {"max_retries": 5, "retry_interval_seconds": 1},
        },
    )
    assert created.status_code == 200
    profile_id = created.json()["id"]
    assert created.json()["retry_policy"]["max_retries"] == 5
    with SessionLocal() as db:
        row = db.query(WebsiteCredential).filter(WebsiteCredential.profile_id == profile_id).one()
        assert "ABC123" not in row.encrypted_payload
        assert "2000-01-01" not in row.encrypted_payload
        assert db.query(WebsiteRetryRule).filter(WebsiteRetryRule.profile_id == profile_id).one().max_retries == 5
        assert db.query(WebsiteLearning).filter(WebsiteLearning.profile_id == profile_id).count() >= 1


def test_missing_profile_returns_learning_prompt():
    response = client.post("/api/websites/open", json={"name": "New College Portal"})
    assert response.status_code == 200
    assert response.json()["requires_profile"] is True
    assert "website URL" in response.json()["message"]


def test_browser_endpoints_require_approval_header():
    response = client.post("/api/browser/search", json={"key": "query", "value": "python tutorials"})
    assert response.status_code == 409


def test_chat_command_routes_website_profile_after_approval():
    approval = client.post("/api/commands", json={"command": "Open Contineo"})
    assert approval.status_code == 200
    data = approval.json()
    assert data["plan"]["agent"] == "website"
    assert data["status"] == "pending"
    approved = client.post(f"/api/task-approvals/{data['id']}/approve")
    assert approved.status_code == 200
    assert approved.json()["task"]["result"]["requires_profile"] is True


def test_monitoring_toggle_and_check_records_history():
    created = client.post("/api/website-profiles", json={"name": f"Monitor Test {uuid4().hex}", "url": "data:text/html,<html><body><input name='email'></body></html>"})
    profile_id = created.json()["id"]
    toggled = client.put(f"/api/website-profiles/{profile_id}/monitoring", json={"enabled": True, "interval_seconds": 300})
    assert toggled.status_code == 200
    checked = client.post("/api/website-profiles/monitor/check")
    assert checked.status_code == 200
    with SessionLocal() as db:
        history = db.query(WebsiteHistory).filter(WebsiteHistory.profile_id == profile_id).all()
        assert any(item.event_type == "monitor_check" for item in history)
        profile = db.get(WebsiteProfile, profile_id)
        assert profile is not None
        assert isinstance(json.loads(profile.field_mapping_json), dict)
        assert db.query(WebsiteMonitoring).filter(WebsiteMonitoring.profile_id == profile_id).one().enabled is False


def test_profile_export_import_history_and_delete():
    created = client.post(
        "/api/website-profiles",
        json={"name": "Exportable Portal", "url": "data:text/html,<html><body><input name='email'></body></html>", "field_mapping": {"email": "[name='email']"}},
    )
    profile_id = created.json()["id"]
    history = client.get(f"/api/website-profiles/{profile_id}/history")
    assert history.status_code == 200
    exported = client.get(f"/api/website-profiles/{profile_id}/export")
    assert exported.status_code == 200
    payload = exported.json()
    payload["profile"]["name"] = "Imported Portal"
    imported = client.post("/api/website-profiles/import", json={"payload": payload})
    assert imported.status_code == 200
    assert imported.json()["name"] == "Imported Portal"
    deleted = client.delete(f"/api/website-profiles/{profile_id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True


def test_kcet_result_flow_requests_input_and_can_save_profile():
    with SessionLocal() as db:
        existing = db.query(WebsiteProfile).filter(WebsiteProfile.name == "KCET").all()
        for profile in existing:
            db.query(WebsiteCredential).filter(WebsiteCredential.profile_id == profile.id).delete()
            db.query(WebsiteSession).filter(WebsiteSession.profile_id == profile.id).delete()
            db.delete(profile)
        db.commit()
    required = client.post("/api/websites/kcet-result", json={})
    assert required.status_code == 200
    assert required.json()["requires_input"] is True
    saved = client.post(
        "/api/websites/kcet-result",
        json={"application_number": "KC123", "date_of_birth": "2000-01-01", "save_profile": True, "url": "data:text/html,<html><body>result<input name='application_number'><input name='dob'><button type='submit'>Login</button></body></html>"},
    )
    assert saved.status_code == 200
    assert saved.json()["status"] in {"available", "failed", "session_restored"}


def test_session_restore_uses_encrypted_cookies():
    created = client.post("/api/website-profiles", json={"name": "Session Portal", "url": "https://session.test"})
    profile_id = created.json()["id"]
    with SessionLocal() as db:
        from backend.services.secure_store import SecureStore

        encrypted = SecureStore().encrypt(json.dumps([{"name": "sid", "value": "secret", "domain": "session.test", "path": "/"}]))
        db.add(WebsiteSession(profile_id=profile_id, status="success", encrypted_cookies=encrypted, retry_count=1))
        db.commit()
    opened = client.post("/api/websites/open", json={"name": "Session Portal"})
    assert opened.status_code == 200
    assert opened.json()["status"] == "session_restored"
    assert opened.json()["restored_cookies"] == 1
