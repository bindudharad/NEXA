from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

import requests
from sqlalchemy.orm import Session

from backend.agents.file_agent import FileAgent
from backend.agents.notifications import NotificationAgent
from backend.agents.system import SystemAgent
from backend.database.models import Notification, Task, VoiceInteraction, VoiceSetting
from backend.database.session import SessionLocal
from backend.services.power_monitor import power_monitor_service

logger = logging.getLogger("nexa.voice")


@dataclass
class VoiceAssistantSettings:
    enabled: bool = True
    wake_word_enabled: bool = True
    wake_phrases: list[str] = field(default_factory=lambda: ["nexa", "hey nexa", "hello nexa", "nexa activate", "nexa wake up"])
    activation_response: str = "Yes?"
    response_style: str = "concise"
    privacy_mode: str = "wake_word_only"
    cloud_ai_enabled: bool = True
    offline_only: bool = False
    push_to_talk: bool = False
    microphone_device: str = "default"
    sensitivity: float = 0.65
    noise_filtering: bool = True
    voice_enabled: bool = True
    voice_volume: int = 85
    voice_speed: int = 0
    voice_gender: str = "default"
    voice_language: str = "en-US"
    activation_notification_enabled: bool = True
    listen_timeout_seconds: int = 8


@dataclass
class VoiceAssistantStatus:
    service_running: bool = False
    listener_running: bool = False
    microphone_status: str = "offline"
    mode: str = "offline"
    online: bool = False
    muted: bool = False
    last_wake_time: str | None = None
    last_command: str | None = None
    last_response: str | None = None
    last_error: str | None = None
    startup_ready_seconds: float | None = None


class VoiceAssistantService:
    settings_key = "voice_assistant_settings"
    personality_modes = {"professional", "friendly", "jarvis", "minimal", "funny", "silent", "custom", "concise"}
    wake_responses = {"Yes?", "I'm listening.", "How can I help?", "Ready.", "What would you like me to do?", "Nexa activated."}

    def __init__(self, db_factory: Callable[[], Session] = SessionLocal) -> None:
        self.db_factory = db_factory
        self.status = VoiceAssistantStatus()
        self._lock = threading.Lock()
        self._listener_process: subprocess.Popen | None = None
        self._started_at: float | None = None
        self._api_base = os.environ.get("NEXA_API_BASE", "http://127.0.0.1:8010/api")

    def start(self) -> None:
        settings = self.get_settings()
        with self._lock:
            self.status.service_running = True
            self.status.online = self._internet_available()
            self.status.mode = self._mode(settings)
            self.status.microphone_status = "muted" if not settings.enabled or not settings.wake_word_enabled else "listening"
            self.status.startup_ready_seconds = round(time.perf_counter() - self._started_at, 2) if self._started_at else 0
        if settings.enabled and settings.wake_word_enabled and not settings.push_to_talk:
            self._start_windows_listener(settings)
        logger.info("Voice assistant service started mode=%s listener=%s", self.status.mode, self.status.listener_running)

    def mark_starting(self) -> None:
        self._started_at = time.perf_counter()

    def stop(self) -> None:
        self._stop_listener()
        with self._lock:
            self.status.service_running = False
            self.status.listener_running = False
            self.status.microphone_status = "offline"
        logger.info("Voice assistant service stopped")

    def pause(self) -> dict:
        self._stop_listener()
        with self._lock:
            self.status.muted = True
            self.status.microphone_status = "muted"
        self._record("listening_paused", "", "Listening paused.", "offline", "completed", {})
        return self.get_status()

    def resume(self) -> dict:
        settings = self.get_settings()
        with self._lock:
            self.status.muted = False
            self.status.microphone_status = "listening"
        if settings.enabled and settings.wake_word_enabled and not settings.push_to_talk:
            self._start_windows_listener(settings)
        self._record("listening_resumed", "", "Listening resumed.", self._mode(settings), "completed", {})
        return self.get_status()

    def get_settings(self, db: Session | None = None) -> VoiceAssistantSettings:
        owns_db = db is None
        db = db or self.db_factory()
        try:
            row = db.query(VoiceSetting).filter(VoiceSetting.key == self.settings_key).one_or_none()
            if not row:
                return VoiceAssistantSettings()
            return VoiceAssistantSettings(**{**asdict(VoiceAssistantSettings()), **json.loads(row.value_json)})
        finally:
            if owns_db:
                db.close()

    def update_settings(self, updates: dict, db: Session | None = None) -> dict:
        current = asdict(self.get_settings(db))
        current.update({key: value for key, value in updates.items() if value is not None})
        if isinstance(current.get("wake_phrases"), str):
            current["wake_phrases"] = [item.strip().lower() for item in current["wake_phrases"].split(",") if item.strip()]
        settings = VoiceAssistantSettings(**current)
        self._validate(settings)
        owns_db = db is None
        db = db or self.db_factory()
        try:
            value = json.dumps(asdict(settings), default=str)
            row = db.query(VoiceSetting).filter(VoiceSetting.key == self.settings_key).one_or_none()
            if row:
                row.value_json = value
                row.updated_at = datetime.utcnow()
            else:
                db.add(VoiceSetting(key=self.settings_key, value_json=value))
            db.commit()
        finally:
            if owns_db:
                db.close()
        if self.status.service_running:
            if settings.enabled and settings.wake_word_enabled and not settings.push_to_talk and not self.status.muted:
                self._start_windows_listener(settings)
            else:
                self._stop_listener()
        return asdict(settings)

    def get_status(self) -> dict:
        settings = self.get_settings()
        with self._lock:
            self.status.online = self._internet_available()
            self.status.mode = self._mode(settings)
            return asdict(self.status)

    def wake(self, phrase: str = "Nexa", source: str = "api") -> dict:
        settings = self.get_settings()
        if not settings.enabled or not settings.wake_word_enabled:
            return {"activated": False, "reason": "wake word disabled"}
        response = settings.activation_response
        now = datetime.utcnow().isoformat()
        with self._lock:
            self.status.last_wake_time = now
            self.status.microphone_status = "listening"
            self.status.last_response = response
            self.status.last_error = None
        if settings.activation_notification_enabled:
            with self.db_factory() as db:
                NotificationAgent(db).notify(
                    "Nexa Activated",
                    "Listening...",
                    alert_type="voice_wake",
                    module="voice_assistant",
                    severity="low",
                    priority="low",
                    category="info",
                    suggested_action="Speak a command or pause listening.",
                    action_buttons=["Pause Listening", "Dismiss"],
                    sound_path=str(Path("assets/sounds/nexa-info.wav").resolve()),
                    sound_enabled=True,
                    voice_message=response,
                    voice_enabled=False,
                    metadata={"phrase": phrase, "source": source},
                )
        if settings.voice_enabled:
            self.speak(response)
        self._record("wake_detected", phrase, response, self._mode(settings), "completed", {"source": source})
        logger.info("Wake word detected phrase=%s source=%s", phrase, source)
        return {"activated": True, "response": response, "mode": self._mode(settings), "timestamp": now}

    def process_command(self, command: str, source: str = "voice") -> dict:
        settings = self.get_settings()
        command = command.strip()
        if not command:
            raise ValueError("command is required")
        with self._lock:
            self.status.microphone_status = "processing"
            self.status.last_command = command
        mode = self._mode(settings)
        try:
            result = self._execute_local_command(command)
            response = result["response"]
            status = "completed"
        except Exception as exc:
            response = f"I could not complete that locally: {exc}"
            result = {"handled": False, "error": str(exc)}
            status = "failed"
            logger.exception("Voice command failed command=%s", command)
        if settings.voice_enabled:
            self.speak(response)
        with self._lock:
            self.status.microphone_status = "speaking" if settings.voice_enabled else "listening"
            self.status.last_response = response
            self.status.last_error = result.get("error")
        if settings.voice_enabled:
            threading.Timer(2.5, self._return_to_listening).start()
        self._record("voice_command", command, response, mode, status, {"source": source, "result": result})
        return {"command": command, "response": response, "mode": mode, "status": status, "result": result}

    def speak(self, text: str) -> None:
        settings = self.get_settings()
        if not settings.voice_enabled:
            return
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.Volume = {settings.voice_volume}; $s.Rate = {settings.voice_speed}; "
            f"$s.Speak({json.dumps(text)});"
        )
        try:
            subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False)
            logger.info("Voice response spoken text=%s", text)
        except Exception:
            logger.exception("Voice response failed")

    def interactions(self, limit: int = 100) -> list[dict]:
        with self.db_factory() as db:
            rows = db.query(VoiceInteraction).order_by(VoiceInteraction.created_at.desc()).limit(limit).all()
            return [
                {
                    "id": row.id,
                    "event_type": row.event_type,
                    "transcript": row.transcript,
                    "response_text": row.response_text,
                    "mode": row.mode,
                    "status": row.status,
                    "detail": json.loads(row.detail_json or "{}"),
                    "created_at": row.created_at.isoformat(),
                }
                for row in rows
            ]

    def _execute_local_command(self, command: str) -> dict:
        lower = command.lower().strip()
        system = SystemAgent()
        if re.search(r"\b(open|launch|start)\s+(chrome|google chrome)\b", lower):
            system.launch_app("chrome")
            return {"handled": True, "response": "Opening Chrome.", "action": "launch_chrome"}
        if re.search(r"\b(open|launch|start)\s+(vs code|vscode|code)\b", lower):
            system.launch_app("vs code")
            return {"handled": True, "response": "Opening VS Code.", "action": "launch_vscode"}
        if "open downloads" in lower:
            self._open_folder(Path.home() / "Downloads")
            return {"handled": True, "response": "Opening Downloads.", "action": "open_downloads"}
        if "show downloads" in lower or "find pdf" in lower or "find zip" in lower or "show large files" in lower or "show duplicates" in lower or "clean downloads" in lower or "organize downloads" in lower:
            from backend.services.evolution import evolution_service

            with self.db_factory() as db:
                if "organize downloads" in lower:
                    result = evolution_service.organize_downloads(db, dry_run=True)
                    return {"handled": True, "response": f"I found {len(result['operations'])} download organization action(s) to review.", "action": "downloads_organize_preview", "result": result}
                if "clean downloads" in lower:
                    suggestions = evolution_service.cleanup_suggestions(db, 20)
                    return {"handled": True, "response": f"You have {len(suggestions)} download cleanup suggestion(s).", "action": "downloads_cleanup", "suggestions": suggestions}
                if "show duplicates" in lower:
                    duplicates = evolution_service.list_duplicate_files(db, 20)
                    return {"handled": True, "response": f"Found {len(duplicates)} duplicate download(s).", "action": "downloads_duplicates", "duplicates": duplicates}
                if "show large files" in lower:
                    result = evolution_service.search_downloads(db, "large files", 20)
                    return {"handled": True, "response": result["summary"], "action": "downloads_large_files", "result": result}
                if "find pdf" in lower:
                    result = evolution_service.search_downloads(db, "find PDFs", 20)
                    return {"handled": True, "response": result["summary"], "action": "downloads_search", "result": result}
                if "find zip" in lower:
                    result = evolution_service.search_downloads(db, "find ZIP files", 20)
                    return {"handled": True, "response": result["summary"], "action": "downloads_search", "result": result}
                dashboard = evolution_service.download_dashboard(db)
            return {"handled": True, "response": f"Download Manager has {len(dashboard['recent'])} recent downloads and {len(dashboard['cleanup_suggestions'])} cleanup suggestion(s).", "action": "downloads_dashboard", "dashboard": dashboard}
        if "open documents" in lower:
            self._open_folder(Path.home() / "Documents")
            return {"handled": True, "response": "Opening Documents.", "action": "open_documents"}
        if "open task manager" in lower:
            subprocess.Popen(["taskmgr.exe"], shell=False)
            return {"handled": True, "response": "Opening Task Manager.", "action": "open_task_manager"}
        if "open settings" in lower:
            subprocess.Popen(["cmd", "/c", "start", "ms-settings:"], shell=False)
            return {"handled": True, "response": "Opening Windows Settings.", "action": "open_settings"}
        if "battery" in lower or "charging" in lower:
            status = power_monitor_service.get_status()
            percent = status.get("battery_percent")
            charging = status.get("is_charging")
            response = f"Battery is currently {percent if percent is not None else 'unknown'} percent"
            response += " and charging." if charging else " and running on battery power." if charging is False else "."
            return {"handled": True, "response": response, "action": "battery_status", "status": status}
        if "system health" in lower or "cpu" in lower or "memory" in lower:
            status = system.status()
            return {"handled": True, "response": f"CPU is {status['cpu_percent']} percent and memory is {status['ram_percent']} percent.", "action": "system_health", "status": status}
        if "show notifications" in lower or "view notifications" in lower:
            with self.db_factory() as db:
                count = db.query(Notification).filter(Notification.read.is_(False)).count()
            return {"handled": True, "response": f"You have {count} unread notifications.", "action": "notifications"}
        if "capture screen" in lower or "analyze screen" in lower or "explain this error" in lower or "read screenshot" in lower or "summarize document" in lower or "extract text" in lower or "save notes" in lower or "screenshot history" in lower:
            from backend.services.evolution import evolution_service

            with self.db_factory() as db:
                dashboard = evolution_service.screenshot_dashboard(db)
                latest = dashboard["recent"][0] if dashboard["recent"] else None
                if "capture screen" in lower or "analyze screen" in lower:
                    return {"handled": True, "response": "Press Control Shift A to capture the screen with Screenshot Assistant.", "action": "screenshot_capture_prompt", "dashboard": dashboard}
                if "screenshot history" in lower:
                    return {"handled": True, "response": f"You have {dashboard['statistics']['screenshots']} screenshot(s) in history.", "action": "screenshot_history", "dashboard": dashboard}
                if not latest:
                    return {"handled": True, "response": "No screenshots are available yet. Press Control Shift A to capture one.", "action": "screenshot_empty"}
                if "explain this error" in lower:
                    error = latest.get("error_analysis")
                    response = "No error was detected in the latest screenshot." if not error else f"{error['error_type']}: {error['probable_cause']}"
                    return {"handled": True, "response": response, "action": "screenshot_explain_error", "screenshot": latest}
                if "summarize document" in lower:
                    summary = latest.get("document_summary", {}).get("summary") or latest.get("analysis", "")
                    return {"handled": True, "response": summary, "action": "screenshot_summarize_document", "screenshot": latest}
                if "extract text" in lower or "read screenshot" in lower:
                    text = (latest.get("extracted_text") or "").strip()
                    response = text[:300] if text else "No readable text was extracted from the latest screenshot."
                    return {"handled": True, "response": response, "action": "screenshot_read_text", "screenshot": latest}
                if "save notes" in lower:
                    action = evolution_service.record_screenshot_action(db, latest["id"], "save_notes", {"source": "voice"})
                    return {"handled": True, "response": "Screenshot notes saved to your memory timeline.", "action": "screenshot_save_notes", "result": action}
        if "show timeline" in lower or "search timeline" in lower or "what did i do" in lower or "study history" in lower or "coding history" in lower or "completed goals" in lower or "weekly report" in lower:
            from backend.services.evolution import evolution_service

            with self.db_factory() as db:
                if "weekly report" in lower:
                    summary = evolution_service.timeline_summary(db, "week")
                    return {"handled": True, "response": summary["summary"], "action": "timeline_weekly_report", "summary": summary}
                if "show timeline" in lower:
                    dashboard = evolution_service.timeline_dashboard(db, "today")
                    return {"handled": True, "response": dashboard["summary"]["summary"], "action": "timeline_show", "dashboard": dashboard}
                search = evolution_service.natural_memory_search(db, command)
            return {"handled": True, "response": search["summary"], "action": "timeline_search", "result": search}
        if "backup project" in lower or "create snapshot" in lower or "show backups" in lower or "show git status" in lower or "project health" in lower or "recover last version" in lower or "restore project" in lower:
            from backend.services.evolution import evolution_service

            project_path = str(Path.cwd())
            with self.db_factory() as db:
                if "show backups" in lower:
                    dashboard = evolution_service.project_guardian_dashboard(db)
                    return {"handled": True, "response": f"You have {len(dashboard['backups'])} project backups available.", "action": "project_backups", "dashboard": dashboard}
                if "show git status" in lower:
                    status = evolution_service.git_status(project_path)
                    response = "This folder is not a Git repository." if not status.get("is_git_repo") else f"Branch {status.get('branch')}, {len(status.get('modified_files', [])) + len(status.get('untracked_files', []))} changed files."
                    return {"handled": True, "response": response, "action": "project_git_status", "status": status}
                if "project health" in lower:
                    dashboard = evolution_service.project_guardian_dashboard(db, project_path)
                    project = dashboard["projects"][0] if dashboard["projects"] else None
                    health = evolution_service.evaluate_project_health(db, project["id"]) if project else None
                    response = "No project registered." if not health else f"Project health is {round(health['health_score'])} percent with {health['risk_level']} risk."
                    return {"handled": True, "response": response, "action": "project_health", "health": health}
                if "recover last version" in lower or "restore project" in lower:
                    dashboard = evolution_service.project_guardian_dashboard(db)
                    latest = dashboard["recovery_points"][0] if dashboard["recovery_points"] else None
                    response = "No recovery points are available." if not latest else f"Latest recovery point is {latest['title']}. Open Project Guardian to choose a restore location."
                    return {"handled": True, "response": response, "action": "project_recovery", "recovery_point": latest}
                snapshot = evolution_service.project_guardian_snapshot(db, project_path, "voice_snapshot")
            return {"handled": True, "response": "Project recovery snapshot created.", "action": "project_snapshot", "snapshot": snapshot}
        if "create a study plan" in lower or "create study plan" in lower or "help me prepare for my exam" in lower or re.search(r"\bexam is in \d+ days\b", lower):
            from backend.services.evolution import evolution_service

            subject = self._extract_study_subject(lower)
            days_match = re.search(r"(?:exam is in|exam in|in)\s+(\d+)\s+days", lower)
            exam_date = (date.today() + timedelta(days=int(days_match.group(1)))).isoformat() if days_match else ""
            default_topics = ["Syllabus overview", "Weak topics", "Revision", "Practice test", "Final revision"]
            title = f"{subject} Exam Plan" if subject else "Exam Study Plan"
            with self.db_factory() as db:
                plan = evolution_service.create_study_plan(db, title, exam_date, default_topics, subject or "General", "high" if days_match else "medium")
            response = f"I created a study plan for {subject or 'your exam'}."
            if exam_date:
                response += f" Exam countdown is {plan.get('exam_countdown_days')} days."
            return {"handled": True, "response": response, "action": "study_plan_create", "plan": plan}
        if "show study progress" in lower or "study progress" in lower:
            from backend.services.evolution import evolution_service

            with self.db_factory() as db:
                dashboard = evolution_service.study_dashboard(db)
            response = f"Overall study readiness is {round(dashboard['readiness_score'])} percent across {len(dashboard['subjects'])} subjects."
            return {"handled": True, "response": response, "action": "study_progress", "dashboard": dashboard}
        if "exam countdown" in lower or "show countdown" in lower:
            from backend.services.evolution import evolution_service

            with self.db_factory() as db:
                dashboard = evolution_service.study_dashboard(db)
            next_exam = dashboard["exams"][0] if dashboard["exams"] else None
            response = "No upcoming exams are configured." if not next_exam else f"{next_exam['title']} is in {next_exam['days_remaining']} days. Readiness is {round(next_exam['readiness_score'])} percent."
            return {"handled": True, "response": response, "action": "exam_countdown", "exam": next_exam}
        if "show revision plan" in lower or "revision plan" in lower:
            from backend.services.evolution import evolution_service

            with self.db_factory() as db:
                dashboard = evolution_service.study_dashboard(db)
            response = f"You have {len(dashboard['revisions'])} revision items scheduled."
            return {"handled": True, "response": response, "action": "revision_plan", "revisions": dashboard["revisions"]}
        if "start study session" in lower:
            from backend.services.evolution import evolution_service

            subject = self._extract_study_subject(lower)
            minutes = self._extract_minutes(lower) if "hour" in lower or "minute" in lower else 25
            with self.db_factory() as db:
                session = evolution_service.record_study_session(db, subject_name=subject or "General", duration_minutes=minutes, session_type="study", notes="Voice command")
            return {"handled": True, "response": f"Recorded a {minutes} minute study session for {subject or 'General'}.", "action": "study_session", "session": session}
        if "mark chapter complete" in lower or "mark topic complete" in lower:
            from backend.services.evolution import evolution_service

            topic = re.sub(r".*mark (?:chapter|topic) complete", "", lower).strip(" .") or "Voice completed topic"
            with self.db_factory() as db:
                dashboard = evolution_service.study_dashboard(db)
                chapter = next((chapter for subject in dashboard["subjects"] for chapter in subject.get("chapters", []) if topic in chapter["title"].lower()), None)
                if not chapter:
                    subject = evolution_service.create_study_subject(db, "General")
                    chapter = evolution_service.add_study_chapter(db, subject["id"], topic.title())
                updated = evolution_service.update_study_chapter_progress(db, chapter["id"], 100, "completed", "Voice command")
            return {"handled": True, "response": f"Marked {updated['title']} complete.", "action": "study_chapter_complete", "chapter": updated}
        if "pause focus" in lower or "pause focus mode" in lower:
            from backend.services.evolution import evolution_service

            with self.db_factory() as db:
                session = evolution_service.pause_focus(db, reason="voice_command")
            return {"handled": True, "response": "Focus mode paused.", "action": "focus_pause", "session": session}
        if "resume focus" in lower or "resume focus mode" in lower:
            from backend.services.evolution import evolution_service

            with self.db_factory() as db:
                session = evolution_service.resume_focus(db)
            return {"handled": True, "response": "Focus mode resumed.", "action": "focus_resume", "session": session}
        if "extend session" in lower or "extend focus" in lower:
            from backend.services.evolution import evolution_service

            minutes = self._extract_minutes(lower)
            with self.db_factory() as db:
                session = evolution_service.extend_focus(db, minutes, reason="voice_command")
            return {"handled": True, "response": f"Focus session extended by {minutes} minutes.", "action": "focus_extend", "session": session}
        if "end focus" in lower or "stop focus" in lower:
            from backend.services.evolution import evolution_service

            with self.db_factory() as db:
                session = evolution_service.end_focus(db)
            return {"handled": True, "response": f"Focus mode ended with a productivity score of {round(session['productivity_score'])} percent.", "action": "focus_end", "session": session}
        if "show progress" in lower or "focus progress" in lower:
            from backend.services.evolution import evolution_service

            with self.db_factory() as db:
                status = evolution_service.focus_status(db)
            if not status.get("active"):
                return {"handled": True, "response": "Focus mode is not active.", "action": "focus_progress", "status": status}
            return {"handled": True, "response": f"Focus progress is {round(status['session_progress_percent'])} percent with {status['remaining_seconds'] // 60} minutes remaining.", "action": "focus_progress", "status": status}
        if "start study mode" in lower or "start coding mode" in lower or "start deep work mode" in lower or "start focus" in lower or "focus mode" in lower:
            from backend.services.evolution import evolution_service

            session_type = "study" if "study" in lower else "coding" if "coding" in lower else "work" if "deep work" in lower else "focus"
            minutes = self._extract_minutes(lower) if "hour" in lower or "minute" in lower else 25
            with self.db_factory() as db:
                session = evolution_service.start_focus(db, f"Voice {session_type.title()} Session", duration_minutes=minutes, session_type=session_type, current_goal=f"{session_type.title()} session")
            return {"handled": True, "response": f"{session_type.title()} focus mode started.", "action": "focus_start", "session": session}
        if "daily briefing" in lower or "morning briefing" in lower:
            from backend.services.evolution import evolution_service

            with self.db_factory() as db:
                briefing = evolution_service.generate_daily_briefing(db, speak=False, notify=True)
            return {"handled": True, "response": "Your daily briefing is ready.", "action": "daily_briefing", "briefing": briefing}
        if "college updates" in lower or "check results" in lower or "show attendance" in lower or "show timetable" in lower or "check fees" in lower:
            from backend.services.evolution import evolution_service

            with self.db_factory() as db:
                result = evolution_service.check_college_updates(db, "college")
            response = "College profile is required in Website Vault." if result.get("requires_profile") else "College updates are ready."
            return {"handled": True, "response": response, "action": "college_updates", "result": result}
        if "view tasks" in lower or "show tasks" in lower:
            with self.db_factory() as db:
                count = db.query(Task).count()
            return {"handled": True, "response": f"You have {count} tasks recorded.", "action": "tasks"}
        if "shutdown after" in lower:
            minutes = self._extract_minutes(lower)
            subprocess.Popen(["shutdown", "/s", "/t", str(minutes * 60)], shell=False)
            return {"handled": True, "response": f"Shutdown scheduled in {minutes} minutes.", "action": "schedule_shutdown"}
        if "restart" in lower and "pc" in lower:
            return {"handled": False, "response": "Restart requires approval from the task approval console.", "action": "restart_requires_approval"}
        return {"handled": False, "response": "I can handle local commands offline. Try opening Chrome, checking battery, showing notifications, or checking system health.", "action": "fallback"}

    def _start_windows_listener(self, settings: VoiceAssistantSettings) -> None:
        if os.name != "nt":
            with self._lock:
                self.status.listener_running = False
                self.status.microphone_status = "offline"
                self.status.last_error = "Wake listener is implemented with Windows System.Speech."
            return
        self._stop_listener()
        script_path = Path("backend/logs/nexa_voice_listener.ps1").resolve()
        phrases = json.dumps(settings.wake_phrases)
        api_base = self._api_base
        script = f"""
Add-Type -AssemblyName System.Speech
$phrases = ConvertFrom-Json @'
{phrases}
'@
$choices = New-Object System.Speech.Recognition.Choices
foreach ($phrase in $phrases) {{ [void]$choices.Add($phrase) }}
$builder = New-Object System.Speech.Recognition.GrammarBuilder
$builder.Culture = [System.Globalization.CultureInfo]::GetCultureInfo('{settings.voice_language}')
$builder.Append($choices)
$grammar = New-Object System.Speech.Recognition.Grammar($builder)
$recognizer = New-Object System.Speech.Recognition.SpeechRecognitionEngine($builder.Culture)
$recognizer.SetInputToDefaultAudioDevice()
$recognizer.LoadGrammar($grammar)
Register-ObjectEvent -InputObject $recognizer -EventName SpeechRecognized -Action {{
  if ($EventArgs.Result.Confidence -ge {settings.sensitivity}) {{
    $body = @{{ phrase = $EventArgs.Result.Text; source = 'windows_system_speech'; confidence = $EventArgs.Result.Confidence }} | ConvertTo-Json -Compress
    try {{ Invoke-RestMethod -Method Post -Uri '{api_base}/voice/wake' -ContentType 'application/json' -Body $body | Out-Null }} catch {{}}
  }}
}} | Out-Null
$recognizer.RecognizeAsync([System.Speech.Recognition.RecognizeMode]::Multiple)
while ($true) {{ Start-Sleep -Seconds 1 }}
"""
        script_path.write_text(script, encoding="utf-8")
        try:
            self._listener_process = subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False)
            with self._lock:
                self.status.listener_running = True
                self.status.microphone_status = "listening"
                self.status.last_error = None
            logger.info("Windows wake listener started pid=%s phrases=%s", self._listener_process.pid, settings.wake_phrases)
        except Exception as exc:
            with self._lock:
                self.status.listener_running = False
                self.status.microphone_status = "offline"
                self.status.last_error = str(exc)
            logger.exception("Windows wake listener failed")

    def _stop_listener(self) -> None:
        if self._listener_process and self._listener_process.poll() is None:
            self._listener_process.terminate()
            try:
                self._listener_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._listener_process.kill()
        self._listener_process = None
        with self._lock:
            self.status.listener_running = False

    def _record(self, event_type: str, transcript: str, response: str, mode: str, status: str, detail: dict) -> None:
        with self.db_factory() as db:
            db.add(VoiceInteraction(event_type=event_type, transcript=transcript, response_text=response, mode=mode, status=status, detail_json=json.dumps(detail, default=str)))
            db.commit()

    def _return_to_listening(self) -> None:
        with self._lock:
            if self.status.service_running and not self.status.muted:
                self.status.microphone_status = "listening"

    def _mode(self, settings: VoiceAssistantSettings) -> str:
        if settings.offline_only or not settings.cloud_ai_enabled:
            return "offline"
        return "online" if self._internet_available() else "offline"

    def _internet_available(self) -> bool:
        try:
            requests.get("https://api.groq.com", timeout=1.5)
            return True
        except Exception:
            return False

    def _open_folder(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer.exe", str(path)], shell=False)

    def _extract_minutes(self, text: str) -> int:
        hour_match = re.search(r"(\d+)\s*(hour|hours|hr|hrs)", text)
        if hour_match:
            return max(1, min(240, int(hour_match.group(1)) * 60))
        match = re.search(r"(\d+)\s*(minute|minutes|min)", text)
        if not match:
            return 10
        return max(1, min(180, int(match.group(1))))

    def _extract_study_subject(self, text: str) -> str:
        patterns = [
            r"study plan for ([a-z0-9 #+._-]+)",
            r"prepare for ([a-z0-9 #+._-]+)",
            r"study session for ([a-z0-9 #+._-]+)",
            r"my ([a-z0-9 #+._-]+) exam",
            r"([a-z0-9 #+._-]+) exam is in",
        ]
        stop_words = {"my", "the", "exam", "is", "in", "days", "for"}
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                raw = re.split(r"\b(in|for|with|tomorrow|today)\b", match.group(1))[0]
                cleaned = " ".join(part for part in raw.strip(" .").split() if part not in stop_words)
                return cleaned.upper() if len(cleaned) <= 5 else cleaned.title()
        return ""

    def _validate(self, settings: VoiceAssistantSettings) -> None:
        if not settings.wake_phrases:
            raise ValueError("At least one wake phrase is required")
        if settings.response_style not in self.personality_modes:
            raise ValueError(f"response_style must be one of {sorted(self.personality_modes)}")
        if settings.response_style != "custom" and settings.activation_response not in self.wake_responses:
            raise ValueError("activation_response must be a supported wake response unless response_style is custom")
        if not 0 <= settings.voice_volume <= 100:
            raise ValueError("voice_volume must be between 0 and 100")
        if not -10 <= settings.voice_speed <= 10:
            raise ValueError("voice_speed must be between -10 and 10")
        if not 0.1 <= settings.sensitivity <= 1.0:
            raise ValueError("sensitivity must be between 0.1 and 1.0")


voice_assistant_service = VoiceAssistantService()
