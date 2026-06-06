from backend.automation import AutomationEngine
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
