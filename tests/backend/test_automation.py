from backend.automation import AutomationEngine
from backend.database.models import AutomationAction, AutomationAnalytics, AutomationCondition, AutomationHistory, AutomationTemplate, AutomationTrigger
from backend.database.session import SessionLocal, init_database


def test_event_automation_fires_notification():
    init_database()
    db = SessionLocal()
    try:
        engine = AutomationEngine(db)
        created = engine.create(
            "Download complete",
            {"event_type": "download_completed"},
            {"type": "notify", "message": "Download finished"},
        )
        assert created["name"] == "Download complete"
        fired = engine.ingest_event("download_completed", {"file": "a.pdf"})
        assert fired[0]["message"] == "Download finished"
        assert db.query(AutomationTrigger).count() >= 1
        assert db.query(AutomationCondition).count() >= 1
        assert db.query(AutomationAction).count() >= 1
        assert db.query(AutomationHistory).filter(AutomationHistory.status == "success").count() >= 1
        assert db.query(AutomationAnalytics).count() >= 1
    finally:
        db.close()


def test_metric_automation_skips_unknown_action():
    init_database()
    db = SessionLocal()
    try:
        engine = AutomationEngine(db)
        engine.create(
            "Always true",
            {"metric": "cpu", "operator": ">", "value": -1},
            {"type": "unknown"},
        )
        fired = engine.evaluate()
        assert any("skipped" in item for item in fired)
    finally:
        db.close()


def test_nested_conditions_templates_dashboard_and_high_risk_approval():
    init_database()
    db = SessionLocal()
    try:
        engine = AutomationEngine(db)
        created = engine.create(
            "Battery low and unplugged",
            {"all": [{"metric": "battery", "operator": "<=", "value": 101}, {"metric": "charging", "operator": "==", "value": False}]},
            {"type": "shutdown", "requires_approval": True},
            description="High-risk automation should not execute without approval.",
        )
        assert created["triggers"]
        assert created["actions"][0]["requires_approval"] is True

        result = engine.ingest_event("manual", {"battery": 10, "charging": False})
        assert any(item.get("requires_approval") for item in result)

        templates = engine.templates()
        dashboard = engine.dashboard()
        analytics = engine.analytics()

        assert any(item["name"] == "Battery Low Alert" for item in templates)
        assert db.query(AutomationTemplate).count() >= 1
        assert dashboard["offline_ready"] is True
        assert analytics["summary"]["pending_approvals"] >= 1
    finally:
        db.close()
