from backend.database.session import SessionLocal, init_database
from backend.services.resource_manager import ResourceManagerService


class Battery:
    def __init__(self, percent, plugged):
        self.percent = percent
        self.power_plugged = plugged


def test_resource_manager_enters_power_saving(monkeypatch):
    init_database()
    service = ResourceManagerService(SessionLocal)
    monkeypatch.setattr("backend.services.resource_manager.psutil.sensors_battery", lambda: Battery(25, False))
    monkeypatch.setattr("backend.services.resource_manager.psutil.cpu_percent", lambda interval=0: 8)
    monkeypatch.setattr(service, "_cpu_temperature", lambda: 45)
    monkeypatch.setattr(service, "_idle_seconds", lambda: 0)

    status = service.evaluate_once()

    assert status["mode"] == "power_saving"
    assert status["power_saving"] is True
    assert service.interval_for("website_monitor", 600) >= 1800
    assert service.should_run_noncritical("website_monitor") is False


def test_resource_manager_enters_thermal_protection(monkeypatch):
    init_database()
    service = ResourceManagerService(SessionLocal)
    monkeypatch.setattr("backend.services.resource_manager.psutil.sensors_battery", lambda: Battery(80, True))
    monkeypatch.setattr("backend.services.resource_manager.psutil.cpu_percent", lambda interval=0: 20)
    monkeypatch.setattr(service, "_cpu_temperature", lambda: 85)
    monkeypatch.setattr(service, "_idle_seconds", lambda: 0)

    status = service.evaluate_once()

    assert status["mode"] == "thermal_protection"
    assert status["thermal_protection"] is True
    assert service.interval_for("system_alerts", 120) >= 240


def test_power_monitor_interval_policy(monkeypatch):
    init_database()
    service = ResourceManagerService(SessionLocal)
    monkeypatch.setattr("backend.services.resource_manager.psutil.sensors_battery", lambda: Battery(10, False))
    monkeypatch.setattr("backend.services.resource_manager.psutil.cpu_percent", lambda interval=0: 5)
    monkeypatch.setattr(service, "_cpu_temperature", lambda: 40)
    monkeypatch.setattr(service, "_idle_seconds", lambda: 0)

    service.evaluate_once()

    assert service.interval_for("power_monitor", 60) == 15
