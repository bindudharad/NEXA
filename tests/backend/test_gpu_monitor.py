from datetime import datetime, timedelta

from backend.database.session import SessionLocal, init_database
from backend.services.gpu_monitor import GpuMonitorService


def test_gpu_monitor_simulation_triggers_and_stops(monkeypatch):
    init_database()
    service = GpuMonitorService(SessionLocal)
    db = SessionLocal()
    sound_calls = []
    monkeypatch.setattr(service, "_play_sound", lambda: sound_calls.append("sound"))
    try:
        service.update_settings({"threshold_celsius": 50, "sound_enabled": True, "notification_enabled": True, "repeat_interval_seconds": 300}, db)
    finally:
        db.close()

    triggered = service.simulate(55)
    assert triggered["alert_active"] is True
    assert triggered["temperature_celsius"] == 55
    assert triggered["gpu_name"] == "Simulated GPU"
    assert sound_calls == ["sound"]

    stopped = service.simulate(45)
    assert stopped["alert_active"] is False
    assert stopped["last_stop_time"] is not None


def test_gpu_monitor_repeat_interval(monkeypatch):
    init_database()
    service = GpuMonitorService(SessionLocal)
    db = SessionLocal()
    sound_calls = []
    monkeypatch.setattr(service, "_play_sound", lambda: sound_calls.append("sound"))
    try:
        service.update_settings({"threshold_celsius": 50, "repeat_interval_seconds": 300, "notification_enabled": False}, db)
    finally:
        db.close()

    service.simulate(65)
    service.evaluate_once()
    assert len(sound_calls) == 1

    service.status.last_alert_time = (datetime.utcnow() - timedelta(seconds=301)).isoformat()
    service.evaluate_once()
    assert len(sound_calls) == 2


def test_gpu_monitor_settings_persist():
    init_database()
    service = GpuMonitorService(SessionLocal)
    db = SessionLocal()
    try:
        updated = service.update_settings({"threshold_celsius": 70, "sound_enabled": False, "repeat_interval_seconds": 600}, db)
        assert updated["threshold_celsius"] == 70
        assert service.get_settings(db).threshold_celsius == 70
        assert service.get_settings(db).sound_enabled is False
    finally:
        db.close()
