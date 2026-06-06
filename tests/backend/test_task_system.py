import json

from backend.database.models import Task
from backend.agents.system import SystemAgent
from backend.core.task_manager import TaskManager
from backend.database.models import TaskStatus
from backend.database.session import SessionLocal, init_database


def test_task_manager_pending_and_confirm_for_shutdown():
    init_database()
    db = SessionLocal()
    try:
        manager = TaskManager(db)
        task = manager.create_from_command("Shutdown after 5 minutes")
        assert task.status == TaskStatus.pending_confirmation.value
        assert task.requires_confirmation is True
    finally:
        db.close()


def test_task_manager_executes_memory_command():
    init_database()
    db = SessionLocal()
    try:
        task = TaskManager(db).create_from_command("remember task manager test")
        assert task.status == TaskStatus.completed.value
        assert json.loads(task.result_json)["remembered"] == "remember task manager test"
    finally:
        db.close()


def test_system_agent_launch_and_kill_are_callable(monkeypatch):
    calls = []

    class FakePopen:
        def __init__(self, command, shell=False):
            calls.append((command, shell))

    monkeypatch.setattr("backend.agents.system.agent.subprocess.Popen", FakePopen)
    result = SystemAgent().launch_app("notepad")
    assert result["launched"] == "notepad"
    assert calls[0][0] == ["notepad.exe"]


def test_system_status_has_metrics():
    status = SystemAgent().status()
    assert "cpu_percent" in status
    assert "ram_percent" in status


def test_task_manager_missing_task_errors():
    init_database()
    db = SessionLocal()
    try:
        manager = TaskManager(db)
        try:
            manager.confirm(999999)
        except ValueError as exc:
            assert "Task not found" in str(exc)
        else:
            raise AssertionError("Expected missing task error")
    finally:
        db.close()


def test_system_agent_power_commands_are_callable(monkeypatch):
    calls = []

    class FakePopen:
        def __init__(self, command, shell=False):
            calls.append(command)

    monkeypatch.setattr("backend.agents.system.agent.subprocess.Popen", FakePopen)
    agent = SystemAgent()
    assert agent.shutdown()["scheduled"] == "shutdown"
    assert agent.restart()["scheduled"] == "restart"
    assert agent.sleep()["scheduled"] == "sleep"
    assert agent.lock()["locked"] is True
    assert len(calls) == 4


def test_system_agent_kill_process(monkeypatch):
    class FakeProcess:
        info = {"pid": 123, "name": "demo.exe"}

        def kill(self):
            self.killed = True

    monkeypatch.setattr("backend.agents.system.agent.psutil.process_iter", lambda fields: [FakeProcess()])
    assert SystemAgent().kill_process("demo.exe")["killed"] == [123]


def test_task_manager_failure_path():
    init_database()
    db = SessionLocal()
    try:
        task = Task(command="bad", intent="bad", agent="unknown", plan_json=json.dumps({"intent": "bad", "agent": "unknown", "action": "x", "params": {}, "requires_confirmation": False}))
        db.add(task)
        db.commit()
        result = TaskManager(db).execute(task.id)
        assert "error" in result
    finally:
        db.close()
