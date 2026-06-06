from datetime import datetime, timedelta

from backend.database.session import SessionLocal, init_database
from backend.services.battery_alert import BatteryAlertService


def test_battery_alert_simulation_triggers_and_stops(monkeypatch):
    init_database()
    service = BatteryAlertService(SessionLocal, poll_interval_seconds=1)
    db = SessionLocal()
    try:
        service.update_settings(
            {
                "enabled": True,
                "threshold_percent": 20,
                "voice_enabled": True,
                "sound_enabled": True,
                "notification_enabled": True,
                "repeat_interval_seconds": 120,
            },
            db,
        )
    finally:
        db.close()
    calls = []
    monkeypatch.setattr(service, "_play_sound", lambda: calls.append("sound"))
    monkeypatch.setattr(service, "_speak", lambda percent: calls.append(("voice", percent)))
    status = service.simulate(20, False)
    assert status["alert_active"] is True
    assert calls == ["sound", ("voice", 20)]
    stopped = service.simulate(20, True)
    assert stopped["alert_active"] is False


def test_battery_alert_repeat_interval(monkeypatch):
    init_database()
    service = BatteryAlertService(SessionLocal, poll_interval_seconds=1)
    db = SessionLocal()
    try:
        service.update_settings({"repeat_interval_seconds": 120, "threshold_percent": 20}, db)
    finally:
        db.close()
    calls = []
    monkeypatch.setattr(service, "_play_sound", lambda: calls.append("sound"))
    monkeypatch.setattr(service, "_speak", lambda percent: calls.append(("voice", percent)))
    service.simulate(10, False)
    service.evaluate_once()
    assert len(calls) == 2
    service.status.last_alert_time = (datetime.utcnow() - timedelta(seconds=121)).isoformat()
    service.evaluate_once()
    assert len(calls) == 4


def test_battery_alert_settings_persist():
    init_database()
    service = BatteryAlertService(SessionLocal, poll_interval_seconds=1)
    db = SessionLocal()
    try:
        updated = service.update_settings({"threshold_percent": 25, "voice_enabled": False}, db)
        assert updated["threshold_percent"] == 25
        settings = service.get_settings(db)
        assert settings.threshold_percent == 25
        assert settings.voice_enabled is False
    finally:
        db.close()
