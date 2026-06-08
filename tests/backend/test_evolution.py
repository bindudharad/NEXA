from pathlib import Path

from backend.database.models import Achievement, ActivityHistory, Automation, BlockedSite, BriefingAnalytics, BriefingHistory, BriefingRecommendation, BriefingSchedule, CleanupSuggestion, CollegeUpdate, DailyBriefing, DocumentSummary, DownloadAnalytics, DownloadRule, DuplicateFile, ErrorAnalysis, FocusAnalytics, FocusGoal, FocusHistory, FocusSession, GitHistory, Goal, MemorySearch, OCRResult, ProjectBackup, ProjectEvent, ProjectHealth, ProjectSnapshot, RecoveryPoint, ScreenshotAction, ScreenshotHistory, StorageReport, StudyAnalytics, StudyChapter, StudyPlan, StudySession, StudySubject, TimelineEvent, TimelineInsight, TimelineSummary
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
        goal = service.create_goal(db, "Code 4 Hours", 4, "hours", "coding")
        updated = service.update_goal(db, goal["id"], 4)
        stats = service.goal_stats(db)

        assert updated["status"] == "achieved"
        assert stats["achieved"] >= 1
        assert db.query(Achievement).filter(Achievement.title.contains("Code 4 Hours")).count() >= 1
        assert db.get(Goal, goal["id"]) is not None


def test_automation_builder_creates_existing_automation_record():
    init_database()
    service = EvolutionService(SessionLocal)

    with SessionLocal() as db:
        result = service.build_automation(db, "When battery reaches 20% notify me")

        assert result["automation"]["condition"]["metric"] == "battery"
        assert db.get(Automation, result["automation"]["id"]) is not None


def test_automation_builder_marks_high_risk_for_approval():
    init_database()
    service = EvolutionService(SessionLocal)

    with SessionLocal() as db:
        result = service.build_automation(db, "When I say cleanup delete files after browser automation")

        assert result["approval"]["required"] is True


def test_college_companion_requests_profile_when_missing():
    init_database()
    service = EvolutionService(SessionLocal)

    with SessionLocal() as db:
        result = service.check_college_updates(db, "unlikely-college-profile-name")

        assert result["requires_profile"] is True
        assert db.query(CollegeUpdate).filter(CollegeUpdate.status == "requires_profile").count() >= 1


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
        assert "authentication" in docs
        assert isinstance(achievements, list)
