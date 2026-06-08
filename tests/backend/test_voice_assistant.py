from backend.database.models import DownloadHistory, FocusSession, VoiceInteraction
from backend.database.session import SessionLocal, init_database
from backend.services.voice_assistant import VoiceAssistantService


def clear_active_focus_sessions():
    with SessionLocal() as db:
        for row in db.query(FocusSession).filter(FocusSession.status.in_(["active", "paused"])).all():
            row.status = "completed"
        db.commit()


def test_voice_settings_persist_and_wake_records_interaction(monkeypatch):
    init_database()
    service = VoiceAssistantService(SessionLocal)
    monkeypatch.setattr(service, "_start_windows_listener", lambda settings: None)
    monkeypatch.setattr(service, "speak", lambda text: None)
    with SessionLocal() as db:
        settings = service.update_settings({"wake_phrases": ["nexa", "hey nexa"], "activation_response": "I'm listening."}, db)
    assert settings["activation_response"] == "I'm listening."

    result = service.wake("Nexa", "test")
    assert result["activated"] is True
    assert result["response"] == "I'm listening."
    with SessionLocal() as db:
        assert db.query(VoiceInteraction).filter(VoiceInteraction.event_type == "wake_detected").count() >= 1


def test_voice_pause_resume_status(monkeypatch):
    init_database()
    service = VoiceAssistantService(SessionLocal)
    monkeypatch.setattr(service, "_start_windows_listener", lambda settings: None)
    service.start()
    paused = service.pause()
    assert paused["muted"] is True
    assert paused["microphone_status"] == "muted"
    resumed = service.resume()
    assert resumed["muted"] is False
    assert resumed["microphone_status"] == "listening"


def test_voice_local_battery_command(monkeypatch):
    init_database()
    service = VoiceAssistantService(SessionLocal)
    monkeypatch.setattr(service, "speak", lambda text: None)
    monkeypatch.setattr("backend.services.voice_assistant.power_monitor_service.get_status", lambda: {"battery_percent": 72, "is_charging": True})
    result = service.process_command("what is my battery level", "test")
    assert result["status"] == "completed"
    assert "72 percent" in result["response"]
    assert "charging" in result["response"]


def test_voice_local_notifications_command(monkeypatch):
    init_database()
    service = VoiceAssistantService(SessionLocal)
    monkeypatch.setattr(service, "speak", lambda text: None)
    result = service.process_command("show notifications", "test")
    assert result["status"] == "completed"
    assert "notifications" in result["response"]


def test_voice_focus_mode_lifecycle(monkeypatch):
    init_database()
    clear_active_focus_sessions()
    service = VoiceAssistantService(SessionLocal)
    monkeypatch.setattr(service, "speak", lambda text: None)

    started = service.process_command("Nexa start study mode for 2 hours", "test")
    assert started["status"] == "completed"
    assert started["result"]["action"] == "focus_start"
    assert started["result"]["session"]["detail"]["session_type"] == "study"
    assert started["result"]["session"]["detail"]["pomodoro"]["focus_minutes"] == 120

    progress = service.process_command("show focus progress", "test")
    assert progress["status"] == "completed"
    assert progress["result"]["action"] == "focus_progress"

    paused = service.process_command("pause focus mode", "test")
    assert paused["status"] == "completed"
    assert paused["result"]["action"] == "focus_pause"
    assert paused["result"]["session"]["status"] == "paused"

    resumed = service.process_command("resume focus mode", "test")
    assert resumed["status"] == "completed"
    assert resumed["result"]["action"] == "focus_resume"
    assert resumed["result"]["session"]["status"] == "active"

    extended = service.process_command("extend focus by 10 minutes", "test")
    assert extended["status"] == "completed"
    assert extended["result"]["action"] == "focus_extend"

    ended = service.process_command("end focus mode", "test")
    assert ended["status"] == "completed"
    assert ended["result"]["action"] == "focus_end"
    assert ended["result"]["session"]["status"] == "completed"


def test_voice_study_assistant_commands(monkeypatch):
    init_database()
    service = VoiceAssistantService(SessionLocal)
    monkeypatch.setattr(service, "speak", lambda text: None)

    created = service.process_command("Nexa create a study plan for DBMS exam is in 10 days", "test")
    assert created["status"] == "completed"
    assert created["result"]["action"] == "study_plan_create"
    assert created["result"]["plan"]["subject"]["name"] == "DBMS"

    progress = service.process_command("show study progress", "test")
    assert progress["status"] == "completed"
    assert progress["result"]["action"] == "study_progress"

    countdown = service.process_command("show exam countdown", "test")
    assert countdown["status"] == "completed"
    assert countdown["result"]["action"] == "exam_countdown"

    revision = service.process_command("show revision plan", "test")
    assert revision["status"] == "completed"
    assert revision["result"]["action"] == "revision_plan"

    session = service.process_command("start study session for DBMS for 30 minutes", "test")
    assert session["status"] == "completed"
    assert session["result"]["action"] == "study_session"
    assert session["result"]["session"]["duration_seconds"] == 30 * 60

    completed = service.process_command("mark chapter complete transactions", "test")
    assert completed["status"] == "completed"
    assert completed["result"]["action"] == "study_chapter_complete"
    assert completed["result"]["chapter"]["status"] == "completed"


def test_voice_memory_timeline_commands(monkeypatch):
    init_database()
    service = VoiceAssistantService(SessionLocal)
    monkeypatch.setattr(service, "speak", lambda text: None)
    from backend.services.evolution import evolution_service

    with SessionLocal() as db:
        evolution_service.add_timeline_event(db, "coding", "Completed voice timeline test", "Voice search memory", "test", duration_seconds=3600, metadata={"important": True})
        evolution_service.add_timeline_event(db, "study", "Studied DBMS timeline", "Study memory", "test", duration_seconds=1800)

    timeline = service.process_command("show timeline", "test")
    assert timeline["status"] == "completed"
    assert timeline["result"]["action"] == "timeline_show"

    yesterday = service.process_command("what did I do yesterday", "test")
    assert yesterday["status"] == "completed"
    assert yesterday["result"]["action"] == "timeline_search"

    coding = service.process_command("show coding history", "test")
    assert coding["status"] == "completed"
    assert coding["result"]["action"] == "timeline_search"

    weekly = service.process_command("generate weekly report", "test")
    assert weekly["status"] == "completed"
    assert weekly["result"]["action"] == "timeline_weekly_report"


def test_voice_project_guardian_commands(monkeypatch, tmp_path):
    init_database()
    service = VoiceAssistantService(SessionLocal)
    monkeypatch.setattr(service, "speak", lambda text: None)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app.py").write_text("print('guardian')", encoding="utf-8")

    snapshot = service.process_command("backup project", "test")
    assert snapshot["status"] == "completed"
    assert snapshot["result"]["action"] == "project_snapshot"

    backups = service.process_command("show backups", "test")
    assert backups["status"] == "completed"
    assert backups["result"]["action"] == "project_backups"

    git = service.process_command("show git status", "test")
    assert git["status"] == "completed"
    assert git["result"]["action"] == "project_git_status"

    health = service.process_command("show project health", "test")
    assert health["status"] == "completed"
    assert health["result"]["action"] == "project_health"

    recovery = service.process_command("recover last version", "test")
    assert recovery["status"] == "completed"
    assert recovery["result"]["action"] == "project_recovery"


def test_voice_download_manager_commands(monkeypatch):
    init_database()
    service = VoiceAssistantService(SessionLocal)
    monkeypatch.setattr(service, "speak", lambda text: None)
    with SessionLocal() as db:
        db.add(DownloadHistory(file_path="C:/Downloads/notes.pdf", file_name="notes.pdf", category="PDF", size_bytes=2048))
        db.add(DownloadHistory(file_path="C:/Downloads/movie.mp4", file_name="movie.mp4", category="Videos", size_bytes=200 * 1024 * 1024))
        db.commit()

    dashboard = service.process_command("show downloads", "test")
    assert dashboard["status"] == "completed"
    assert dashboard["result"]["action"] == "downloads_dashboard"

    pdfs = service.process_command("find PDFs", "test")
    assert pdfs["status"] == "completed"
    assert pdfs["result"]["action"] == "downloads_search"
    assert pdfs["result"]["result"]["results"]

    large = service.process_command("show large files", "test")
    assert large["status"] == "completed"
    assert large["result"]["action"] == "downloads_large_files"


def test_voice_screenshot_assistant_commands(monkeypatch, tmp_path):
    init_database()
    service = VoiceAssistantService(SessionLocal)
    monkeypatch.setattr(service, "speak", lambda text: None)
    from backend.services.evolution import evolution_service

    screenshot = tmp_path / "screen.png"
    screenshot.write_bytes(b"png")
    with SessionLocal() as db:
        evolution_service.record_screenshot(db, str(screenshot), "voice_test", extracted_text="Traceback error in app.py")

    history = service.process_command("show screenshot history", "test")
    assert history["status"] == "completed"
    assert history["result"]["action"] == "screenshot_history"

    explain = service.process_command("explain this error", "test")
    assert explain["status"] == "completed"
    assert explain["result"]["action"] == "screenshot_explain_error"

    read = service.process_command("read screenshot", "test")
    assert read["status"] == "completed"
    assert read["result"]["action"] == "screenshot_read_text"

    saved = service.process_command("save notes", "test")
    assert saved["status"] == "completed"
    assert saved["result"]["action"] == "screenshot_save_notes"
