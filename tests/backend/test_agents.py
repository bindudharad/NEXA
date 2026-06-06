from pathlib import Path
import pytest

from backend.agents.browser import BrowserAgent
from backend.agents.file_agent import FileAgent
from backend.agents.memory import MemoryAgent
from backend.agents.scheduler import SchedulerAgent
from backend.core.config import get_settings
from backend.database.session import SessionLocal, init_database


def test_file_agent_crud_and_search(tmp_path):
    settings = get_settings()
    original = settings.allowed_base_path
    settings.allowed_base_path = tmp_path
    try:
        agent = FileAgent()
        created = agent.create_file("notes/demo.txt", "hello")
        assert Path(created["created"]).exists()
        assert agent.search_files("demo", str(tmp_path))["count"] == 1
        moved = agent.move_file("notes/demo.txt", "archive")
        assert Path(moved["target"]).exists()
        renamed = agent.rename_file("archive/demo.txt", "renamed.txt")
        assert Path(renamed["target"]).exists()
        deleted = agent.delete_file("archive/renamed.txt")
        assert deleted["deleted"].endswith("renamed.txt")
        folder = agent.create_folder("folder")
        assert Path(folder["created"]).is_dir()
        removed = agent.delete_folder("folder")
        assert removed["deleted"].endswith("folder")
    finally:
        settings.allowed_base_path = original


def test_file_agent_blocks_outside_allowed_base(tmp_path):
    settings = get_settings()
    original = settings.allowed_base_path
    settings.allowed_base_path = tmp_path
    try:
        agent = FileAgent()
        outside = tmp_path.parent / "outside.txt"
        try:
            agent.create_file(str(outside), "blocked")
        except ValueError as exc:
            assert "outside allowed base path" in str(exc)
        else:
            raise AssertionError("Expected path traversal block")
    finally:
        settings.allowed_base_path = original


def test_browser_url_normalization():
    agent = BrowserAgent()
    assert agent.normalize_url("github") == "https://github.com"
    assert agent.normalize_url("example.com") == "https://example.com"
    assert agent.normalize_url("data:text/html,ok") == "data:text/html,ok"
    assert agent.execute("normalize_url", {"target": "google"}) == "https://google.com"


def test_browser_open_and_search(monkeypatch):
    opened = []
    monkeypatch.setattr("backend.agents.browser.agent.webbrowser.open", lambda url: opened.append(url))
    agent = BrowserAgent()
    assert agent.open_url("github")["opened"] == "https://github.com"
    import asyncio
    result = asyncio.run(agent.search_google("nexa"))
    assert "nexa" in result["opened"]
    assert len(opened) == 2


@pytest.mark.asyncio
async def test_browser_playwright_title_and_form():
    agent = BrowserAgent()
    title = await agent.scrape_title("data:text/html,<title>Nexa</title>")
    assert title["title"] == "Nexa"
    form = await agent.fill_form(
        "data:text/html,<title>Form</title><input id='name'><button id='go'>go</button>",
        {"#name": "Nexa"},
    )
    assert form["title"] == "Form"
    assert "#name" in form["filled"]


def test_scheduler_recurring_jobs():
    scheduler = SchedulerAgent()
    result = scheduler.schedule_daily("lock", 23, 30)
    assert result["cadence"] == "daily"
    assert any(job["id"] == result["job_id"] for job in scheduler.jobs())
    weekly = scheduler.schedule_weekly("lock", "mon", 9)
    monthly = scheduler.schedule_monthly("lock", 1, 9)
    assert weekly["cadence"] == "weekly"
    assert monthly["cadence"] == "monthly"


def test_scheduler_delayed_and_reminder_jobs():
    scheduler = SchedulerAgent()
    delayed = scheduler.schedule_delay("lock", 60)
    reminder = scheduler.create_reminder("check tests")
    assert delayed["command"] == "lock"
    assert reminder["text"] == "check tests"


def test_scheduler_run_command_routes(monkeypatch):
    scheduler = SchedulerAgent()
    monkeypatch.setattr(scheduler.system, "execute", lambda command, params: {"system": command})
    monkeypatch.setattr("backend.agents.scheduler.agent.FileAgent.backup_folder", lambda self, command: {"backup": command})
    monkeypatch.setattr("backend.agents.scheduler.agent.NotificationAgent.notify", lambda self, title, message: {"message": message})
    assert scheduler._run_command("lock")["system"] == "lock"
    assert scheduler._run_command("backup")["backup"] == "scheduled backup"
    assert scheduler._run_command("custom")["message"] == "custom"


def test_file_agent_duplicates_and_backup(tmp_path):
    settings = get_settings()
    original = settings.allowed_base_path
    settings.allowed_base_path = tmp_path.parent
    try:
        agent = FileAgent()
        source = tmp_path / "source"
        source.mkdir()
        agent.create_file(str(source / "a.txt"), "same")
        agent.create_file(str(source / "b.txt"), "same")
        assert agent.find_duplicates(str(source))["groups"] == 1
        backup = agent.backup_folder("test backup", str(source), str(tmp_path / "backups"))
        assert Path(backup["backup"]).exists()
    finally:
        settings.allowed_base_path = original


def test_file_agent_rejects_recursive_backup(tmp_path):
    settings = get_settings()
    original = settings.allowed_base_path
    settings.allowed_base_path = tmp_path
    try:
        agent = FileAgent()
        agent.create_file("a.txt", "same")
        try:
            agent.backup_folder("bad backup", str(tmp_path), str(tmp_path / "backups"))
        except ValueError as exc:
            assert "outside the source tree" in str(exc)
        else:
            raise AssertionError("Expected recursive backup protection")
    finally:
        settings.allowed_base_path = original


def test_memory_settings_and_history():
    init_database()
    db = SessionLocal()
    try:
        agent = MemoryAgent(db)
        setting = agent.set_setting("theme", "dark")
        assert setting["value"] == "dark"
        history = agent.conversation_history()
        assert isinstance(history, list)
    finally:
        db.close()
