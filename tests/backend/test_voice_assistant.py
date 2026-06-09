from backend.database.models import AssignmentRecord, AttendanceRecord, CollegeProfile, CustomPersonality, DownloadHistory, FeeRecord, FocusSession, VoiceAnalytics, VoiceHistory, VoiceInteraction, VoiceProfile, WakeWordHistory
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
        settings = service.update_settings({"response_style": "professional", "wake_phrases": ["nexa", "hey nexa"], "activation_response": "I'm listening."}, db)
    assert settings["activation_response"] == "I'm listening."

    result = service.wake("Nexa", "test")
    assert result["activated"] is True
    assert result["response"] == "I'm listening."
    with SessionLocal() as db:
        assert db.query(VoiceInteraction).filter(VoiceInteraction.event_type == "wake_detected").count() >= 1


def test_voice_personality_modes_wake_responses_and_history(monkeypatch):
    init_database()
    service = VoiceAssistantService(SessionLocal)
    spoken: list[str] = []
    monkeypatch.setattr(service, "_start_windows_listener", lambda settings: None)
    monkeypatch.setattr(service, "speak", lambda text: spoken.append(text))

    expected = {
        "professional": {"Yes, how may I assist you?", "How may I assist you?"},
        "friendly": {"Hey! How can I help?", "I'm listening."},
        "jarvis": {"At your service.", "Ready when you are."},
        "minimal": {"Yes?", "Ready."},
        "funny": {"You summoned me?", "Ready for another mission?"},
    }
    for mode, valid in expected.items():
        with SessionLocal() as db:
            service.update_settings({"response_style": mode, "voice_enabled": True}, db)
        result = service.wake("Nexa", "test")
        assert result["response"] in valid

    with SessionLocal() as db:
        assert db.query(VoiceProfile).count() >= 6
        assert db.query(WakeWordHistory).count() >= 5
        assert db.query(VoiceHistory).filter(VoiceHistory.event_type == "wake_detected").count() >= 5
        assert db.query(VoiceAnalytics).count() >= 1
    assert spoken


def test_voice_silent_and_custom_personality(monkeypatch):
    init_database()
    service = VoiceAssistantService(SessionLocal)
    spoken: list[str] = []
    monkeypatch.setattr(service, "speak", lambda text: spoken.append(text))

    with SessionLocal() as db:
        service.update_settings({"response_style": "silent", "voice_enabled": True}, db)
    silent = service.wake("Nexa", "test")
    assert silent["response"] == ""
    assert spoken == []

    custom = service.create_custom_personality({"name": "Operator", "wake_responses": ["Standing by."], "completion_responses": ["Handled."]})
    with SessionLocal() as db:
        service.update_settings({"response_style": "custom", "custom_personality_id": custom["id"]}, db)
    custom_wake = service.wake("Nexa", "test")
    response = service.personality_response("completion", "Task completed successfully.", {})

    assert custom_wake["response"] == "Standing by."
    assert response == "Handled."
    with SessionLocal() as db:
        assert db.query(CustomPersonality).filter(CustomPersonality.id == custom["id"]).count() == 1


def test_voice_dashboard_profiles_and_context_responses(monkeypatch):
    init_database()
    service = VoiceAssistantService(SessionLocal)
    monkeypatch.setattr(service, "speak", lambda text: None)
    with SessionLocal() as db:
        service.update_settings({"response_style": "funny"}, db)

    battery = service.personality_response("battery_low", "Battery level is low. Please connect your charger.", {})
    completion = service.personality_response("completion", "Task completed successfully.", {})
    dashboard = service.dashboard()
    profiles = service.profiles()

    assert "food" in battery.lower()
    assert completion in {"Mission accomplished.", "Achievement unlocked: task completed."}
    assert dashboard["current_personality"] == "funny"
    assert dashboard["offline_ready"] is True
    assert any(item["profile_key"] == "jarvis" for item in profiles)


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


def test_voice_emergency_recovery_commands(monkeypatch, tmp_path):
    init_database()
    service = VoiceAssistantService(SessionLocal)
    monkeypatch.setattr(service, "speak", lambda text: None)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "main.py").write_text("print('recovery')", encoding="utf-8")

    capture = service.process_command("recover vscode", "test")
    assert capture["status"] == "completed"
    assert capture["result"]["action"] == "recovery_capture"

    dashboard = service.process_command("show recovery dashboard", "test")
    assert dashboard["status"] == "completed"
    assert dashboard["result"]["action"] == "recovery_dashboard"

    reports = service.process_command("show crash reports", "test")
    assert reports["status"] == "completed"
    assert reports["result"]["action"] == "recovery_crash_reports"

    restore = service.process_command("restore session", "test")
    assert restore["status"] == "completed"
    assert restore["result"]["action"] == "recovery_session_restore"


def test_voice_automation_builder_commands(monkeypatch):
    init_database()
    service = VoiceAssistantService(SessionLocal)
    monkeypatch.setattr(service, "speak", lambda text: None)

    created = service.process_command("create automation when battery reaches 20 percent notify me", "test")
    assert created["status"] == "completed"
    assert created["result"]["action"] == "automation_create"

    shown = service.process_command("show automations", "test")
    assert shown["status"] == "completed"
    assert shown["result"]["action"] == "automation_dashboard"

    paused = service.process_command("pause automation", "test")
    assert paused["status"] == "completed"
    assert paused["result"]["action"] == "automation_toggle"

    resumed = service.process_command("resume automation", "test")
    assert resumed["status"] == "completed"
    assert resumed["result"]["action"] == "automation_toggle"

    history = service.process_command("automation history", "test")
    assert history["status"] == "completed"
    assert history["result"]["action"] == "automation_history"


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


def test_voice_goal_tracker_commands(monkeypatch):
    init_database()
    service = VoiceAssistantService(SessionLocal)
    monkeypatch.setattr(service, "speak", lambda text: None)

    created = service.process_command("create goal drink water 4 count daily", "test")
    assert created["status"] == "completed"
    assert created["result"]["action"] == "goal_create"

    dashboard = service.process_command("show goals", "test")
    assert dashboard["status"] == "completed"
    assert dashboard["result"]["action"] == "goal_dashboard"

    completed = service.process_command("mark goal complete", "test")
    assert completed["status"] == "completed"
    assert completed["result"]["action"] == "goal_complete"

    streaks = service.process_command("show streaks", "test")
    assert streaks["status"] == "completed"
    assert streaks["result"]["action"] == "goal_streaks"

    achievements = service.process_command("show achievements", "test")
    assert achievements["status"] == "completed"
    assert achievements["result"]["action"] == "goal_achievements"


def test_voice_self_health_commands(monkeypatch):
    init_database()
    service = VoiceAssistantService(SessionLocal)
    monkeypatch.setattr(service, "speak", lambda text: None)

    health = service.process_command("show nexa health", "test")
    assert health["status"] == "completed"
    assert health["result"]["action"] == "self_health_dashboard"

    cpu = service.process_command("show nexa cpu", "test")
    assert cpu["status"] == "completed"
    assert cpu["result"]["action"] == "self_health_cpu"

    api = service.process_command("show api status", "test")
    assert api["status"] == "completed"
    assert api["result"]["action"] == "self_health_api"

    optimized = service.process_command("optimize nexa", "test")
    assert optimized["status"] == "completed"
    assert optimized["result"]["action"] == "self_health_optimize"


def test_voice_college_companion_commands(monkeypatch):
    init_database()
    service = VoiceAssistantService(SessionLocal)
    monkeypatch.setattr(service, "speak", lambda text: None)
    with SessionLocal() as db:
        profile = CollegeProfile(name="Voice College", portal_type="erp", target_attendance_percent=75)
        db.add(profile)
        db.flush()
        db.add(AttendanceRecord(profile_id=profile.id, subject="Overall", attended_classes=80, total_classes=100, percentage=80, target_percentage=75))
        db.add(AssignmentRecord(profile_id=profile.id, title="DBMS Assignment", status="pending"))
        db.add(FeeRecord(profile_id=profile.id, fee_type="Exam Fee", amount=1000, status="pending"))
        db.commit()

    attendance = service.process_command("show attendance", "test")
    assert attendance["status"] == "completed"
    assert attendance["result"]["action"] == "college_attendance"

    assignments = service.process_command("show assignments", "test")
    assert assignments["status"] == "completed"
    assert assignments["result"]["action"] == "college_assignments"

    fees = service.process_command("show fees", "test")
    assert fees["status"] == "completed"
    assert fees["result"]["action"] == "college_fees"
