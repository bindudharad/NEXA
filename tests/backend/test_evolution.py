import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from backend.database.models import Achievement, ActivityHistory, AnnouncementRecord, AssignmentRecord, AttendanceRecord, Automation, AutomationAction, AutomationHealth, AutomationHistory, AutomationTrigger, BlockedSite, BriefingAnalytics, BriefingHistory, BriefingRecommendation, BriefingSchedule, CleanupSuggestion, CodingSession, CollegeProfile, CollegeUpdate, CrashReport, DailyBriefing, DocumentSummary, DownloadAnalytics, DownloadRule, DuplicateFile, ErrorAnalysis, FeeRecord, FocusAnalytics, FocusGoal, FocusHistory, FocusSession, GitHistory, Goal, GoalAnalytics, GoalHistory, GoalProgress, HealthMetric, HealthScore, IncidentReport, InternalMark, KCETRecord, MemorySearch, OCRResult, OptimizationEvent, ProjectBackup, ProjectEvent, ProjectHealth, ProjectSnapshot, RecoveredApplication, RecoveryEvent, RecoveryHistory, RecoveryPoint, RecoverySession, ResourceUsage, ResultRecord, ScreenshotAction, ScreenshotHistory, StorageReport, Streak, StudyAnalytics, StudyChapter, StudyPlan, StudySession, StudySubject, TimetableRecord, TimelineEvent, TimelineInsight, TimelineSummary, WebsiteProfile
from backend.database.models import ContextSnapshot, CopilotAction, CopilotAnalytics, CopilotHistory, CopilotInsight, CopilotWarning, DeviceToken, MobileAuditLog, MobileDevice, PairingCode, SyncQueue
from backend.database.session import SessionLocal, init_database
from backend.services.download_monitor import DownloadMonitoringService
from backend.services.evolution import EvolutionService


def test_daily_briefing_persists_and_returns_summary():
    init_database()
    service = EvolutionService(SessionLocal)

    with SessionLocal() as db:
        briefing = service.generate_daily_briefing(db, speak=False, notify=True)

        assert briefing["summary"]
        assert "weather" in briefing["payload"]
        assert "downloads" in briefing["payload"]
        assert "website_alerts" in briefing["payload"]
        assert "sections" in briefing["payload"]
        assert "recommendations" in briefing["payload"]
        assert "insights" in briefing["payload"]
        assert db.get(DailyBriefing, briefing["id"]) is not None
        assert db.query(BriefingHistory).filter(BriefingHistory.briefing_id == briefing["id"]).count() >= 1
        assert db.query(BriefingRecommendation).filter(BriefingRecommendation.briefing_id == briefing["id"]).count() >= 1
        assert db.query(BriefingAnalytics).filter(BriefingAnalytics.briefing_date == briefing["briefing_date"]).count() >= 1


def test_daily_briefing_settings_persist():
    init_database()
    service = EvolutionService(SessionLocal)

    with SessionLocal() as db:
        settings = service.update_briefing_settings(db, {"time": "08:30", "days": "weekdays", "on_startup": True, "weather_location": "Bengaluru"})

        assert settings["time"] == "08:30"
        assert settings["days"] == "weekdays"
        assert service.get_briefing_settings(db)["weather_location"] == "Bengaluru"
        assert db.query(BriefingSchedule).first() is not None


def test_daily_briefing_history_recommendations_analytics_and_mobile():
    init_database()
    service = EvolutionService(SessionLocal)

    with SessionLocal() as db:
        briefing = service.generate_daily_briefing(db, speak=False, notify=False, delivery_method="test")
        history = service.briefing_history(db)
        recommendations = service.briefing_recommendations(db)
        analytics = service.briefing_analytics(db)
        mobile = service.mobile_summary(db)

        assert history[0]["briefing_id"] == briefing["id"]
        assert recommendations
        assert analytics
        assert mobile["daily_briefing"]["id"] == briefing["id"]
        assert "copilot" in briefing["payload"]
        assert "top_recommendations" in briefing["payload"]["copilot"]
        assert "copilot" in mobile
        assert mobile["copilot"]["offline_ready"] is True


def test_daily_briefing_weather_offline_is_graceful(monkeypatch):
    init_database()
    service = EvolutionService(SessionLocal)
    monkeypatch.setattr("backend.services.evolution.requests.get", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("offline")))

    with SessionLocal() as db:
        service.update_briefing_settings(db, {"weather_location": "Bengaluru"})
        briefing = service.generate_daily_briefing(db, speak=False, notify=False)

        assert briefing["payload"]["weather"]["status"] == "offline"


def test_focus_session_start_and_end():
    init_database()
    service = EvolutionService(SessionLocal)

    with SessionLocal() as db:
        active = db.query(FocusSession).filter(FocusSession.status == "active").all()
        for row in active:
            row.status = "cancelled"
        db.commit()
        session = service.start_focus(db, "Test Focus", duration_minutes=1, session_type="study", subject="DBMS", chapter="Transactions", topic="Locks", current_goal="Study locks", blocked_websites=["youtube.com"])
        status = service.focus_status(db)
        distraction = service.check_focus_distraction(db, url="https://youtube.com/watch?v=abc")
        paused = service.pause_focus(db, session["id"])
        resumed = service.resume_focus(db, session["id"])
        extended = service.extend_focus(db, 10, session["id"])
        break_state = service.start_focus_break(db, 5, session["id"])
        completed = service.end_focus(db, session["id"], tasks_completed=2, distraction_count=1, goal_completion_percent=100)

        assert status["active"] is True
        assert "youtube.com" in status["detail"]["blocked_websites"]
        assert distraction["blocked"] is True
        assert paused["status"] == "paused"
        assert resumed["status"] == "active"
        assert extended["detail"]["planned_minutes"] == 11
        assert break_state["detail"]["pomodoro"]["state"] == "break"
        assert completed["status"] == "completed"
        assert completed["productivity_score"] > 0
        assert db.query(BlockedSite).filter(BlockedSite.domain == "youtube.com").count() >= 1
        assert db.query(FocusHistory).filter(FocusHistory.session_id == session["id"]).count() >= 5
        assert db.query(FocusAnalytics).filter(FocusAnalytics.session_id == session["id"]).count() == 1


def test_focus_goals_and_dashboard():
    init_database()
    service = EvolutionService(SessionLocal)

    with SessionLocal() as db:
        for row in db.query(FocusSession).filter(FocusSession.status.in_(["active", "paused"])).all():
            row.status = "cancelled"
        db.commit()
        session = service.start_focus(db, "Coding Focus", duration_minutes=25, session_type="coding", current_goal="Code feature")
        goal = service.create_focus_goal(db, "Code 25 minutes", "coding", 25, session["id"])
        updated = service.update_focus_goal(db, goal["id"], 25)
        dashboard = service.focus_dashboard(db)

        assert updated["status"] == "completed"
        assert dashboard["active"]["active"] is True
        assert any(item["id"] == goal["id"] for item in dashboard["goals"])


def test_study_plan_and_progress_tracking():
    init_database()
    service = EvolutionService(SessionLocal)

    with SessionLocal() as db:
        plan = service.create_study_plan(db, "Networks Exam", exam_date="2099-01-10", topics=["OSI", "TCP"], subject_name="CN", priority="high")
        updated = service.update_study_progress(db, plan["id"], "OSI", 100, "completed")
        reminder = service.schedule_study_reminder(db, plan["id"], "TCP")
        subject = service.create_study_subject(db, "DBMS", "high", "hard", "2099-01-15", 95)
        chapter = service.add_study_chapter(db, subject["id"], "Transactions", "Unit 3", ["Locks", "Serializability"], "high", "hard")
        chapter_done = service.update_study_chapter_progress(db, chapter["id"], 100, "completed")
        session = service.record_study_session(db, subject["id"], chapter_id=chapter["id"], topic="Locks", duration_minutes=45, session_type="revision")
        goal = service.create_study_goal(db, "Study DBMS 3 Hours", 3, "hours", subject["id"], "2099-01-14")
        goal_done = service.update_study_goal(db, goal["id"], 3)
        dashboard = service.study_dashboard(db)

        assert updated["progress_percent"] >= 50
        assert updated["revision_plan"]
        assert reminder["notification"]["module"] == "study_assistant"
        assert chapter_done["status"] == "completed"
        assert session["duration_seconds"] == 45 * 60
        assert goal_done["status"] == "completed"
        assert dashboard["subjects"]
        assert dashboard["exams"]
        assert dashboard["revisions"]
        assert dashboard["analytics"]
        assert dashboard["recommendations"]
        assert dashboard["offline_ready"] is True
        assert db.get(StudyPlan, plan["id"]) is not None
        assert db.query(StudySubject).filter(StudySubject.name == "DBMS").count() >= 1
        assert db.query(StudyChapter).filter(StudyChapter.title == "Transactions").count() >= 1
        assert db.query(StudySession).count() >= 1
        assert db.query(StudyAnalytics).count() >= 1


def test_focus_study_session_updates_study_assistant():
    init_database()
    service = EvolutionService(SessionLocal)

    with SessionLocal() as db:
        for row in db.query(FocusSession).filter(FocusSession.status.in_(["active", "paused"])).all():
            row.status = "cancelled"
        db.commit()
        session = service.start_focus(db, "DBMS Study Focus", duration_minutes=1, session_type="study", subject="DBMS", chapter="Transactions", topic="Locks")
        completed = service.end_focus(db, session["id"], tasks_completed=1, goal_completion_percent=100)
        dashboard = service.study_dashboard(db)

        assert completed["status"] == "completed"
        assert any(item["focus_session_id"] == session["id"] for item in dashboard["sessions"])
        assert any(item["name"] == "DBMS" for item in dashboard["subjects"])


def test_timeline_is_searchable():
    init_database()
    service = EvolutionService(SessionLocal)

    with SessionLocal() as db:
        event = service.add_timeline_event(db, "study", "Studied DBMS joins", "SQL joins revision", "test")
        results = service.search_timeline(db, query="DBMS")

        assert any(item["id"] == event["id"] for item in results)
        assert db.get(TimelineEvent, event["id"]) is not None


def test_ai_memory_timeline_summaries_search_and_insights():
    init_database()
    service = EvolutionService(SessionLocal)

    with SessionLocal() as db:
        coding = service.add_timeline_event(db, "coding", "Completed Nexa timeline module", "Worked on AI Memory Timeline", "test", duration_seconds=7200, metadata={"project": "Nexa", "important": True})
        study = service.add_timeline_event(db, "study", "Completed DBMS Unit 3", "Transactions revision", "study_assistant", duration_seconds=3600)
        focus = service.add_timeline_event(db, "focus", "Focus mode completed", "Deep work", "focus_mode", duration_seconds=1800)
        duplicate = service.add_timeline_event(db, "focus", "Focus mode completed", "Deep work", "focus_mode", duration_seconds=1800)
        search = service.natural_memory_search(db, "show study history")
        today = service.timeline_summary(db, "day", force=True)
        week = service.timeline_summary(db, "week", force=True)
        dashboard = service.timeline_dashboard(db, "today")

        assert coding["metadata"]["importance"] >= 80
        assert study["event_type"] == "study"
        assert duplicate["id"] == focus["id"]
        assert search["results"]
        assert "study" in search["summary"]
        assert today["stats"]["study_seconds"] >= 3600
        assert week["summary"]
        assert dashboard["offline_ready"] is True
        assert dashboard["events"]
        assert db.query(ActivityHistory).count() >= 3
        assert db.query(MemorySearch).count() >= 1
        assert db.query(TimelineSummary).count() >= 1
        assert db.query(TimelineInsight).count() >= 1


def test_goal_unlocks_achievement():
    init_database()
    service = EvolutionService(SessionLocal)

    with SessionLocal() as db:
        goal = service.create_goal(db, "Code 4 Hours", 4, "hours", "coding", description="Daily coding", deadline="2026-06-20", priority="high", category="coding")
        updated = service.update_goal(db, goal["id"], 4, "test", "completed in test")
        stats = service.goal_stats(db)
        dashboard = service.goal_dashboard(db)
        analytics = service.goal_analytics(db)

        assert updated["status"] == "achieved"
        assert updated["description"] == "Daily coding"
        assert updated["priority"] == "high"
        assert stats["achieved"] >= 1
        assert dashboard["offline_ready"] is True
        assert dashboard["completed_goals"]
        assert "success_rate" in analytics
        assert db.query(Achievement).filter(Achievement.title.contains("Code 4 Hours")).count() >= 1
        assert db.query(GoalProgress).filter(GoalProgress.goal_id == goal["id"]).count() >= 1
        assert db.query(GoalHistory).filter(GoalHistory.goal_id == goal["id"]).count() >= 1
        assert db.query(GoalAnalytics).filter(GoalAnalytics.goal_id == goal["id"]).count() >= 1
        assert db.query(Streak).filter(Streak.goal_id == goal["id"]).count() >= 1
        assert db.get(Goal, goal["id"]) is not None


def test_goal_auto_tracking_uses_coding_study_and_focus_sources():
    init_database()
    service = EvolutionService(SessionLocal)
    today = datetime.utcnow()

    with SessionLocal() as db:
        coding = service.create_goal(db, "Auto Coding Goal", 2, "hours", "coding")
        study = service.create_goal(db, "Auto Study Goal", 1, "hours", "study")
        focus = service.create_goal(db, "Auto Focus Goal", 30, "minutes", "focus")
        db.add(CodingSession(app_name="VS Code", project="Nexa", duration_seconds=7200, started_at=today))
        db.add(StudySession(subject_name="DBMS", duration_seconds=3600, started_at=today, created_at=today))
        db.add(FocusSession(title="Focus", duration_seconds=1800, started_at=today, status="completed"))
        db.commit()

        result = service.refresh_goal_auto_tracking(db)
        dashboard = service.goal_dashboard(db)

        assert result["count"] >= 3
        refreshed = {goal["id"]: goal for goal in dashboard["goals"]}
        assert refreshed[coding["id"]]["progress_percent"] == 100
        assert refreshed[study["id"]]["progress_percent"] == 100
        assert refreshed[focus["id"]]["progress_percent"] == 100


def test_self_health_dashboard_persists_metrics_and_optimizes():
    init_database()
    service = EvolutionService(SessionLocal)

    with SessionLocal() as db:
        dashboard = service.self_health(db)
        optimized = service.optimize_self_health(db, "optimize")

        assert "cpu" in dashboard
        assert "ram" in dashboard
        assert "api_health" in dashboard
        assert "automation_health" in dashboard
        assert "module_scores" in dashboard
        assert dashboard["offline_ready"] is True
        assert dashboard["orbital"]["button"] == "Health"
        assert optimized["action"] == "optimize"
        assert db.query(ResourceUsage).count() >= 1
        assert db.query(HealthScore).count() >= 1
        assert db.query(HealthMetric).count() >= 1
        assert db.query(AutomationHealth).count() >= 1
        assert db.query(OptimizationEvent).count() >= 1


def test_automation_builder_creates_existing_automation_record():
    init_database()
    service = EvolutionService(SessionLocal)

    with SessionLocal() as db:
        result = service.build_automation(db, "When battery reaches 20% and charger is not connected, notify me every 2 minutes")

        assert result["trigger"]["metric"] == "battery"
        assert result["conditions"][0]["metric"] == "charging"
        assert result["schedule"]["repeat_every_seconds"] == 120
        assert db.get(Automation, result["automation"]["id"]) is not None
        assert db.query(AutomationTrigger).count() >= 1
        assert db.query(AutomationAction).count() >= 1


def test_automation_builder_marks_high_risk_for_approval():
    init_database()
    service = EvolutionService(SessionLocal)

    with SessionLocal() as db:
        result = service.build_automation(db, "When I say cleanup delete files after browser automation")

        assert result["approval"]["required"] is True
        assert result["automation"]["actions"][0]["requires_approval"] is True


def test_automation_builder_codex_and_kcet_examples():
    init_database()
    service = EvolutionService(SessionLocal)

    with SessionLocal() as db:
        shutdown = service.build_automation(db, "After Codex finishes all queued tasks, shutdown the laptop after 5 minutes.")
        kcet = service.build_automation(db, "Check KCET results every 30 minutes.")
        briefing = service.generate_daily_briefing(db, notify=False, delivery_method="dashboard")

        assert shutdown["trigger"]["event_type"] == "codex_queue_completed"
        assert shutdown["action"]["type"] == "shutdown"
        assert shutdown["approval"]["required"] is True
        assert shutdown["schedule"]["delay_seconds"] == 300
        assert kcet["trigger"]["event_type"] == "kcet_available"
        assert kcet["schedule"]["repeat_every_seconds"] == 1800
        assert any(item["id"] == "automations" for item in briefing["payload"]["sections"])
        assert db.query(AutomationHistory).filter(AutomationHistory.event_type == "created").count() >= 2


def test_daily_briefing_uses_voice_personality():
    init_database()
    service = EvolutionService(SessionLocal)
    from backend.services.voice_assistant import voice_assistant_service

    with SessionLocal() as db:
        voice_assistant_service.update_settings({"response_style": "jarvis"}, db)
        briefing = service.generate_daily_briefing(db, notify=False, delivery_method="dashboard")

        assert briefing["payload"]["voice_text"].startswith("Good morning. Your briefing is ready.")


def test_college_companion_requests_profile_when_missing():
    init_database()
    service = EvolutionService(SessionLocal)

    with SessionLocal() as db:
        result = service.check_college_updates(db, "unlikely-college-profile-name")

        assert result["requires_profile"] is True
        assert db.query(CollegeUpdate).filter(CollegeUpdate.status == "requires_profile").count() >= 1


def test_college_companion_ingests_profile_data_and_dashboard():
    init_database()
    service = EvolutionService(SessionLocal)
    sample = {
        "college_data": {
            "attendance": [{"subject": "Overall", "attended_classes": 62, "total_classes": 80, "percentage": 72.5}],
            "marks": [{"subject": "DBMS", "component": "CIA", "marks_obtained": 42, "max_marks": 50}],
            "results": [{"exam_name": "Semester 4", "summary": "Passed", "score": "8.4 SGPA"}],
            "assignments": [{"title": "DBMS Assignment", "subject": "DBMS", "deadline": "2099-01-02", "status": "pending"}],
            "fees": [{"fee_type": "Exam Fee", "amount": 1200, "due_at": "2099-01-05", "status": "pending"}],
            "timetables": [{"title": "DBMS Lab", "starts_at": "2099-01-01T10:00:00", "ends_at": "2099-01-01T12:00:00", "location": "Lab 1"}],
            "announcements": [{"title": "Holiday Notice", "message": "College closed tomorrow."}],
            "kcet": [{"title": "KCET Result", "rank": "12345", "score": "88"}],
        }
    }

    with SessionLocal() as db:
        profile = WebsiteProfile(name=f"Contineo Portal {uuid4().hex}", url="https://contineo.test", success_check_json=json.dumps(sample))
        db.add(profile)
        db.commit()
        result = service.check_college_updates(db, "college")
        dashboard = service.college_dashboard(db)
        briefing = service.generate_daily_briefing(db, speak=False, notify=False)

        assert result["requires_profile"] is False
        assert dashboard["offline_ready"] is True
        assert dashboard["security"]["credentials_encrypted"] is True
        assert dashboard["attendance"][0]["percentage"] == 72.5
        assert dashboard["marks"][0]["subject"] == "DBMS"
        assert dashboard["results"][0]["exam_name"] == "Semester 4"
        assert dashboard["assignments"][0]["title"] == "DBMS Assignment"
        assert dashboard["fees"][0]["fee_type"] == "Exam Fee"
        assert dashboard["timetables"][0]["title"] == "DBMS Lab"
        assert dashboard["announcements"][0]["title"] == "Holiday Notice"
        assert dashboard["kcet"][0]["rank"] == "12345"
        assert dashboard["recommendations"][0]["type"] == "attendance_warning"
        assert "summary" in briefing["payload"]["college"]
        assert db.query(CollegeProfile).count() >= 1
        assert db.query(AttendanceRecord).count() >= 1
        assert db.query(InternalMark).count() >= 1
        assert db.query(ResultRecord).count() >= 1
        assert db.query(AssignmentRecord).count() >= 1
        assert db.query(FeeRecord).count() >= 1
        assert db.query(TimetableRecord).count() >= 1
        assert db.query(AnnouncementRecord).count() >= 1
        assert db.query(KCETRecord).count() >= 1


def test_download_scan_and_screenshot_history(tmp_path: Path):
    init_database()
    service = EvolutionService(SessionLocal)
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    (downloads / "notes.pdf").write_bytes(b"pdf")
    (downloads / "app.zip").write_bytes(b"zip")
    screenshot = tmp_path / "screen.png"
    screenshot.write_bytes(b"png")

    with SessionLocal() as db:
        scan = service.scan_downloads(db, str(downloads))
        organize = service.organize_downloads(db, str(downloads), dry_run=True)
        shot = service.record_screenshot(db, str(screenshot), "test", extracted_text="Traceback error in code")

        assert scan["count"] == 2
        assert any(item["category"] == "PDF" for item in scan["items"])
        assert len(organize["operations"]) == 2
        assert "error" in shot["tags"]
        assert shot["error_analysis"] is not None
        assert shot["document_summary"] is not None
        assert db.get(ScreenshotHistory, shot["id"]) is not None


def test_screenshot_assistant_analysis_search_actions_and_briefing(tmp_path: Path):
    init_database()
    service = EvolutionService(SessionLocal)
    screenshot = tmp_path / "error.png"
    screenshot.write_bytes(b"png")
    text = "Traceback (most recent call last):\n  File app.py, line 10\nTypeError: unsupported operand type"

    with SessionLocal() as db:
        shot = service.record_screenshot(db, str(screenshot), "test_hotkey", extracted_text=text)
        dashboard = service.screenshot_dashboard(db)
        search = service.search_screenshots(db, "find coding errors")
        action = service.record_screenshot_action(db, shot["id"], "save_notes", {"source": "test"})
        settings = service.update_screenshot_settings(db, {"cloud_ai_enabled": False, "require_cloud_approval": True})
        briefing = service.generate_daily_briefing(db, speak=False, notify=False)

        assert "error" in shot["tags"]
        assert shot["error_analysis"]["language"] == "Python"
        assert shot["document_summary"]["document_type"] == "code"
        assert dashboard["offline_ready"] is True
        assert dashboard["privacy"]["cloud_upload_requires_approval"] is True
        assert search["results"]
        assert action["action_type"] == "save_notes"
        assert settings["require_cloud_approval"] is True
        assert "screenshots" in briefing["payload"]
        assert db.query(OCRResult).count() >= 1
        assert db.query(ErrorAnalysis).count() >= 1
        assert db.query(DocumentSummary).count() >= 1
        assert db.query(ScreenshotAction).count() >= 1


def test_smart_download_manager_detects_duplicates_analytics_and_search(tmp_path: Path):
    init_database()
    service = EvolutionService(SessionLocal)
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    (downloads / "assignment.pdf").write_bytes(b"same-content")
    (downloads / "assignment-copy.pdf").write_bytes(b"same-content")
    (downloads / "video.mp4").write_bytes(b"x" * (2 * 1024 * 1024))
    (downloads / "app.exe").write_bytes(b"installer")

    with SessionLocal() as db:
        rule = service.create_download_rule(db, "Assignment PDFs", "assignment", "PDF", match_type="name_contains", priority=1)
        scan = service.scan_downloads(db, str(downloads), large_file_mb=1)
        dashboard = service.download_dashboard(db, str(downloads))
        pdfs = service.search_downloads(db, "find PDFs", 10)
        large = service.search_downloads(db, "find files larger than 1 MB", 10)

        assert rule["category"] == "PDF"
        assert scan["count"] == 4
        assert len(scan["duplicates"]) >= 1
        assert len(scan["large_files"]) == 1
        assert dashboard["statistics"]["duplicates"] >= 1
        assert dashboard["offline_ready"] is True
        assert pdfs["results"]
        assert large["results"][0]["file_name"] == "video.mp4"
        assert db.query(DuplicateFile).count() >= 1
        assert db.query(CleanupSuggestion).count() >= 2
        assert db.query(DownloadAnalytics).count() >= 1
        assert db.query(StorageReport).count() >= 1
        assert db.query(DownloadRule).count() >= 1


def test_smart_download_manager_organizes_files(tmp_path: Path):
    init_database()
    service = EvolutionService(SessionLocal)
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    source = downloads / "notes.pdf"
    source.write_bytes(b"pdf")

    with SessionLocal() as db:
        preview = service.organize_downloads(db, str(downloads), dry_run=True)
        result = service.organize_downloads(db, str(downloads), dry_run=False)

        destination = downloads / "PDFs" / "notes.pdf"
        assert preview["operations"][0]["destination"].endswith("PDFs\\notes.pdf") or preview["operations"][0]["destination"].endswith("PDFs/notes.pdf")
        assert result["operations"][0]["category"] == "PDF"
        assert destination.exists()
        assert not source.exists()


def test_download_monitor_starts_with_filesystem_events(tmp_path: Path):
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    monitor = DownloadMonitoringService()

    started = monitor.start([str(downloads)])
    stopped = monitor.stop()

    assert started["running"] is True
    assert str(downloads.resolve()) in started["watched_paths"]
    assert stopped["running"] is False


def test_project_guardian_snapshot_and_restore(tmp_path: Path):
    init_database()
    service = EvolutionService(SessionLocal)
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("print('ok')", encoding="utf-8")
    restore_path = tmp_path / "restored"

    with SessionLocal() as db:
        backup = service.project_guardian_snapshot(db, str(project), "git_push")
        restored = service.restore_project_backup(db, backup["id"], str(restore_path))

        assert Path(restored["backup_path"]).exists()
        assert (restore_path / "main.py").exists()
        assert db.get(ProjectBackup, backup["id"]).status == "restored"


def test_project_guardian_protection_git_health_and_dashboard(tmp_path: Path):
    init_database()
    service = EvolutionService(SessionLocal)
    project = tmp_path / "repo"
    project.mkdir()
    (project / "main.py").write_text("print('hello')", encoding="utf-8")
    (project / ".env").write_text("SECRET=1", encoding="utf-8")
    import subprocess

    subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "nexa@example.com"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.name", "Nexa"], cwd=project, check=True)
    subprocess.run(["git", "add", "main.py"], cwd=project, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=project, check=True, capture_output=True)
    (project / "main.py").write_text("print('changed')", encoding="utf-8")

    with SessionLocal() as db:
        protected = service.protect_project_operation(db, str(project), "git_push", "test push")
        dashboard = service.project_guardian_dashboard(db, str(project))
        health = service.evaluate_project_health(db, protected["project"]["id"])

        assert protected["protected"] is True
        assert protected["git_status"]["dirty"] is True
        assert protected["snapshot"]["snapshot"]["modified_files"]
        assert not (Path(protected["snapshot"]["backup_path"]) / ".env").exists()
        assert health["health_score"] < 100
        assert dashboard["projects"]
        assert dashboard["recovery_points"]
        assert db.query(ProjectSnapshot).count() >= 1
        assert db.query(RecoveryPoint).count() >= 1
        assert db.query(GitHistory).count() >= 1
        assert db.query(ProjectHealth).count() >= 1
        assert db.query(ProjectEvent).count() >= 1


def test_emergency_recovery_records_restores_and_briefs(tmp_path: Path):
    init_database()
    service = EvolutionService(SessionLocal)
    project = tmp_path / "recovery-project"
    project.mkdir()
    (project / "main.py").write_text("print('recover')", encoding="utf-8")

    with SessionLocal() as db:
        recorded = service.record_crash_report(
            db,
            "vscode_crash",
            source="test",
            application="VS Code",
            message="VS Code closed unexpectedly.",
            diagnostics={"open_files": ["main.py"], "workspace_path": str(project)},
            project_path=str(project),
        )
        captured = service.capture_recovery_session(db, "terminal_crash", [{"name": "Terminal", "workspace_path": str(project), "terminal": {"cwd": str(project)}}], str(project))
        restored = service.restore_recovery_session(db, captured["id"])
        dashboard = service.recovery_dashboard(db)
        briefing = service.generate_daily_briefing(db, notify=False, delivery_method="dashboard")

        assert recorded["crash_report"]["application"] == "VS Code"
        assert restored["status"] == "restored"
        assert dashboard["summary"]["crash_reports"] >= 1
        assert dashboard["capabilities"]["bsod_detection"] is True
        assert any(item["id"] == "recovery" for item in briefing["payload"]["sections"])
        assert db.query(CrashReport).count() >= 1
        assert db.query(RecoverySession).count() >= 2
        assert db.query(IncidentReport).count() >= 1
        assert db.query(RecoveredApplication).count() >= 1
        assert db.query(RecoveryEvent).count() >= 1
        assert db.query(RecoveryHistory).count() >= 1


def test_emergency_recovery_startup_heartbeat_detects_unclean_shutdown():
    init_database()
    service = EvolutionService(SessionLocal)
    with SessionLocal() as db:
        service._set_setting_value(db, "emergency_recovery.clean_shutdown", "false")
        service._set_setting_value(db, "emergency_recovery.last_seen", "2026-06-08T00:00:00")
        db.commit()

    result = service.recovery_startup_check()
    assert result["unclean_shutdown_detected"] is True
    with SessionLocal() as db:
        assert db.query(CrashReport).filter(CrashReport.crash_type == "unexpected_shutdown").count() >= 1
    service.recovery_clean_shutdown()


def test_copilot_and_mobile_summary_smoke():
    init_database()
    service = EvolutionService(SessionLocal)

    with SessionLocal() as db:
        suggestions = service.generate_copilot_suggestions(db)
        summary = service.mobile_summary(db)
        docs = service.mobile_api_docs()
        achievements = service.evaluate_achievements(db)

        assert isinstance(suggestions, list)
        assert "battery" in summary
        assert "notifications" in summary
        assert "copilot" in summary
        assert "quick_actions" in summary["copilot"]
        assert "authentication" in docs
        assert isinstance(achievements, list)


def test_mobile_companion_pairing_auth_sync_and_remote_approval():
    init_database()
    service = EvolutionService(SessionLocal)

    with SessionLocal() as db:
        pairing = service.mobile_pairing_start(db, "Pixel Test")
        claimed = service.mobile_pairing_claim(db, pairing["pairing_code"], pairing["pairing_token"], "Pixel Test", "android", f"fp-{uuid4()}")
        device = service.mobile_authenticate(db, f"Bearer {claimed['access_token']}")
        refreshed = service.mobile_refresh(db, claimed["refresh_token"])
        sync = service.mobile_sync_enqueue(db, device, "task", "upsert", {"title": "Mobile task"})
        approval = service.mobile_remote_command(db, device, "shutdown", {"reason": "test"})
        dashboard = service.mobile_gateway_dashboard(db)

        assert claimed["device"]["device_name"] == "Pixel Test"
        assert refreshed["access_token"]
        assert sync["status"] == "pending"
        assert approval["requires_approval"] is True
        assert dashboard["devices"]
        assert db.query(MobileDevice).count() >= 1
        assert db.query(DeviceToken).count() >= 1
        assert db.query(PairingCode).filter(PairingCode.status == "claimed").count() >= 1
        assert db.query(SyncQueue).count() >= 1
        assert db.query(MobileAuditLog).count() >= 1


def test_copilot_mode_context_dashboard_actions_and_settings():
    init_database()
    service = EvolutionService(SessionLocal)

    with SessionLocal() as db:
        settings = service.update_copilot_settings(db, {"privacy_mode": "local", "modules": {"battery": True, "health": True}})
        snapshot = service.create_context_snapshot(db)
        suggestions = service.generate_copilot_suggestions(db)
        dashboard = service.copilot_dashboard(db)
        target = dashboard["suggestions"][0] if dashboard["suggestions"] else service._create_suggestion(db, "test", "Test suggestion", "Test message", "low", {"type": "open", "target": "dashboard"})
        acted = service.execute_copilot_action(db, target["id"], "save")

        assert settings["privacy_mode"] == "local"
        assert snapshot["payload"]["privacy"]["local_processing"] is True
        assert isinstance(suggestions, list)
        assert dashboard["offline_ready"] is True
        assert "quick_actions" in dashboard
        assert acted["suggestion"]["status"] == "saved"
        assert db.query(ContextSnapshot).count() >= 1
        assert db.query(CopilotInsight).count() >= 1
        assert db.query(CopilotAction).count() >= 1
        assert db.query(CopilotHistory).count() >= 1
        assert db.query(CopilotAnalytics).count() >= 1
