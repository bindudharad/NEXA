from backend.database.models import ChargeHistory, PowerEvent
from backend.database.session import SessionLocal, init_database
from backend.services.power_monitor import PowerMonitorService


def test_power_monitor_detects_charger_connected_and_disconnected(monkeypatch):
    init_database()
    service = PowerMonitorService(SessionLocal, poll_interval_seconds=1)
    monkeypatch.setattr(service, "_read_windows_battery_health", lambda: {})
    with SessionLocal() as db:
        service.update_settings({"sound_enabled": False, "voice_enabled": False, "notification_enabled": True}, db)

    service.simulate(44, False)
    connected = service.simulate(45, True)
    disconnected = service.simulate(46, False)

    assert connected["is_charging"] is True
    assert disconnected["is_charging"] is False
    with SessionLocal() as db:
        event_types = [row.event_type for row in db.query(PowerEvent).order_by(PowerEvent.created_at.desc()).limit(4).all()]
        assert "charger_connected" in event_types
        assert "charger_disconnected" in event_types


def test_power_monitor_95_full_low_and_critical_events(monkeypatch):
    init_database()
    service = PowerMonitorService(SessionLocal, poll_interval_seconds=1)
    monkeypatch.setattr(service, "_read_windows_battery_health", lambda: {})
    with SessionLocal() as db:
        service.update_settings({"sound_enabled": False, "voice_enabled": False, "notification_enabled": True}, db)

    service.simulate(94, True)
    service.simulate(95, True)
    service.simulate(100, True)
    service.simulate(20, False)
    service.simulate(10, False)

    with SessionLocal() as db:
        event_types = [row.event_type for row in db.query(PowerEvent).all()]
        assert "battery_95" in event_types
        assert "battery_full" in event_types
        assert "low_battery" in event_types
        assert "critical_battery" in event_types


def test_power_monitor_detects_fluctuation(monkeypatch):
    init_database()
    service = PowerMonitorService(SessionLocal, poll_interval_seconds=1)
    monkeypatch.setattr(service, "_read_windows_battery_health", lambda: {})
    with SessionLocal() as db:
        service.update_settings(
            {
                "sound_enabled": False,
                "voice_enabled": False,
                "notification_enabled": True,
                "fluctuation_window_seconds": 30,
                "fluctuation_transition_count": 4,
            },
            db,
        )

    service.simulate(55, False)
    service.simulate(55, True)
    service.simulate(55, False)
    service.simulate(55, True)
    service.simulate(55, False)

    with SessionLocal() as db:
        assert db.query(PowerEvent).filter(PowerEvent.event_type == "power_fluctuation").count() >= 1


def test_power_monitor_tracks_charge_session(monkeypatch):
    init_database()
    service = PowerMonitorService(SessionLocal, poll_interval_seconds=1)
    monkeypatch.setattr(service, "_read_windows_battery_health", lambda: {})
    with SessionLocal() as db:
        service.update_settings({"sound_enabled": False, "voice_enabled": False, "notification_enabled": False}, db)

    service.simulate(20, False)
    service.simulate(21, True)
    service.simulate(85, False)

    with SessionLocal() as db:
        session = db.query(ChargeHistory).order_by(ChargeHistory.id.desc()).first()
        assert session is not None
        assert session.status == "completed"
        assert session.start_percent == 21
        assert session.end_percent == 85
        assert session.charge_added_percent == 64
