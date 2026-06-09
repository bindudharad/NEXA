from __future__ import annotations

import hashlib
import base64
import hmac
import json
import logging
import mimetypes
import re
import secrets
import shutil
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

import requests
from sqlalchemy.orm import Session

from backend.agents.notifications import NotificationAgent
from backend.agents.scheduler import SchedulerAgent
from backend.agents.system import SystemAgent
from backend.automation import AutomationEngine
from backend.database.models import (
    Achievement,
    AchievementHistory,
    ActivityHistory,
    ActivityLog,
    APIHealth,
    ApprovalStatus,
    AutomationHealth,
    AutomationHistory,
    BriefingAnalytics,
    BriefingHistory,
    BriefingRecommendation,
    BriefingSchedule,
    CodingSession,
    AnnouncementRecord,
    AssignmentRecord,
    AttendanceRecord,
    CollegeProfile,
    CollegeUpdate,
    CopilotSuggestion,
    ContextSnapshot,
    CopilotAction,
    CopilotAnalytics,
    CopilotHistory,
    CopilotInsight,
    CopilotWarning,
    CrashReport,
    DailyBriefing,
    CleanupSuggestion,
    DocumentSummary,
    DownloadAnalytics,
    DownloadHistory,
    DownloadMonitorEvent,
    DownloadRule,
    DuplicateFile,
    ErrorAnalysis,
    ExtractedText,
    BlockedApp,
    BlockedSite,
    FocusSession,
    FocusAnalytics,
    FocusGoal,
    FocusHistory,
    FeeRecord,
    Goal,
    GoalAnalytics,
    GoalHistory,
    GoalProgress,
    GoalReminder,
    HealthMetric,
    HealthScore,
    InternalMark,
    DeviceToken,
    Notification,
    NotificationQueue,
    ErrorLog,
    IncidentReport,
    KCETRecord,
    GitHistory,
    ProjectBackup,
    Project,
    ProjectEvent,
    ProjectHealth,
    ProjectSnapshot,
    RecoveredApplication,
    RecoveryEvent,
    RecoveryHistory,
    RecoveryPoint,
    RecoverySession,
    ProductivityScore,
    OptimizationEvent,
    OCRResult,
    ScreenshotAction,
    ScreenshotHistory,
    Setting,
    Streak,
    ResourceUsage,
    StorageReport,
    ResultRecord,
    TimetableRecord,
    ExamSchedule,
    RevisionPlan,
    StudyAchievement,
    StudyAnalytics,
    StudyChapter,
    StudyGoal,
    StudyPlan,
    StudyProgress,
    StudySession,
    StudySubject,
    Task,
    TaskApproval,
    TaskStatus,
    TimelineEvent,
    TimelineInsight,
    TimelineSummary,
    MemoryCategory,
    MemorySearch,
    MobileAuditLog,
    MobileDevice,
    MobilePermission,
    MobileSession,
    PairingCode,
    WebsiteProfile,
    WebsiteSession,
    SyncQueue,
)
from backend.core.config import get_settings
from backend.database.session import SessionLocal
from backend.services.power_monitor import power_monitor_service
from backend.services.resource_manager import resource_manager_service
from backend.services.voice_assistant import voice_assistant_service

logger = logging.getLogger("nexa.evolution")


def _loads(raw: str, fallback):
    try:
        return json.loads(raw or "")
    except Exception:
        return fallback


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


class EvolutionService:
    """Feature facade for Nexa Evolution Pack modules.

    The methods are intentionally event-driven/on-demand. Scheduled callers may
    invoke them at coarse intervals, but the service does not spawn monitoring
    loops by itself.
    """

    download_categories = {
        ".pdf": "PDF",
        ".epub": "Ebooks",
        ".mobi": "Ebooks",
        ".azw3": "Ebooks",
        ".zip": "Archives",
        ".7z": "Archives",
        ".rar": "Archives",
        ".tar": "Archives",
        ".gz": "Archives",
        ".png": "Images",
        ".jpg": "Images",
        ".jpeg": "Images",
        ".gif": "Images",
        ".webp": "Images",
        ".mp4": "Videos",
        ".mkv": "Videos",
        ".mov": "Videos",
        ".avi": "Videos",
        ".mp3": "Audio",
        ".wav": "Audio",
        ".m4a": "Audio",
        ".flac": "Audio",
        ".doc": "Documents",
        ".docx": "Documents",
        ".txt": "Documents",
        ".rtf": "Documents",
        ".xls": "Spreadsheets",
        ".xlsx": "Spreadsheets",
        ".csv": "Spreadsheets",
        ".ppt": "Presentations",
        ".pptx": "Presentations",
        ".exe": "Programs",
        ".msi": "Programs",
        ".bat": "Programs",
        ".py": "Code Files",
        ".ipynb": "Code Files",
        ".js": "Code Files",
        ".ts": "Code Files",
        ".tsx": "Code Files",
        ".jsx": "Code Files",
        ".java": "Code Files",
        ".cpp": "Code Files",
        ".c": "Code Files",
        ".cs": "Code Files",
        ".html": "Code Files",
        ".css": "Code Files",
        ".json": "Code Files",
    }
    incomplete_download_suffixes = {".crdownload", ".part", ".tmp", ".download"}

    def __init__(self, db_factory: Callable[[], Session] = SessionLocal) -> None:
        self.db_factory = db_factory

    def overview(self, db: Session) -> dict:
        return {
            "copilot": self.list_copilot_suggestions(db, limit=8),
            "copilot_dashboard": self.copilot_dashboard(db),
            "briefing": self.latest_briefing(db),
            "briefing_settings": self.get_briefing_settings(db),
            "focus": self.active_focus(db),
            "timeline": self.search_timeline(db, limit=8),
            "goals": self.list_goals(db),
            "goal_stats": self.goal_stats(db),
            "achievements": self.list_achievements(db),
            "self_health": self.self_health(db),
            "college": self.list_college_updates(db, limit=6),
        }

    def generate_copilot_suggestions(self, db: Session) -> list[dict]:
        settings = self.get_copilot_settings(db)
        if not settings["enabled"]:
            return []
        snapshot = self.create_context_snapshot(db)
        context = snapshot["payload"]
        candidates = self._copilot_candidates(db, context, settings)
        suggestions = [self._create_suggestion(db, item["type"], item["title"], item["message"], item["severity"], item["action"], item.get("module", "copilot_engine"), item.get("metadata", {})) for item in candidates]
        self._record_copilot_insights(db, context)
        self._record_copilot_analytics(db, len(suggestions))
        db.commit()
        for item in suggestions:
            if item["severity"] in {"high", "critical"}:
                NotificationAgent(db).notify(
                    item["title"],
                    item["message"],
                    alert_type="copilot_suggestion",
                    module="copilot_engine",
                    severity=item["severity"],
                    priority="high",
                    category="warning",
                    suggested_action="Open Copilot suggestions and choose an action.",
                    action_buttons=["Open Copilot", "Dismiss"],
                    metadata={"suggestion_id": item["id"]},
                )
        return suggestions

    def create_context_snapshot(self, db: Session) -> dict:
        context = self._copilot_context(db)
        latest_activity = context["activity"]["latest"]
        row = ContextSnapshot(
            current_app=latest_activity.get("app_name", ""),
            current_window=latest_activity.get("window_title", ""),
            activity_type=context["activity"]["type"],
            priority_context=context["priority_context"],
            payload_json=json.dumps(context, default=str),
            privacy_mode=self.get_copilot_settings(db)["privacy_mode"],
        )
        db.add(row)
        db.flush()
        return self._context_snapshot_dict(row)

    def copilot_dashboard(self, db: Session) -> dict:
        latest_snapshot = db.query(ContextSnapshot).order_by(ContextSnapshot.created_at.desc()).first()
        if not latest_snapshot:
            latest_snapshot = ContextSnapshot(activity_type="idle", payload_json=json.dumps(self._copilot_context(db), default=str))
            db.add(latest_snapshot)
            db.flush()
        suggestions = self.list_copilot_suggestions(db, 100)
        open_suggestions = [item for item in suggestions if item["status"] == "open"]
        warnings = [self._copilot_warning_dict(row) for row in db.query(CopilotWarning).order_by(CopilotWarning.created_at.desc()).limit(50).all()]
        insights = [self._copilot_insight_dict(row) for row in db.query(CopilotInsight).order_by(CopilotInsight.created_at.desc()).limit(20).all()]
        actions = [self._copilot_action_dict(row) for row in db.query(CopilotAction).order_by(CopilotAction.created_at.desc()).limit(50).all()]
        history = [self._copilot_history_dict(row) for row in db.query(CopilotHistory).order_by(CopilotHistory.created_at.desc()).limit(50).all()]
        analytics = [self._copilot_analytics_dict(row) for row in db.query(CopilotAnalytics).order_by(CopilotAnalytics.created_at.desc()).limit(14).all()]
        severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        top = sorted(open_suggestions, key=lambda item: severity_rank.get(item["severity"], 0), reverse=True)[:5]
        return {
            "context": self._context_snapshot_dict(latest_snapshot),
            "suggestions": open_suggestions,
            "warnings": warnings,
            "insights": insights,
            "quick_actions": self._copilot_quick_actions(open_suggestions),
            "actions": actions,
            "history": history,
            "analytics": analytics,
            "top_recommendations": top,
            "system_status": self._copilot_system_status(open_suggestions, warnings),
            "activity_summary": _loads(latest_snapshot.payload_json, {}).get("activity", {}),
            "orbital": {"glow": bool(top), "suggestion_count": len(open_suggestions), "critical_count": sum(1 for item in open_suggestions if item["severity"] == "critical")},
            "voice": {"commands": ["what should I do next", "any important updates", "show recommendations"]},
            "privacy": self.get_copilot_settings(db),
            "offline_ready": True,
        }

    def list_copilot_suggestions(self, db: Session, limit: int = 50) -> list[dict]:
        rows = db.query(CopilotSuggestion).order_by(CopilotSuggestion.created_at.desc()).limit(limit).all()
        return [self._suggestion_dict(row) for row in rows]

    def update_suggestion_status(self, db: Session, suggestion_id: int, status: str) -> dict:
        row = db.get(CopilotSuggestion, suggestion_id)
        if not row:
            raise ValueError("Suggestion not found")
        row.status = status
        row.acted_at = datetime.utcnow()
        db.add(CopilotHistory(event_type=f"suggestion_{status}", suggestion_id=row.id, title=row.title, detail_json=json.dumps({"status": status, "suggestion_type": row.suggestion_type}), status=status))
        db.commit()
        db.refresh(row)
        return self._suggestion_dict(row)

    def execute_copilot_action(self, db: Session, suggestion_id: int, action_type: str) -> dict:
        suggestion = db.get(CopilotSuggestion, suggestion_id)
        if not suggestion:
            raise ValueError("Suggestion not found")
        action = _loads(suggestion.action_json, {})
        result: dict = {"status": "recorded", "action": action}
        if action_type == "dismiss":
            suggestion.status = "dismissed"
            suggestion.acted_at = datetime.utcnow()
            result = {"status": "dismissed"}
        elif action_type == "save":
            suggestion.status = "saved"
            suggestion.acted_at = datetime.utcnow()
            result = {"status": "saved"}
        elif action_type == "act":
            target = action.get("target", action.get("type", "dashboard"))
            if target == "resources":
                result = self.optimize_self_health(db, "optimize")
            elif action.get("type") == "start_focus" or target == "focus":
                result = self.start_focus(db, "Copilot Focus Session", 25, 5, "focus")
            elif target == "battery":
                result = {"status": "open_panel", "target": "battery"}
            elif target == "project_backup" and action.get("project_path"):
                result = self.project_guardian_snapshot(db, action["project_path"], "copilot_recommendation")
            else:
                result = {"status": "open_panel", "target": target}
            suggestion.status = "acted"
            suggestion.acted_at = datetime.utcnow()
        row = CopilotAction(suggestion_id=suggestion.id, action_type=action_type, title=suggestion.title, payload_json=json.dumps(action, default=str), status=result.get("status", "completed"), result_json=json.dumps(result, default=str), executed_at=datetime.utcnow())
        db.add(row)
        db.add(CopilotHistory(event_type="action_executed", suggestion_id=suggestion.id, title=suggestion.title, detail_json=json.dumps({"action_type": action_type, "result": result}, default=str), status=result.get("status", "completed")))
        self.add_timeline_event(db, "copilot", "Copilot action executed", suggestion.title, "copilot_engine", metadata={"suggestion_id": suggestion.id, "action_type": action_type}, commit=False)
        db.commit()
        return {"suggestion": self._suggestion_dict(suggestion), "action": self._copilot_action_dict(row), "result": result}

    def get_copilot_settings(self, db: Session) -> dict:
        defaults = {"enabled": True, "notifications_enabled": True, "voice_enabled": True, "privacy_mode": "local", "modules": {"coding": True, "study": True, "college": True, "battery": True, "health": True, "project": True, "goals": True}, "quiet_minutes": 30, "learning_enabled": True}
        row = db.query(Setting).filter(Setting.key == "evolution.copilot_settings").one_or_none()
        return {**defaults, **_loads(row.value, {})} if row else defaults

    def update_copilot_settings(self, db: Session, updates: dict) -> dict:
        current = self.get_copilot_settings(db)
        if isinstance(updates.get("modules"), dict):
            current["modules"] = {**current["modules"], **updates.pop("modules")}
        current.update({key: value for key, value in updates.items() if value is not None})
        row = db.query(Setting).filter(Setting.key == "evolution.copilot_settings").one_or_none()
        if row:
            row.value = json.dumps(current, default=str)
            row.updated_at = datetime.utcnow()
        else:
            db.add(Setting(key="evolution.copilot_settings", value=json.dumps(current, default=str)))
        db.commit()
        return current

    def get_briefing_settings(self, db: Session) -> dict:
        defaults = {
            "enabled": True,
            "time": "08:00",
            "days": "all",
            "on_startup": False,
            "speak": False,
            "notify": True,
            "weather_location": "",
            "delivery_methods": ["dashboard", "notification"],
        }
        row = db.query(Setting).filter(Setting.key == "evolution.daily_briefing").one_or_none()
        if not row:
            return defaults
        return {**defaults, **_loads(row.value, {})}

    def update_briefing_settings(self, db: Session, updates: dict) -> dict:
        current = self.get_briefing_settings(db)
        current.update({key: value for key, value in updates.items() if value is not None})
        if isinstance(current.get("delivery_methods"), str):
            current["delivery_methods"] = [item.strip() for item in current["delivery_methods"].split(",") if item.strip()]
        row = db.query(Setting).filter(Setting.key == "evolution.daily_briefing").one_or_none()
        if row:
            row.value = json.dumps(current, default=str)
            row.updated_at = datetime.utcnow()
        else:
            db.add(Setting(key="evolution.daily_briefing", value=json.dumps(current, default=str)))
        schedule = self._get_or_create_briefing_schedule(db)
        schedule.enabled = bool(current["enabled"])
        schedule.schedule_time = current["time"]
        schedule.days = current["days"]
        schedule.on_startup = bool(current["on_startup"])
        schedule.speak = bool(current["speak"])
        schedule.notify = bool(current["notify"])
        schedule.delivery_methods_json = json.dumps(current["delivery_methods"], default=str)
        schedule.updated_at = datetime.utcnow()
        db.commit()
        return current

    def ensure_daily_briefing_schedule(self, scheduler: SchedulerAgent) -> dict:
        with self.db_factory() as db:
            settings = self.get_briefing_settings(db)
            schedule = self._get_or_create_briefing_schedule(db)
            if not settings["enabled"]:
                schedule.next_run_hint = "disabled"
                db.commit()
                return {"scheduled": False, "reason": "disabled"}
            hour, minute = self._parse_time(settings["time"])

            def run_briefing() -> None:
                with self.db_factory() as run_db:
                    if self._schedule_allows_today(self.get_briefing_settings(run_db)):
                        self.generate_daily_briefing(run_db, speak=bool(settings.get("speak")), notify=bool(settings.get("notify")), delivery_method="scheduled")

            result = scheduler.schedule_callable("nexa-daily-briefing", run_briefing, hour, minute)
            schedule.next_run_hint = str(result.get("next_run_time") or "")
            if settings.get("on_startup") and self._schedule_allows_today(settings):
                today = date.today().isoformat()
                existing = db.query(BriefingHistory).filter(BriefingHistory.briefing_date == today, BriefingHistory.delivery_method == "startup").first()
                if not existing:
                    self.generate_daily_briefing(db, speak=bool(settings.get("speak")), notify=bool(settings.get("notify")), delivery_method="startup")
            db.commit()
            return {"scheduled": True, **result}

    def generate_daily_briefing(self, db: Session, speak: bool = False, notify: bool = True, delivery_method: str = "manual") -> dict:
        started = datetime.utcnow()
        today = date.today().isoformat()
        existing = db.query(DailyBriefing).filter(DailyBriefing.briefing_date == today).order_by(DailyBriefing.created_at.desc()).first()
        settings = self.get_briefing_settings(db)
        context = self._briefing_context(db, settings)
        sections = self._prioritize_briefing_sections(context)
        recommendations = self._secretary_recommendations(context)
        insights = self._briefing_insights(db, context)
        summary = self._briefing_summary(context, sections, recommendations)
        voice_text = self._voice_briefing_text(context, recommendations)
        voice_text = voice_assistant_service.personality_response("daily_briefing", voice_text, context)
        payload = {
            "current_time": datetime.now().strftime("%I:%M %p"),
            "sections": sections,
            "recommendations": recommendations,
            "insights": insights,
            "voice_text": voice_text,
            "delivery_methods": settings["delivery_methods"],
            **context,
        }
        notification_id = existing.notification_id if existing else None
        if notify:
            notification = NotificationAgent(db).notify(
                "Nexa Daily Briefing",
                summary,
                alert_type="daily_briefing",
                module="daily_briefing",
                severity="low",
                priority="medium",
                category="info",
                suggested_action="Open the briefing dashboard for secretary recommendations and today's priorities.",
                action_buttons=["Open Briefing", "Mark Reviewed", "Dismiss"],
                voice_message=voice_text,
                voice_enabled=speak,
                metadata=payload,
            )
            notification_id = notification.get("id")
        if speak:
            voice_assistant_service.speak(voice_text)
        row = existing or DailyBriefing(briefing_date=today)
        row.title = "Good Morning"
        row.summary = summary
        row.payload_json = json.dumps(payload, default=str)
        row.spoken = speak
        row.notification_id = notification_id
        db.add(row)
        db.flush()
        self._store_briefing_records(db, row, payload, recommendations, context, delivery_method, started)
        schedule = self._get_or_create_briefing_schedule(db)
        schedule.last_run_at = datetime.utcnow()
        self.add_timeline_event(db, "briefing", "Daily briefing generated", summary, "daily_briefing", commit=False)
        db.commit()
        db.refresh(row)
        return self._briefing_dict(row)

    def latest_briefing(self, db: Session) -> dict | None:
        row = db.query(DailyBriefing).order_by(DailyBriefing.created_at.desc()).first()
        return self._briefing_dict(row) if row else None

    def briefing_history(self, db: Session, limit: int = 30) -> list[dict]:
        rows = db.query(BriefingHistory).order_by(BriefingHistory.created_at.desc()).limit(limit).all()
        return [self._briefing_history_dict(row) for row in rows]

    def briefing_recommendations(self, db: Session, status: str | None = None, limit: int = 50) -> list[dict]:
        query = db.query(BriefingRecommendation)
        if status:
            query = query.filter(BriefingRecommendation.status == status)
        return [self._briefing_recommendation_dict(row) for row in query.order_by(BriefingRecommendation.created_at.desc()).limit(limit).all()]

    def briefing_analytics(self, db: Session, limit: int = 30) -> list[dict]:
        rows = db.query(BriefingAnalytics).order_by(BriefingAnalytics.created_at.desc()).limit(limit).all()
        return [self._briefing_analytics_dict(row) for row in rows]

    def start_focus(
        self,
        db: Session,
        title: str = "Focus Session",
        duration_minutes: int = 25,
        break_minutes: int = 5,
        mode: str = "pomodoro",
        session_type: str = "focus",
        subject: str = "",
        chapter: str = "",
        topic: str = "",
        current_goal: str = "",
        pomodoro_preset: str = "25/5",
        blocked_websites: list[str] | None = None,
        blocked_apps: list[str] | None = None,
        mute_notifications: bool = True,
        allow_critical_notifications: bool = True,
        long_break_minutes: int = 15,
        cycles_before_long_break: int = 4,
    ) -> dict:
        existing = db.query(FocusSession).filter(FocusSession.status == "active").one_or_none()
        if existing:
            return self._focus_dict(existing)
        blocked_websites = blocked_websites or self._default_blocked_sites()
        blocked_apps = blocked_apps or []
        detail = {
            "planned_minutes": duration_minutes,
            "session_type": session_type,
            "subject": subject,
            "chapter": chapter,
            "topic": topic,
            "current_goal": current_goal,
            "pomodoro_preset": pomodoro_preset,
            "pomodoro": {
                "focus_minutes": duration_minutes,
                "break_minutes": break_minutes,
                "long_break_minutes": long_break_minutes,
                "cycles_before_long_break": cycles_before_long_break,
                "cycle": 1,
                "state": "focus",
                "paused_seconds": 0,
                "last_paused_at": None,
            },
            "blocked_websites": blocked_websites,
            "blocked_apps": blocked_apps,
            "notification_muting": mute_notifications,
            "allowed_notifications": ["battery", "critical", "emergency"] if allow_critical_notifications else [],
            "study_tracking": True,
            "coding_tracking": True,
            "break_reminders": ["Drink some water.", "Take a quick stretch."],
            "distraction_events": [],
            "extensions": [],
        }
        row = FocusSession(title=title, mode=mode, break_seconds=break_minutes * 60, detail_json=json.dumps(detail))
        db.add(row)
        db.flush()
        for domain in blocked_websites:
            self._ensure_blocked_site(db, domain)
        for app_name in blocked_apps:
            self._ensure_blocked_app(db, app_name)
        if current_goal:
            db.add(FocusGoal(session_id=row.id, title=current_goal, goal_type=session_type, target_minutes=duration_minutes))
        self._focus_history(db, row.id, "started", detail)
        db.commit()
        db.refresh(row)
        NotificationAgent(db).notify(
            "Nexa Focus Mode",
            f"{title} started for {duration_minutes} minutes. Distractions are muted and blockers are active.",
            alert_type="focus_mode",
            module="focus_mode",
            severity="low",
            priority="medium",
            category="info",
            suggested_action="Stay in the session or end focus mode from the dashboard.",
            action_buttons=["End Focus", "Dismiss"],
        )
        self.add_timeline_event(db, "focus", "Focus mode started", title, "focus_mode")
        return self._focus_dict(row)

    def focus_status(self, db: Session) -> dict:
        row = db.query(FocusSession).filter(FocusSession.status.in_(["active", "paused"])).order_by(FocusSession.started_at.desc()).first()
        if not row:
            return {"active": False}
        active = self._focus_dict(row)
        detail = active["detail"]
        elapsed = int((datetime.utcnow() - datetime.fromisoformat(active["started_at"])).total_seconds()) - int(detail.get("pomodoro", {}).get("paused_seconds", 0))
        if detail.get("pomodoro", {}).get("last_paused_at"):
            elapsed -= int((datetime.utcnow() - datetime.fromisoformat(detail["pomodoro"]["last_paused_at"])).total_seconds())
        elapsed = max(0, elapsed)
        planned = int(active["detail"].get("planned_minutes", 25)) * 60
        progress = round(min(100, elapsed / max(planned, 1) * 100), 2)
        return {**active, "active": row.status == "active", "paused": row.status == "paused", "elapsed_seconds": elapsed, "remaining_seconds": max(0, planned - elapsed), "session_progress_percent": progress, "blocker_active": True, "notification_control": detail.get("notification_muting", True)}

    def pause_focus(self, db: Session, session_id: int | None = None, reason: str = "") -> dict:
        row = self._active_focus_row(db, session_id)
        detail = _loads(row.detail_json, {})
        detail.setdefault("pomodoro", {})["state"] = "paused"
        detail["pomodoro"]["last_paused_at"] = datetime.utcnow().isoformat()
        row.status = "paused"
        row.detail_json = json.dumps(detail, default=str)
        self._focus_history(db, row.id, "paused", {"reason": reason})
        db.commit()
        db.refresh(row)
        return self._focus_dict(row)

    def resume_focus(self, db: Session, session_id: int | None = None) -> dict:
        row = self._active_focus_row(db, session_id, include_paused=True)
        detail = _loads(row.detail_json, {})
        pomodoro = detail.setdefault("pomodoro", {})
        paused_at = pomodoro.get("last_paused_at")
        if paused_at:
            pomodoro["paused_seconds"] = int(pomodoro.get("paused_seconds", 0)) + max(0, int((datetime.utcnow() - datetime.fromisoformat(paused_at)).total_seconds()))
        pomodoro["last_paused_at"] = None
        pomodoro["state"] = "focus"
        row.status = "active"
        row.detail_json = json.dumps(detail, default=str)
        self._focus_history(db, row.id, "resumed", {})
        db.commit()
        db.refresh(row)
        return self._focus_dict(row)

    def extend_focus(self, db: Session, minutes: int, session_id: int | None = None, reason: str = "") -> dict:
        row = self._active_focus_row(db, session_id, include_paused=True)
        detail = _loads(row.detail_json, {})
        detail["planned_minutes"] = int(detail.get("planned_minutes", 25)) + minutes
        detail.setdefault("pomodoro", {})["focus_minutes"] = detail["planned_minutes"]
        detail.setdefault("extensions", []).append({"minutes": minutes, "reason": reason, "at": datetime.utcnow().isoformat()})
        row.detail_json = json.dumps(detail, default=str)
        self._focus_history(db, row.id, "extended", {"minutes": minutes, "reason": reason})
        db.commit()
        db.refresh(row)
        return self._focus_dict(row)

    def start_focus_break(self, db: Session, minutes: int = 5, session_id: int | None = None) -> dict:
        row = self._active_focus_row(db, session_id, include_paused=True)
        detail = _loads(row.detail_json, {})
        pomodoro = detail.setdefault("pomodoro", {})
        pomodoro["state"] = "break"
        pomodoro["break_started_at"] = datetime.utcnow().isoformat()
        pomodoro["current_break_minutes"] = minutes
        row.detail_json = json.dumps(detail, default=str)
        self._focus_history(db, row.id, "break_started", {"minutes": minutes})
        db.commit()
        db.refresh(row)
        NotificationAgent(db).notify(
            "Nexa Focus Break",
            f"You've focused for a while. Time for a {minutes} minute break.",
            alert_type="focus_break",
            module="focus_mode",
            severity="low",
            priority="medium",
            category="reminder",
            suggested_action="Take a short break, stretch, then resume focus.",
            action_buttons=["Resume Focus", "Dismiss"],
            voice_message="Time for a short break.",
            voice_enabled=False,
        )
        return self._focus_dict(row)

    def end_focus(self, db: Session, session_id: int | None = None, tasks_completed: int = 0, distraction_count: int = 0, goal_completion_percent: float = 0) -> dict:
        row = self._active_focus_row(db, session_id, include_paused=True)
        now = datetime.utcnow()
        detail = _loads(row.detail_json, {})
        paused_seconds = int(detail.get("pomodoro", {}).get("paused_seconds", 0))
        row.status = "completed"
        row.ended_at = now
        row.duration_seconds = max(0, int((now - row.started_at).total_seconds()) - paused_seconds)
        row.tasks_completed = tasks_completed
        row.distraction_count = distraction_count
        if goal_completion_percent:
            goals = db.query(FocusGoal).filter(FocusGoal.session_id == row.id).all()
            for goal in goals:
                goal.completion_percent = max(goal.completion_percent, goal_completion_percent)
                goal.completed_minutes = max(goal.completed_minutes, round(goal.target_minutes * goal.completion_percent / 100))
                goal.status = "completed" if goal.completion_percent >= 100 else goal.status
        goal_completion = max(goal_completion_percent, self._focus_goal_completion(db, row.id))
        row.productivity_score = self._focus_productivity_score(row.duration_seconds, row.break_seconds, distraction_count, goal_completion, tasks_completed)
        recommendations = self._focus_recommendations(row.productivity_score, distraction_count, goal_completion)
        db.add(
            FocusAnalytics(
                session_id=row.id,
                focus_seconds=row.duration_seconds,
                break_seconds=row.break_seconds,
                distraction_count=distraction_count,
                tasks_completed=tasks_completed,
                goal_completion_percent=goal_completion,
                productivity_score=row.productivity_score,
                recommendations_json=json.dumps(recommendations, default=str),
            )
        )
        db.add(ProductivityScore(session_id=row.id, score=row.productivity_score, factors_json=json.dumps({"focus_seconds": row.duration_seconds, "break_seconds": row.break_seconds, "distractions": distraction_count, "goal_completion": goal_completion, "tasks_completed": tasks_completed}, default=str), recommendations_json=json.dumps(recommendations, default=str)))
        self._focus_history(db, row.id, "completed", {"tasks_completed": tasks_completed, "distraction_count": distraction_count, "productivity_score": row.productivity_score})
        db.commit()
        db.refresh(row)
        self.add_timeline_event(db, "focus", "Focus mode completed", row.title, "focus_mode", row.duration_seconds)
        if detail.get("session_type") == "study":
            self.record_study_session(
                db,
                subject_name=detail.get("subject", ""),
                chapter_title=detail.get("chapter", ""),
                topic=detail.get("topic", detail.get("current_goal", "")),
                duration_minutes=max(1, round(row.duration_seconds / 60)),
                session_type="study",
                notes=f"Recorded from Focus Mode: {row.title}",
                focus_session_id=row.id,
            )
        NotificationAgent(db).notify(
            "Nexa Focus Complete",
            f"{row.title} completed with a productivity score of {round(row.productivity_score)}%.",
            alert_type="focus_complete",
            module="focus_mode",
            severity="low",
            priority="medium",
            category="success",
            suggested_action="Review your focus history and recommendations.",
            action_buttons=["Open Focus History", "Dismiss"],
            metadata={"session_id": row.id, "productivity_score": row.productivity_score},
        )
        return self._focus_dict(row)

    def active_focus(self, db: Session) -> dict | None:
        row = db.query(FocusSession).filter(FocusSession.status == "active").one_or_none()
        return self._focus_dict(row) if row else None

    def list_focus_sessions(self, db: Session, limit: int = 50) -> list[dict]:
        return [self._focus_dict(row) for row in db.query(FocusSession).order_by(FocusSession.started_at.desc()).limit(limit).all()]

    def focus_dashboard(self, db: Session) -> dict:
        active = self.focus_status(db)
        recent = self.list_focus_sessions(db, limit=20)
        analytics = [self._focus_analytics_dict(row) for row in db.query(FocusAnalytics).order_by(FocusAnalytics.created_at.desc()).limit(20).all()]
        goals = [self._focus_goal_dict(row) for row in db.query(FocusGoal).order_by(FocusGoal.created_at.desc()).limit(20).all()]
        history = [self._focus_history_dict(row) for row in db.query(FocusHistory).order_by(FocusHistory.created_at.desc()).limit(50).all()]
        return {"active": active, "recent_sessions": recent, "analytics": analytics, "goals": goals, "history": history, "blocked_sites": self.blocked_sites(db), "blocked_apps": self.blocked_apps(db)}

    def blocked_sites(self, db: Session) -> list[dict]:
        return [self._blocked_site_dict(row) for row in db.query(BlockedSite).order_by(BlockedSite.domain.asc()).all()]

    def blocked_apps(self, db: Session) -> list[dict]:
        return [self._blocked_app_dict(row) for row in db.query(BlockedApp).order_by(BlockedApp.app_name.asc()).all()]

    def check_focus_distraction(self, db: Session, url: str | None = None, app_name: str | None = None) -> dict:
        active = db.query(FocusSession).filter(FocusSession.status == "active").one_or_none()
        if not active:
            return {"blocked": False, "reason": "Focus Mode inactive"}
        detail = _loads(active.detail_json, {})
        blocked = False
        target = url or app_name or ""
        if url:
            blocked = any(domain.lower() in url.lower() for domain in detail.get("blocked_websites", []))
        if app_name:
            blocked = blocked or any(app.lower() in app_name.lower() for app in detail.get("blocked_apps", []))
        if blocked:
            event = {"target": target, "at": datetime.utcnow().isoformat(), "message": "Focus Mode Active. This distraction is blocked."}
            detail.setdefault("distraction_events", []).append(event)
            active.distraction_count += 1
            active.detail_json = json.dumps(detail, default=str)
            self._focus_history(db, active.id, "distraction_blocked", event)
            db.commit()
            NotificationAgent(db).notify(
                "Nexa Focus Blocked Distraction",
                f"Focus Mode blocked {target}.",
                alert_type="focus_distraction",
                module="focus_mode",
                severity="low",
                priority="low",
                category="warning",
                suggested_action="Return to your current focus goal.",
                action_buttons=["Show Focus", "Dismiss"],
                metadata={"session_id": active.id, "target": target},
            )
            return {"blocked": True, "title": "Focus Mode Active", "message": "This site or app is blocked.", "target": target, "session": self._focus_dict(active)}
        return {"blocked": False, "reason": "Not in blocked distractions", "target": target}

    def create_focus_goal(self, db: Session, title: str, goal_type: str = "custom", target_minutes: int = 25, session_id: int | None = None) -> dict:
        row = FocusGoal(session_id=session_id, title=title, goal_type=goal_type, target_minutes=target_minutes)
        db.add(row)
        db.commit()
        db.refresh(row)
        return self._focus_goal_dict(row)

    def update_focus_goal(self, db: Session, goal_id: int, completed_minutes: int, status: str | None = None) -> dict:
        row = db.get(FocusGoal, goal_id)
        if not row:
            raise ValueError("Focus goal not found")
        row.completed_minutes = completed_minutes
        row.completion_percent = round(min(100, completed_minutes / max(row.target_minutes, 1) * 100), 2)
        row.status = status or ("completed" if row.completion_percent >= 100 else row.status)
        row.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        if row.status == "completed":
            NotificationAgent(db).notify(
                "Nexa Focus Goal Achieved",
                f"{row.title} completed.",
                alert_type="focus_goal",
                module="focus_mode",
                severity="low",
                priority="medium",
                category="success",
                suggested_action="Review focus analytics or start the next goal.",
                action_buttons=["Open Focus", "Dismiss"],
                metadata={"goal_id": row.id},
            )
        return self._focus_goal_dict(row)

    def create_study_subject(self, db: Session, name: str, priority: str = "medium", difficulty: str = "medium", exam_date: str = "", target_score: float = 90) -> dict:
        row = db.query(StudySubject).filter(StudySubject.name.ilike(name)).order_by(StudySubject.updated_at.desc()).first()
        if row:
            row.priority = priority or row.priority
            row.difficulty = difficulty or row.difficulty
            row.exam_date = exam_date or row.exam_date
            row.target_score = target_score or row.target_score
            row.updated_at = datetime.utcnow()
        else:
            row = StudySubject(name=name, priority=priority, difficulty=difficulty, exam_date=exam_date, target_score=target_score)
            db.add(row)
        db.commit()
        db.refresh(row)
        if exam_date and not db.query(ExamSchedule).filter(ExamSchedule.subject_id == row.id, ExamSchedule.exam_date == exam_date).one_or_none():
            db.add(ExamSchedule(subject_id=row.id, title=f"{row.name} Exam", exam_date=exam_date, target_score=target_score))
            db.commit()
        self.add_timeline_event(db, "study", "Study subject configured", row.name, "study_assistant")
        return self._study_subject_dict(row, db)

    def add_study_chapter(self, db: Session, subject_id: int, title: str, unit: str = "", topics: list[str] | None = None, priority: str = "medium", difficulty: str = "medium") -> dict:
        subject = db.get(StudySubject, subject_id)
        if not subject:
            raise ValueError("Study subject not found")
        row = StudyChapter(subject_id=subject_id, title=title, unit=unit, topics_json=json.dumps(topics or []), priority=priority, difficulty=difficulty)
        db.add(row)
        db.commit()
        db.refresh(row)
        self._recalculate_subject(db, subject_id)
        self._ensure_revision_plan(db, subject_id, row.id, title)
        self.add_timeline_event(db, "study", "Study chapter added", f"{subject.name}: {title}", "study_assistant")
        return self._study_chapter_dict(row)

    def create_study_plan(
        self,
        db: Session,
        title: str,
        exam_date: str = "",
        topics: list[str] | None = None,
        subject_name: str = "",
        priority: str = "medium",
        difficulty: str = "medium",
        target_score: float = 90,
        availability_minutes_per_day: int = 120,
    ) -> dict:
        topics = topics or []
        subject_label = subject_name or title.replace("Exam Plan", "").replace("Plan", "").strip() or title
        subject = self.create_study_subject(db, subject_label, priority, difficulty, exam_date, target_score)
        subject_id = subject["id"]
        days_available = self._days_until(exam_date) if exam_date else max(len(topics), 1)
        daily_plan = self._build_daily_study_plan(topics, days_available, availability_minutes_per_day)
        row = StudyPlan(title=title, exam_date=exam_date, syllabus_json=json.dumps(topics), daily_plan_json=json.dumps(daily_plan))
        db.add(row)
        db.commit()
        db.refresh(row)
        for index, topic in enumerate(topics, start=1):
            db.add(StudyProgress(plan_id=row.id, topic=topic))
            chapter = db.query(StudyChapter).filter(StudyChapter.subject_id == subject_id, StudyChapter.title == topic).order_by(StudyChapter.updated_at.desc()).first()
            if not chapter:
                chapter = StudyChapter(subject_id=subject_id, unit=f"Unit {index}", title=topic, topics_json=json.dumps([topic]), priority=priority, difficulty=difficulty)
                db.add(chapter)
                db.flush()
            self._ensure_revision_plan(db, subject_id, chapter.id, topic, exam_date)
        if exam_date and not db.query(ExamSchedule).filter(ExamSchedule.subject_id == subject_id, ExamSchedule.exam_date == exam_date).one_or_none():
            db.add(ExamSchedule(subject_id=subject_id, title=f"{subject_label} Exam", exam_date=exam_date, target_score=target_score))
        db.commit()
        self._recalculate_subject(db, subject_id)
        self.add_timeline_event(db, "study", "Study plan created", title, "study_assistant")
        self.schedule_study_reminder(db, row.id, topics[0] if topics else title)
        return {**self._study_plan_dict(row, db), "subject": self._study_subject_dict(db.get(StudySubject, subject_id), db)}

    def schedule_study_reminder(self, db: Session, plan_id: int, topic: str | None = None) -> dict:
        plan = db.get(StudyPlan, plan_id)
        if not plan:
            raise ValueError("Study plan not found")
        message = f"Study reminder: {topic or plan.title}"
        notification = NotificationAgent(db).notify(
            "Nexa Study Reminder",
            message,
            alert_type="study_reminder",
            module="study_assistant",
            severity="low",
            priority="medium",
            category="reminder",
            suggested_action="Open the study plan and update progress.",
            action_buttons=["Open Study Plan", "Snooze", "Dismiss"],
            voice_message="You have a study reminder.",
            voice_enabled=False,
            metadata={"plan_id": plan_id, "topic": topic},
        )
        self.add_timeline_event(db, "study", "Study reminder scheduled", message, "study_assistant")
        return {"plan": self._study_plan_dict(plan, db), "notification": notification}

    def update_study_progress(self, db: Session, plan_id: int, topic: str, progress_percent: float, status: str = "in_progress", notes: str = "") -> dict:
        row = db.query(StudyProgress).filter(StudyProgress.plan_id == plan_id, StudyProgress.topic == topic).one_or_none()
        if not row:
            row = StudyProgress(plan_id=plan_id, topic=topic)
            db.add(row)
        row.progress_percent = max(0, min(100, progress_percent))
        row.status = status
        row.notes = notes
        row.updated_at = datetime.utcnow()
        plan = db.get(StudyPlan, plan_id)
        if not plan:
            raise ValueError("Study plan not found")
        db.commit()
        progress_rows = db.query(StudyProgress).filter(StudyProgress.plan_id == plan_id).all()
        plan.progress_percent = round(sum(item.progress_percent for item in progress_rows) / max(len(progress_rows), 1), 2)
        plan.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(plan)
        if status == "completed" or progress_percent >= 100:
            self.add_timeline_event(db, "study", "Study topic completed", topic, "study_assistant")
            self._unlock_study_achievement(db, "Topic Completed", "Progress", f"Completed {topic}.", {"topic": topic, "plan_id": plan_id})
        return self._study_plan_dict(plan, db)

    def list_study_plans(self, db: Session) -> list[dict]:
        return [self._study_plan_dict(row, db) for row in db.query(StudyPlan).order_by(StudyPlan.created_at.desc()).all()]

    def update_study_chapter_progress(self, db: Session, chapter_id: int, completion_percent: float, status: str = "in_progress", notes: str = "") -> dict:
        row = db.get(StudyChapter, chapter_id)
        if not row:
            raise ValueError("Study chapter not found")
        row.completion_percent = max(0, min(100, completion_percent))
        row.status = "completed" if row.completion_percent >= 100 else status
        row.last_studied_at = datetime.utcnow()
        row.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        self._recalculate_subject(db, row.subject_id)
        self.add_timeline_event(db, "study", "Chapter progress updated", row.title, "study_assistant", metadata={"chapter_id": row.id, "completion_percent": row.completion_percent})
        if row.status == "completed":
            self._unlock_study_achievement(db, "Chapter Completed", "Progress", f"Completed {row.title}.", {"chapter_id": row.id})
        return self._study_chapter_dict(row)

    def record_study_session(
        self,
        db: Session,
        subject_id: int | None = None,
        subject_name: str = "",
        chapter_id: int | None = None,
        chapter_title: str = "",
        topic: str = "",
        duration_minutes: int = 25,
        session_type: str = "study",
        notes: str = "",
        focus_session_id: int | None = None,
    ) -> dict:
        subject = db.get(StudySubject, subject_id) if subject_id else None
        if not subject and subject_name:
            subject = db.query(StudySubject).filter(StudySubject.name.ilike(subject_name)).order_by(StudySubject.updated_at.desc()).first()
            if not subject:
                subject = StudySubject(name=subject_name)
                db.add(subject)
                db.flush()
        chapter = db.get(StudyChapter, chapter_id) if chapter_id else None
        if not chapter and subject and chapter_title:
            chapter = db.query(StudyChapter).filter(StudyChapter.subject_id == subject.id, StudyChapter.title.ilike(chapter_title)).order_by(StudyChapter.updated_at.desc()).first()
            if not chapter:
                chapter = StudyChapter(subject_id=subject.id, title=chapter_title, topics_json=json.dumps([topic] if topic else []))
                db.add(chapter)
                db.flush()
        duration_seconds = max(0, duration_minutes) * 60
        row = StudySession(
            subject_id=subject.id if subject else None,
            chapter_id=chapter.id if chapter else None,
            subject_name=subject.name if subject else subject_name,
            chapter_title=chapter.title if chapter else chapter_title,
            topic=topic,
            session_type=session_type,
            duration_seconds=duration_seconds,
            revision_seconds=duration_seconds if session_type == "revision" else 0,
            practice_seconds=duration_seconds if session_type == "practice" else 0,
            focus_session_id=focus_session_id,
            notes=notes,
            ended_at=datetime.utcnow(),
        )
        db.add(row)
        if chapter and duration_seconds:
            chapter.last_studied_at = datetime.utcnow()
            chapter.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        if subject:
            self._recalculate_subject(db, subject.id)
        self._update_study_analytics(db, row)
        self.add_timeline_event(db, "study", "Study session recorded", row.subject_name or row.topic or "Study session", "study_assistant", duration_seconds=duration_seconds, metadata={"session_id": row.id, "subject_id": row.subject_id})
        self._evaluate_study_achievements(db)
        return self._study_session_dict(row)

    def create_study_goal(self, db: Session, title: str, target_value: float, unit: str = "hours", subject_id: int | None = None, deadline: str = "") -> dict:
        row = StudyGoal(title=title, target_value=target_value, unit=unit, subject_id=subject_id, deadline=deadline)
        db.add(row)
        db.commit()
        db.refresh(row)
        return self._study_goal_dict(row)

    def update_study_goal(self, db: Session, goal_id: int, current_value: float) -> dict:
        row = db.get(StudyGoal, goal_id)
        if not row:
            raise ValueError("Study goal not found")
        row.current_value = max(0, current_value)
        row.progress_percent = round(min(100, row.current_value / max(row.target_value, 1) * 100), 2)
        row.status = "completed" if row.progress_percent >= 100 else "active"
        row.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        if row.status == "completed":
            self._unlock_study_achievement(db, "Study Goal Achieved", "Goal", row.title, {"goal_id": row.id})
        return self._study_goal_dict(row)

    def study_dashboard(self, db: Session) -> dict:
        subjects = [self._study_subject_dict(row, db) for row in db.query(StudySubject).order_by(StudySubject.updated_at.desc()).limit(50).all()]
        plans = self.list_study_plans(db)
        sessions = [self._study_session_dict(row) for row in db.query(StudySession).order_by(StudySession.created_at.desc()).limit(30).all()]
        goals = [self._study_goal_dict(row) for row in db.query(StudyGoal).order_by(StudyGoal.updated_at.desc()).limit(30).all()]
        exams = [self._exam_schedule_dict(row, db) for row in db.query(ExamSchedule).order_by(ExamSchedule.exam_date.asc()).limit(30).all()]
        revisions = [self._revision_plan_dict(row, db) for row in db.query(RevisionPlan).order_by(RevisionPlan.scheduled_date.asc()).limit(50).all()]
        analytics = [self._study_analytics_dict(row) for row in db.query(StudyAnalytics).order_by(StudyAnalytics.created_at.desc()).limit(30).all()]
        achievements = [self._study_achievement_dict(row) for row in db.query(StudyAchievement).order_by(StudyAchievement.created_at.desc()).limit(20).all()]
        recommendations = self.study_recommendations(db, subjects, revisions, goals)
        today_seconds = sum(item["duration_seconds"] for item in sessions if item["created_at"][:10] == date.today().isoformat())
        readiness = round(sum(item["readiness_score"] for item in subjects) / max(len(subjects), 1), 2)
        return {
            "subjects": subjects,
            "plans": plans,
            "sessions": sessions,
            "goals": goals,
            "exams": exams,
            "revisions": revisions,
            "analytics": analytics,
            "achievements": achievements,
            "recommendations": recommendations,
            "today_study_seconds": today_seconds,
            "readiness_score": readiness,
            "offline_ready": True,
        }

    def study_recommendations(self, db: Session, subjects: list[dict] | None = None, revisions: list[dict] | None = None, goals: list[dict] | None = None) -> list[dict]:
        subjects = subjects if subjects is not None else [self._study_subject_dict(row, db) for row in db.query(StudySubject).all()]
        revisions = revisions if revisions is not None else [self._revision_plan_dict(row, db) for row in db.query(RevisionPlan).all()]
        goals = goals if goals is not None else [self._study_goal_dict(row) for row in db.query(StudyGoal).all()]
        today = date.today()
        recommendations: list[dict] = []
        for subject in subjects:
            days = subject.get("days_remaining")
            if days is not None and days <= 5 and subject.get("completion_percent", 0) < 80:
                recommendations.append({"priority": "high", "title": f"{subject['name']} exam is close", "message": "Prioritize weak chapters, revision, and practice tests.", "action": "open_study_dashboard"})
            if subject.get("days_since_studied") is not None and subject["days_since_studied"] >= 4:
                recommendations.append({"priority": "medium", "title": f"Resume {subject['name']}", "message": f"You have not studied {subject['name']} in {subject['days_since_studied']} days.", "action": "start_study_session"})
            if subject.get("completion_percent", 0) < 50 and (days or 99) <= 14:
                recommendations.append({"priority": "high", "title": f"{subject['name']} progress is below target", "message": "Increase daily study time or reduce lower-priority topics.", "action": "adjust_plan"})
        due_revisions = [item for item in revisions if item.get("scheduled_date") and item["scheduled_date"] <= today.isoformat() and item.get("status") == "scheduled"]
        if due_revisions:
            recommendations.append({"priority": "medium", "title": "Revision due today", "message": f"{len(due_revisions)} revision item(s) are due.", "action": "show_revision_plan"})
        for goal in goals:
            if goal.get("status") != "completed" and goal.get("deadline") and goal["deadline"] <= today.isoformat():
                recommendations.append({"priority": "medium", "title": "Study goal deadline reached", "message": goal["title"], "action": "update_goal"})
        if not recommendations:
            recommendations.append({"priority": "low", "title": "Study plan is stable", "message": "Keep following today's schedule and record progress after each session.", "action": "continue"})
        return recommendations[:10]

    def add_timeline_event(self, db: Session, event_type: str, title: str, description: str = "", source: str = "nexa", duration_seconds: int = 0, metadata: dict | None = None, commit: bool = True) -> dict:
        metadata = metadata or {}
        importance = self._memory_importance(event_type, title, duration_seconds, metadata)
        if importance < 15:
            return {"skipped": True, "reason": "low_importance", "event_type": event_type, "title": title}
        recent_cutoff = datetime.utcnow() - timedelta(minutes=2)
        duplicate = (
            db.query(TimelineEvent)
            .filter(TimelineEvent.event_type == event_type, TimelineEvent.title == title, TimelineEvent.source == source, TimelineEvent.created_at >= recent_cutoff)
            .order_by(TimelineEvent.created_at.desc())
            .first()
        )
        if duplicate:
            return self._timeline_dict(duplicate)
        enriched = {**metadata, "importance": importance, "category": self._memory_category(event_type)}
        row = TimelineEvent(event_type=event_type, title=title, description=description, source=source, duration_seconds=duration_seconds, metadata_json=json.dumps(enriched, default=str))
        db.add(row)
        db.flush()
        db.add(ActivityHistory(timeline_event_id=row.id, activity_type=event_type, title=title, detail_json=json.dumps(enriched, default=str), importance=importance))
        if event_type in {"achievement", "goal", "study_achievement"} or "achieved" in title.lower() or "completed" in title.lower():
            db.add(AchievementHistory(achievement_type=event_type, title=title, description=description, source=source, metadata_json=json.dumps(enriched, default=str)))
        if commit:
            db.commit()
            db.refresh(row)
        else:
            db.flush()
        return self._timeline_dict(row)

    def search_timeline(self, db: Session, query: str | None = None, event_type: str | None = None, limit: int = 100, start_date: str | None = None, end_date: str | None = None) -> list[dict]:
        rows = db.query(TimelineEvent)
        if query:
            like = f"%{query}%"
            rows = rows.filter((TimelineEvent.title.ilike(like)) | (TimelineEvent.description.ilike(like)) | (TimelineEvent.project.ilike(like)) | (TimelineEvent.source.ilike(like)))
        if event_type:
            rows = rows.filter(TimelineEvent.event_type == event_type)
        if start_date:
            rows = rows.filter(TimelineEvent.created_at >= datetime.fromisoformat(start_date))
        if end_date:
            rows = rows.filter(TimelineEvent.created_at < datetime.fromisoformat(end_date) + timedelta(days=1))
        result = [self._timeline_dict(row) for row in rows.order_by(TimelineEvent.created_at.desc()).limit(limit).all()]
        if query:
            db.add(MemorySearch(query=query, normalized_query=query.lower().strip(), result_count=len(result), filters_json=json.dumps({"event_type": event_type, "start_date": start_date, "end_date": end_date}, default=str)))
            db.commit()
        return result

    def natural_memory_search(self, db: Session, query: str, limit: int = 100) -> dict:
        lower = query.lower().strip()
        today = date.today()
        event_type = None
        start = None
        end = None
        text_query = query
        if "yesterday" in lower:
            start = today - timedelta(days=1)
            end = start
            text_query = ""
        elif "today" in lower:
            start = today
            end = today
            text_query = ""
        elif "last week" in lower or "this week" in lower:
            start = today - timedelta(days=today.weekday() + (7 if "last week" in lower else 0))
            end = start + timedelta(days=6)
            text_query = ""
        elif "last month" in lower or "this month" in lower:
            first = today.replace(day=1)
            if "last month" in lower:
                last_month_end = first - timedelta(days=1)
                start = last_month_end.replace(day=1)
                end = last_month_end
            else:
                start = first
                end = today
            text_query = ""
        for key in ["coding", "study", "focus", "goal", "automation", "download", "college", "project", "achievement"]:
            if key in lower:
                event_type = key if key != "achievement" else None
                if "history" in lower or "show" in lower or "report" in lower:
                    text_query = ""
                elif not text_query:
                    text_query = key
                break
        results = self.search_timeline(db, text_query or None, event_type, limit, start.isoformat() if start else None, end.isoformat() if end else None)
        summary = self._memory_search_summary(query, results)
        return {"query": query, "interpreted": {"event_type": event_type, "start_date": start.isoformat() if start else None, "end_date": end.isoformat() if end else None}, "summary": summary, "results": results}

    def timeline_summary(self, db: Session, period: str = "day", reference_date: str | None = None, force: bool = False) -> dict:
        start, end = self._timeline_range(period, reference_date)
        existing = db.query(TimelineSummary).filter(TimelineSummary.period == period, TimelineSummary.start_date == start.isoformat(), TimelineSummary.end_date == end.isoformat()).order_by(TimelineSummary.updated_at.desc()).first()
        if existing and not force:
            return self._timeline_summary_dict(existing)
        events = self.search_timeline(db, start_date=start.isoformat(), end_date=end.isoformat(), limit=1000)
        stats = self._timeline_stats(events)
        highlights = self._timeline_highlights(events)
        recommendations = self._timeline_recommendations(stats)
        summary = self._timeline_summary_text(period, stats, highlights)
        row = existing or TimelineSummary(period=period, start_date=start.isoformat(), end_date=end.isoformat())
        row.summary = summary
        row.stats_json = json.dumps(stats, default=str)
        row.highlights_json = json.dumps(highlights, default=str)
        row.recommendations_json = json.dumps(recommendations, default=str)
        row.updated_at = datetime.utcnow()
        db.add(row)
        db.commit()
        db.refresh(row)
        self._generate_timeline_insights(db, period, stats)
        return self._timeline_summary_dict(row)

    def timeline_dashboard(self, db: Session, view: str = "today", event_type: str | None = None, query: str | None = None) -> dict:
        period = {"today": "day", "week": "week", "month": "month", "year": "year"}.get(view, "day")
        start, end = self._timeline_range(period)
        events = self.search_timeline(db, query, event_type, 300, start.isoformat(), end.isoformat())
        summary = self.timeline_summary(db, period)
        week = self.timeline_summary(db, "week")
        month = self.timeline_summary(db, "month")
        insights = [self._timeline_insight_dict(row) for row in db.query(TimelineInsight).order_by(TimelineInsight.created_at.desc()).limit(20).all()]
        categories = self._memory_categories(db)
        return {"view": view, "period": period, "start_date": start.isoformat(), "end_date": end.isoformat(), "events": events, "summary": summary, "week": week, "month": month, "insights": insights, "categories": categories, "stats": self._timeline_stats(events), "offline_ready": True}

    def project_guardian_snapshot(self, db: Session, project_path: str, action: str = "manual_snapshot") -> dict:
        source = Path(project_path).expanduser().resolve()
        if not source.exists():
            raise ValueError("Project path does not exist")
        project = self._ensure_project(db, source)
        git_status = self.git_status(str(source))
        destination = self._create_project_backup(source, action)
        detail = {
            "reason": "Project Guardian recovery snapshot",
            "git_status": git_status,
            "sensitive_files_excluded": True,
            "backup_policy": "local_copy_excluding_build_secrets",
        }
        backup = ProjectBackup(project_path=str(source), action=action, backup_path=str(destination), detail_json=json.dumps(detail, default=str))
        db.add(backup)
        db.flush()
        snapshot = ProjectSnapshot(
            project_id=project.id,
            project_path=str(source),
            project_name=project.name,
            action=action,
            git_status_json=json.dumps(git_status, default=str),
            modified_files_json=json.dumps(git_status.get("modified_files", []), default=str),
            commit_hash=git_status.get("commit_hash", ""),
            branch_name=git_status.get("branch", ""),
            backup_path=str(destination),
            metadata_json=json.dumps({"backup_id": backup.id, "operation": action}, default=str),
        )
        db.add(snapshot)
        db.flush()
        recovery = RecoveryPoint(project_id=project.id, snapshot_id=snapshot.id, backup_id=backup.id, title=f"{project.name} {action} recovery point", restore_path=str(destination), recovery_type=action, metadata_json=json.dumps({"project_path": str(source)}, default=str))
        db.add(recovery)
        project.last_backup_at = datetime.utcnow()
        project.git_branch = git_status.get("branch", "")
        project.commit_hash = git_status.get("commit_hash", "")
        project.updated_at = datetime.utcnow()
        self._record_project_event(db, project.id, "snapshot_created", "Project snapshot created", f"{project.name} protected before {action}.", "low", {"snapshot_id": snapshot.id, "backup_id": backup.id})
        db.commit()
        db.refresh(backup)
        self.add_timeline_event(db, "project", "Project snapshot created", f"{project.name} protected before {action}.", "project_guardian", metadata={"project_id": project.id, "snapshot_id": snapshot.id, "backup_id": backup.id, "important": True})
        NotificationAgent(db).notify(
            "Nexa Project Guardian",
            f"Recovery snapshot created for {project.name}.",
            alert_type="project_guardian",
            module="project_guardian",
            severity="low",
            priority="medium",
            category="success",
            suggested_action="Continue only after the recovery point is available.",
            action_buttons=["Open Project Guardian", "Dismiss"],
            metadata={"project_id": project.id, "backup_id": backup.id, "snapshot_id": snapshot.id},
        )
        self.evaluate_project_health(db, project.id)
        return {**self._project_backup_dict(backup), "snapshot": self._project_snapshot_dict(snapshot), "recovery_point": self._recovery_point_dict(recovery)}

    def restore_project_backup(self, db: Session, backup_id: int, restore_path: str) -> dict:
        row = db.get(ProjectBackup, backup_id)
        if not row:
            raise ValueError("Backup not found")
        source = Path(row.backup_path).expanduser().resolve()
        destination = Path(restore_path).expanduser().resolve()
        if not source.exists():
            raise ValueError("Backup path does not exist")
        if destination.exists():
            raise ValueError("Restore path already exists")
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        row.status = "restored"
        row.detail_json = json.dumps({**_loads(row.detail_json, {}), "restored_to": str(destination), "restored_at": datetime.utcnow().isoformat()}, default=str)
        project = db.query(Project).filter(Project.path == row.project_path).order_by(Project.updated_at.desc()).first()
        if project:
            recovery = db.query(RecoveryPoint).filter(RecoveryPoint.backup_id == row.id).order_by(RecoveryPoint.created_at.desc()).first()
            if recovery:
                recovery.status = "restored"
                recovery.restored_at = datetime.utcnow()
            self._record_project_event(db, project.id, "restored", "Project restored", f"Restored {project.name} to {destination}.", "medium", {"backup_id": row.id, "restore_path": str(destination)})
            self.add_timeline_event(db, "project", "Project restored", f"{project.name} restored from recovery point.", "project_guardian", metadata={"project_id": project.id, "backup_id": row.id, "important": True}, commit=False)
        db.commit()
        db.refresh(row)
        return self._project_backup_dict(row)

    def git_status(self, project_path: str) -> dict:
        source = Path(project_path).expanduser().resolve()
        if not source.exists():
            raise ValueError("Project path does not exist")
        if not (source / ".git").exists():
            return {"is_git_repo": False, "branch": "", "commit_hash": "", "modified_files": [], "untracked_files": [], "dirty": False}
        def run_git(args: list[str]) -> str:
            result = subprocess.run(["git", *args], cwd=str(source), capture_output=True, text=True, timeout=10)
            return result.stdout.strip() if result.returncode == 0 else ""
        branch = run_git(["branch", "--show-current"])
        commit_hash = run_git(["rev-parse", "--short", "HEAD"])
        porcelain = run_git(["status", "--porcelain"])
        modified = []
        untracked = []
        for line in porcelain.splitlines():
            path = line[3:].strip()
            if line.startswith("??"):
                untracked.append(path)
            elif path:
                modified.append(path)
        return {"is_git_repo": True, "branch": branch, "commit_hash": commit_hash, "modified_files": modified, "untracked_files": untracked, "dirty": bool(modified or untracked), "raw": porcelain}

    def protect_project_operation(self, db: Session, project_path: str, operation: str, reason: str = "") -> dict:
        source = Path(project_path).expanduser().resolve()
        if not source.exists():
            raise ValueError("Project path does not exist")
        high_risk = operation in {"shutdown", "restart", "sleep", "hibernate", "delete", "git_push", "git_pull", "git_merge", "git_reset", "git_rebase", "branch_switch"}
        snapshot = self.project_guardian_snapshot(db, str(source), operation)
        project = self._ensure_project(db, source)
        status = self.git_status(str(source))
        risk = "high" if high_risk or status.get("dirty") else "medium"
        git_row = GitHistory(project_id=project.id, project_path=str(source), operation=operation, branch_name=status.get("branch", ""), commit_hash=status.get("commit_hash", ""), status_json=json.dumps(status, default=str), snapshot_id=snapshot["snapshot"]["id"], risk_level=risk)
        db.add(git_row)
        self._record_project_event(db, project.id, f"{operation}_protected", "Project operation protected", reason or f"Protected before {operation}.", risk, {"snapshot_id": snapshot["snapshot"]["id"], "dirty": status.get("dirty")})
        db.commit()
        approval = {
            "requires_approval": operation in {"shutdown", "restart", "delete", "git_reset", "git_rebase", "branch_switch"},
            "action": operation,
            "risk_level": risk,
            "options": ["Backup and Proceed", "Cancel", "Review Changes"],
        }
        return {"project": self._project_dict(project), "snapshot": snapshot, "git_status": status, "approval": approval, "protected": True}

    def evaluate_project_health(self, db: Session, project_id: int) -> dict:
        project = db.get(Project, project_id)
        if not project:
            raise ValueError("Project not found")
        status = self.git_status(project.path)
        backup_age_hours = 999.0
        if project.last_backup_at:
            backup_age_hours = round((datetime.utcnow() - project.last_backup_at).total_seconds() / 3600, 2)
        uncommitted = len(status.get("modified_files", [])) + len(status.get("untracked_files", []))
        score = 100 - min(35, uncommitted * 5) - min(35, backup_age_hours / 24 * 10)
        if not status.get("is_git_repo"):
            score -= 10
        score = round(max(0, min(100, score)), 2)
        recommendations = []
        if uncommitted:
            recommendations.append("Commit or snapshot uncommitted changes.")
        if backup_age_hours > 24:
            recommendations.append("Create a fresh Project Guardian backup.")
        if not status.get("is_git_repo"):
            recommendations.append("Initialize Git or register this as a non-Git project.")
        if not recommendations:
            recommendations.append("Project recovery readiness is healthy.")
        risk = "high" if score < 50 else "medium" if score < 75 else "low"
        row = ProjectHealth(project_id=project.id, health_score=score, uncommitted_files=uncommitted, backup_age_hours=backup_age_hours, risk_level=risk, recommendations_json=json.dumps(recommendations, default=str))
        db.add(row)
        project.health_score = score
        project.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        return self._project_health_dict(row)

    def project_guardian_dashboard(self, db: Session, project_path: str | None = None) -> dict:
        if project_path:
            self._ensure_project(db, Path(project_path).expanduser().resolve())
        projects = [self._project_dict(row) for row in db.query(Project).order_by(Project.updated_at.desc()).limit(50).all()]
        backups = [self._project_backup_dict(row) for row in db.query(ProjectBackup).order_by(ProjectBackup.created_at.desc()).limit(30).all()]
        snapshots = [self._project_snapshot_dict(row) for row in db.query(ProjectSnapshot).order_by(ProjectSnapshot.created_at.desc()).limit(30).all()]
        recovery_points = [self._recovery_point_dict(row) for row in db.query(RecoveryPoint).order_by(RecoveryPoint.created_at.desc()).limit(30).all()]
        git_history = [self._git_history_dict(row) for row in db.query(GitHistory).order_by(GitHistory.created_at.desc()).limit(30).all()]
        events = [self._project_event_dict(row) for row in db.query(ProjectEvent).order_by(ProjectEvent.created_at.desc()).limit(50).all()]
        health = [self._project_health_dict(row) for row in db.query(ProjectHealth).order_by(ProjectHealth.created_at.desc()).limit(30).all()]
        return {"projects": projects, "backups": backups, "snapshots": snapshots, "recovery_points": recovery_points, "git_history": git_history, "events": events, "health": health, "offline_ready": True}

    def recovery_dashboard(self, db: Session) -> dict:
        reports = [self._crash_report_dict(row) for row in db.query(CrashReport).order_by(CrashReport.created_at.desc()).limit(30).all()]
        sessions = [self._recovery_session_dict(row) for row in db.query(RecoverySession).order_by(RecoverySession.started_at.desc()).limit(30).all()]
        incidents = [self._incident_report_dict(row) for row in db.query(IncidentReport).order_by(IncidentReport.created_at.desc()).limit(30).all()]
        events = [self._recovery_event_dict(row) for row in db.query(RecoveryEvent).order_by(RecoveryEvent.created_at.desc()).limit(50).all()]
        apps = [self._recovered_application_dict(row) for row in db.query(RecoveredApplication).order_by(RecoveredApplication.created_at.desc()).limit(50).all()]
        history = [self._recovery_history_dict(row) for row in db.query(RecoveryHistory).order_by(RecoveryHistory.created_at.desc()).limit(50).all()]
        guardian = self.project_guardian_dashboard(db)
        open_reports = sum(1 for row in reports if row["status"] == "open")
        recovered = sum(1 for row in sessions if row["status"] == "restored")
        score = max(0, min(100, 100 - open_reports * 12 + min(len(guardian["recovery_points"]), 5) * 3))
        return {
            "summary": {
                "crash_reports": len(reports),
                "open_reports": open_reports,
                "recovery_sessions": len(sessions),
                "restored_sessions": recovered,
                "incident_reports": len(incidents),
                "available_app_restores": sum(1 for row in apps if row["status"] == "available"),
                "recovery_points": len(guardian["recovery_points"]),
                "health_score": round(score, 1),
            },
            "crash_reports": reports,
            "recovery_sessions": sessions,
            "incident_reports": incidents,
            "events": events,
            "recovered_applications": apps,
            "history": history,
            "project_guardian": {
                "recovery_points": guardian["recovery_points"][:10],
                "backups": guardian["backups"][:10],
                "health": guardian["health"][:10],
            },
            "recommendations": self.recovery_recommendations(db),
            "capabilities": {
                "crash_detection": True,
                "vscode_recovery": True,
                "cursor_recovery": True,
                "terminal_recovery": True,
                "power_loss_recovery": True,
                "bsod_detection": True,
                "session_restore": True,
                "offline_ready": True,
            },
            "offline_ready": True,
        }

    def record_crash_report(
        self,
        db: Session,
        crash_type: str,
        source: str = "emergency_recovery",
        application: str = "",
        message: str = "",
        severity: str = "high",
        stack_trace: str = "",
        diagnostics: dict | None = None,
        project_path: str | None = None,
    ) -> dict:
        diagnostics = diagnostics or {}
        application = application or self._application_from_crash_type(crash_type)
        title = f"{application or 'System'} recovery report"
        report = CrashReport(crash_type=crash_type, source=source, application=application, severity=severity, message=message or f"{crash_type.replace('_', ' ').title()} detected.", stack_trace=stack_trace, diagnostics_json=json.dumps(diagnostics, default=str))
        db.add(report)
        db.flush()
        session = self._capture_recovery_session_row(db, crash_type, [{"name": application, "process": diagnostics.get("process_name", ""), "workspace_path": project_path or diagnostics.get("workspace_path", "")}], project_path, commit=False)
        actions = ["Saved crash diagnostics", "Captured recovery session", "Prepared restore plan"]
        if project_path:
            try:
                snapshot = self.project_guardian_snapshot(db, project_path, f"{crash_type}_recovery")
                actions.append("Created Project Guardian recovery snapshot")
                diagnostics["project_guardian_snapshot"] = snapshot
                report.diagnostics_json = json.dumps(diagnostics, default=str)
            except Exception as exc:
                diagnostics["project_guardian_error"] = str(exc)
                report.diagnostics_json = json.dumps(diagnostics, default=str)
        incident = IncidentReport(
            incident_type=crash_type,
            title=title,
            summary=report.message,
            applications_affected_json=json.dumps([application] if application else [], default=str),
            recovery_actions_json=json.dumps(actions, default=str),
            recovered_items_json=json.dumps(_loads(session.restore_plan_json, []), default=str),
            recommendations_json=json.dumps(self._recovery_recommendations_for(crash_type, application), default=str),
        )
        db.add(incident)
        self._record_recovery_event(db, crash_type, "Crash detected", report.message, severity, {"report_id": report.id, "application": application, "session_id": session.id})
        db.commit()
        db.refresh(report)
        db.refresh(session)
        db.refresh(incident)
        self._write_recovery_log("crash.log", f"{crash_type} {application}: {report.message}")
        self._write_recovery_log("recovery.log", f"Captured session {session.id} for report {report.id}")
        self.add_timeline_event(db, "recovery", "Crash recovery report created", report.message, "emergency_recovery", metadata={"report_id": report.id, "session_id": session.id, "important": True})
        NotificationAgent(db).notify(
            "Nexa Emergency Recovery",
            report.message,
            alert_type="emergency_recovery",
            module="emergency_recovery",
            severity=severity,
            priority="high",
            category="warning",
            suggested_action="Open Emergency Recovery to review restore options.",
            action_buttons=["Open Recovery", "View Report", "Dismiss"],
            metadata={"report_id": report.id, "session_id": session.id, "application": application},
        )
        return {"crash_report": self._crash_report_dict(report), "session": self._recovery_session_dict(session), "incident_report": self._incident_report_dict(incident)}

    def capture_recovery_session(self, db: Session, session_type: str = "workspace", applications: list[dict] | None = None, project_path: str | None = None) -> dict:
        row = self._capture_recovery_session_row(db, session_type, applications or [], project_path)
        self._record_recovery_event(db, "session_captured", "Recovery session captured", f"Captured {session_type} recovery state.", "medium", {"session_id": row.id})
        db.commit()
        db.refresh(row)
        self._write_recovery_log("recovery.log", f"Captured recovery session {row.id} ({session_type})")
        return self._recovery_session_dict(row)

    def restore_recovery_session(self, db: Session, session_id: int) -> dict:
        row = db.get(RecoverySession, session_id)
        if not row:
            raise ValueError("Recovery session not found")
        restore_plan = _loads(row.restore_plan_json, [])
        row.status = "restored"
        row.ended_at = datetime.utcnow()
        row.restored_items_json = json.dumps(restore_plan, default=str)
        apps = db.query(RecoveredApplication).filter(RecoveredApplication.session_id == row.id).all()
        for app in apps:
            app.status = "restored"
        self._record_recovery_event(db, "session_restored", "Session restored", f"Prepared restore plan for {len(restore_plan)} item(s).", "low", {"session_id": row.id})
        db.add(RecoveryHistory(event_type="session_restored", title="Session restored", message=f"Recovery session {row.id} marked restored.", status="completed", metadata_json=json.dumps({"session_id": row.id, "restore_plan": restore_plan}, default=str)))
        db.commit()
        db.refresh(row)
        self._write_recovery_log("recovery.log", f"Restored recovery session {row.id}")
        self.add_timeline_event(db, "recovery", "Session restored", f"Recovery session {row.id} restored.", "emergency_recovery", metadata={"session_id": row.id, "important": True})
        NotificationAgent(db).notify(
            "Nexa Emergency Recovery",
            "Recovery session restored. Review the restore plan before reopening sensitive work.",
            alert_type="emergency_recovery",
            module="emergency_recovery",
            severity="low",
            priority="medium",
            category="success",
            suggested_action="Review recovered applications and reopen required work.",
            action_buttons=["Open Recovery", "Dismiss"],
            metadata={"session_id": row.id},
        )
        return self._recovery_session_dict(row)

    def simulate_recovery_event(self, db: Session, event_type: str, application: str = "VS Code", project_path: str | None = None) -> dict:
        diagnostics = {
            "simulated": True,
            "process_name": self._process_for_application(application),
            "workspace_path": project_path or str(Path.cwd()),
            "open_files": [],
            "terminal": {"cwd": project_path or str(Path.cwd()), "recent_commands": []},
        }
        return self.record_crash_report(db, event_type, "simulation", application, f"{application} {event_type.replace('_', ' ')} simulated for recovery validation.", "high", diagnostics=diagnostics, project_path=project_path)

    def recovery_recommendations(self, db: Session) -> list[dict]:
        open_reports = db.query(CrashReport).filter(CrashReport.status == "open").count()
        sessions = db.query(RecoverySession).filter(RecoverySession.status == "captured").count()
        recovery_points = db.query(RecoveryPoint).filter(RecoveryPoint.status == "available").count()
        recommendations = []
        if open_reports:
            recommendations.append({"priority": "high", "title": "Review crash reports", "message": f"{open_reports} open crash report(s) need review.", "action": "open_recovery_dashboard"})
        if sessions:
            recommendations.append({"priority": "medium", "title": "Restore captured sessions", "message": f"{sessions} captured recovery session(s) are available.", "action": "restore_session"})
        if recovery_points == 0:
            recommendations.append({"priority": "medium", "title": "Create project recovery points", "message": "No Project Guardian recovery point is available yet.", "action": "create_snapshot"})
        if not recommendations:
            recommendations.append({"priority": "low", "title": "Recovery readiness healthy", "message": "No open incidents detected. Recovery services are ready offline.", "action": "none"})
        return recommendations

    def recovery_startup_check(self) -> dict:
        with self.db_factory() as db:
            clean = self._setting_value(db, "emergency_recovery.clean_shutdown", "true")
            last_seen = self._setting_value(db, "emergency_recovery.last_seen", "")
            recorded = None
            if clean == "false":
                recorded = self.record_crash_report(
                    db,
                    "unexpected_shutdown",
                    source="startup_heartbeat",
                    application="Nexa",
                    message="Nexa detected an unclean previous shutdown. Recovery information is available.",
                    severity="high",
                    diagnostics={"last_seen": last_seen, "detected_at": datetime.utcnow().isoformat()},
                )
            self._set_setting_value(db, "emergency_recovery.clean_shutdown", "false")
            self._set_setting_value(db, "emergency_recovery.last_seen", datetime.utcnow().isoformat())
            db.commit()
            return {"startup_checked": True, "unclean_shutdown_detected": recorded is not None, "recorded": recorded}

    def recovery_clean_shutdown(self) -> None:
        with self.db_factory() as db:
            self._set_setting_value(db, "emergency_recovery.clean_shutdown", "true")
            self._set_setting_value(db, "emergency_recovery.last_seen", datetime.utcnow().isoformat())
            db.commit()

    def scan_downloads(self, db: Session, folder: str | None = None, large_file_mb: int = 500) -> dict:
        root = self._downloads_root(folder)
        large_threshold = max(1, large_file_mb) * 1024 * 1024
        seen_content: dict[str, str] = {}
        seen_names: dict[str, str] = {}
        indexed: list[DownloadHistory] = []
        duplicates: list[DuplicateFile] = []
        suggestions: list[CleanupSuggestion] = []
        category_stats: dict[str, dict] = {}
        large_files: list[dict] = []
        total_size = 0

        for path in self._download_files(root):
            size = path.stat().st_size
            total_size += size
            digest = self._file_digest(path)
            duplicate = seen_content.get(digest, "")
            duplicate_type = "content"
            name_key = path.name.lower()
            if not duplicate and name_key in seen_names:
                duplicate = seen_names[name_key]
                duplicate_type = "name"
            seen_content.setdefault(digest, str(path))
            seen_names.setdefault(name_key, str(path))

            category = self._download_category(path, db)
            recommendation = ""
            if size >= large_threshold:
                recommendation = "Large file: review before keeping."
                large_files.append(self._download_file_metadata(path, category, digest))
                suggestions.append(self._record_cleanup_suggestion(db, path, "large_file", "Large file downloaded", f"{path.name} is {self._format_bytes(size)}. Review whether it should be kept.", size, "medium", {"category": category}))
            if duplicate:
                recommendation = f"Duplicate of {duplicate}"
                duplicate_row = DuplicateFile(file_path=str(path), duplicate_of=duplicate, duplicate_type=duplicate_type, digest=digest, size_bytes=size, recommendation="Review duplicate before deleting.")
                db.add(duplicate_row)
                duplicates.append(duplicate_row)
                suggestions.append(self._record_cleanup_suggestion(db, path, "duplicate", "Duplicate download detected", f"{path.name} appears to duplicate {Path(duplicate).name}.", size, "medium", {"duplicate_of": duplicate, "duplicate_type": duplicate_type}))
            if category == "Programs" and path.stat().st_mtime < (datetime.utcnow() - timedelta(days=30)).timestamp():
                suggestions.append(self._record_cleanup_suggestion(db, path, "old_installer", "Old installer can be cleaned", f"{path.name} is an installer older than 30 days.", size, "low", {"category": category}))

            row = self._upsert_download_history(db, path, category, size, duplicate, recommendation, "indexed")
            indexed.append(row)
            bucket = category_stats.setdefault(category, {"category": category, "file_count": 0, "total_size_bytes": 0, "large_file_count": 0, "duplicate_count": 0})
            bucket["file_count"] += 1
            bucket["total_size_bytes"] += size
            bucket["large_file_count"] += 1 if size >= large_threshold else 0
            bucket["duplicate_count"] += 1 if duplicate else 0

        self._record_download_analytics(db, category_stats)
        report = StorageReport(root_path=str(root), total_files=len(indexed), total_size_bytes=total_size, category_breakdown_json=json.dumps(category_stats, default=str), large_files_json=json.dumps(large_files, default=str), duplicate_count=len(duplicates), cleanup_recommendations_json=json.dumps([self._cleanup_suggestion_dict(item) for item in suggestions], default=str))
        db.add(report)
        db.add(DownloadMonitorEvent(event_type="scan", file_path=str(root), title="Downloads scanned", message=f"Indexed {len(indexed)} files.", metadata_json=json.dumps({"large_files": len(large_files), "duplicates": len(duplicates)}, default=str)))
        db.commit()
        for row in indexed:
            db.refresh(row)
        self.add_timeline_event(db, "download", "Downloads scanned", f"{len(indexed)} files indexed in {root.name}.", "download_manager", metadata={"folder": str(root), "duplicates": len(duplicates), "large_files": len(large_files)})
        if duplicates:
            self._notify_download_event(db, "Duplicate downloads detected", f"{len(duplicates)} duplicate download(s) need review.", "Review duplicates", "warning")
        if large_files:
            self._notify_download_event(db, "Large download detected", f"{len(large_files)} large file(s) were found in Downloads.", "Review large files", "info")
        return {"folder": str(root), "count": len(indexed), "items": [self._download_dict(row) for row in indexed], "duplicates": [self._duplicate_file_dict(row) for row in duplicates], "large_files": large_files, "cleanup_suggestions": [self._cleanup_suggestion_dict(item) for item in suggestions], "analytics": list(category_stats.values())}

    def organize_downloads(self, db: Session, folder: str | None = None, dry_run: bool = True) -> dict:
        root = self._downloads_root(folder)
        operations = []
        for path in self._download_files(root):
            category = self._download_category(path, db)
            destination = self._unique_destination(root / self._category_folder(category) / path.name)
            operations.append({"source": str(path), "destination": str(destination), "category": category, "dry_run": dry_run})
            if not dry_run:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path), str(destination))
                row = self._upsert_download_history(db, destination, category, destination.stat().st_size, "", "Organized into category folder.", "sorted")
                db.add(DownloadMonitorEvent(event_type="moved", file_path=str(destination), title="Download organized", message=f"{path.name} moved to {destination.parent.name}.", metadata_json=json.dumps({"source": str(path), "destination": str(destination), "category": category}, default=str)))
                self.add_timeline_event(db, "download", "Download organized", f"{path.name} moved to {destination.parent.name}.", "download_manager", metadata={"download_id": row.id, "category": category}, commit=False)
        db.commit()
        if operations:
            self._notify_download_event(db, "Downloads organized" if not dry_run else "Downloads organization preview", f"{len(operations)} file(s) {'organized' if not dry_run else 'ready to organize'}.", "Open Download Manager", "success" if not dry_run else "info")
        return {"folder": str(root), "dry_run": dry_run, "operations": operations}

    def download_dashboard(self, db: Session, folder: str | None = None) -> dict:
        root = str(self._downloads_root(folder, must_exist=False))
        recent = self.list_downloads(db, 25)
        duplicates = self.list_duplicate_files(db, 25)
        cleanup = self.cleanup_suggestions(db, 25)
        analytics = self.download_analytics(db, days=30)
        latest_report = db.query(StorageReport).order_by(StorageReport.created_at.desc()).first()
        large_files = [item for item in recent if item["size_bytes"] >= 100 * 1024 * 1024]
        return {
            "root": root,
            "recent": recent,
            "duplicates": duplicates,
            "large_files": large_files,
            "cleanup_suggestions": cleanup,
            "analytics": analytics,
            "rules": self.list_download_rules(db),
            "storage": self._storage_report_dict(latest_report) if latest_report else None,
            "statistics": self._download_statistics(recent, analytics, duplicates, cleanup),
            "orbital": {"button": "Downloads", "quick_actions": ["Recent Downloads", "Duplicates", "Large Files", "Cleanup Suggestions", "Statistics"]},
            "offline_ready": True,
        }

    def cleanup_suggestions(self, db: Session, limit: int = 100) -> list[dict]:
        rows = db.query(CleanupSuggestion).order_by(CleanupSuggestion.created_at.desc()).limit(limit).all()
        if rows:
            return [self._cleanup_suggestion_dict(row) for row in rows]
        legacy = db.query(DownloadHistory).filter(DownloadHistory.recommendation != "").order_by(DownloadHistory.created_at.desc()).limit(limit).all()
        return [self._download_dict(row) for row in legacy]

    def list_downloads(self, db: Session, limit: int = 100) -> list[dict]:
        rows = db.query(DownloadHistory).order_by(DownloadHistory.created_at.desc()).limit(limit).all()
        return [self._download_dict(row) for row in rows]

    def list_duplicate_files(self, db: Session, limit: int = 100) -> list[dict]:
        rows = db.query(DuplicateFile).order_by(DuplicateFile.created_at.desc()).limit(limit).all()
        return [self._duplicate_file_dict(row) for row in rows]

    def download_analytics(self, db: Session, days: int = 30) -> dict:
        since = (date.today() - timedelta(days=max(1, days))).isoformat()
        rows = db.query(DownloadAnalytics).filter(DownloadAnalytics.analytics_date >= since).order_by(DownloadAnalytics.analytics_date.desc()).all()
        by_category: dict[str, dict] = {}
        total_files = 0
        total_size = 0
        for row in rows:
            bucket = by_category.setdefault(row.category, {"category": row.category, "file_count": 0, "total_size_bytes": 0, "large_file_count": 0, "duplicate_count": 0})
            bucket["file_count"] += row.file_count
            bucket["total_size_bytes"] += row.total_size_bytes
            bucket["large_file_count"] += row.large_file_count
            bucket["duplicate_count"] += row.duplicate_count
            total_files += row.file_count
            total_size += row.total_size_bytes
        return {"days": days, "total_files": total_files, "total_size_bytes": total_size, "by_category": sorted(by_category.values(), key=lambda item: item["total_size_bytes"], reverse=True)}

    def search_downloads(self, db: Session, query: str, limit: int = 100) -> dict:
        lower = query.lower().strip()
        rows = db.query(DownloadHistory)
        if "duplicate" in lower:
            duplicates = self.list_duplicate_files(db, limit)
            return {"query": query, "mode": "duplicates", "summary": f"Found {len(duplicates)} duplicate downloads.", "results": duplicates}
        size_filter = "large" in lower or "larger" in lower
        if size_filter:
            rows = rows.filter(DownloadHistory.size_bytes >= self._extract_size_threshold(lower, 100 * 1024 * 1024))
        category = self._query_category(lower)
        if category:
            rows = rows.filter(DownloadHistory.category == category)
        if "yesterday" in lower:
            start = datetime.combine(date.today() - timedelta(days=1), datetime.min.time())
            end = start + timedelta(days=1)
            rows = rows.filter(DownloadHistory.created_at >= start, DownloadHistory.created_at < end)
        elif "today" in lower:
            start = datetime.combine(date.today(), datetime.min.time())
            rows = rows.filter(DownloadHistory.created_at >= start)
        text = lower
        for token in ["show", "find", "downloads", "download", "from", "today", "yesterday", "large", "larger", "than", "mb", "gb", "files"]:
            text = text.replace(token, " ")
        text = " ".join(text.split())
        if text and not category and not size_filter:
            like = f"%{text}%"
            rows = rows.filter((DownloadHistory.file_name.ilike(like)) | (DownloadHistory.category.ilike(like)))
        results = [self._download_dict(row) for row in rows.order_by(DownloadHistory.created_at.desc()).limit(limit).all()]
        return {"query": query, "mode": "downloads", "summary": f"Found {len(results)} download(s).", "results": results}

    def create_download_rule(self, db: Session, name: str, pattern: str, category: str, destination: str = "", match_type: str = "extension", enabled: bool = True, priority: int = 100) -> dict:
        row = DownloadRule(name=name, pattern=pattern.lower().strip(), category=category, destination=destination, match_type=match_type, enabled=enabled, priority=priority, updated_at=datetime.utcnow())
        db.add(row)
        db.commit()
        db.refresh(row)
        return self._download_rule_dict(row)

    def list_download_rules(self, db: Session) -> list[dict]:
        rows = db.query(DownloadRule).order_by(DownloadRule.priority.asc(), DownloadRule.created_at.desc()).all()
        return [self._download_rule_dict(row) for row in rows]

    def record_screenshot(self, db: Session, file_path: str, source: str = "shortcut", extracted_text: str = "", analysis: str = "", capture_mode: str = "full_screen", language: str = "eng") -> dict:
        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            raise ValueError("Screenshot file does not exist")
        settings = self.get_screenshot_settings(db)
        extracted_text = extracted_text or self._try_local_ocr(path, language)
        local_analysis = self._analyze_screenshot_text(path, extracted_text)
        analysis = analysis or local_analysis["summary"]
        tags = self._screenshot_tags(path, extracted_text, analysis, local_analysis)
        row = ScreenshotHistory(file_path=str(path), source=source, extracted_text=extracted_text, analysis=analysis, tags_json=json.dumps(tags))
        db.add(row)
        db.flush()
        entities = self._extract_text_entities(extracted_text)
        db.add(OCRResult(screenshot_id=row.id, engine="pytesseract" if extracted_text else "local_unavailable", language=language, extracted_text=extracted_text, confidence=local_analysis["ocr_confidence"], entities_json=json.dumps(entities, default=str), status="completed" if extracted_text else "unavailable"))
        db.add(ExtractedText(screenshot_id=row.id, text_type="ocr", value=extracted_text, metadata_json=json.dumps(entities, default=str)))
        if local_analysis.get("error"):
            db.add(ErrorAnalysis(screenshot_id=row.id, error_type=local_analysis["error"]["error_type"], language=local_analysis["error"]["language"], framework=local_analysis["error"]["framework"], probable_cause=local_analysis["error"]["probable_cause"], suggested_fixes_json=json.dumps(local_analysis["error"]["suggested_fixes"], default=str), severity=local_analysis["error"]["severity"]))
        db.add(DocumentSummary(screenshot_id=row.id, document_type=local_analysis["document_type"], summary=local_analysis["summary"], key_points_json=json.dumps(local_analysis["key_points"], default=str), study_notes_json=json.dumps(local_analysis["study_notes"], default=str)))
        db.add(ScreenshotAction(screenshot_id=row.id, action_type="capture", detail_json=json.dumps({"source": source, "capture_mode": capture_mode, "privacy": settings}, default=str)))
        self.add_timeline_event(db, "screenshot", "Screenshot analyzed", local_analysis["summary"], "screenshot_assistant", metadata={"screenshot_id": row.id, "tags": tags, "document_type": local_analysis["document_type"]}, commit=False)
        db.commit()
        db.refresh(row)
        NotificationAgent(db).notify(
            "Nexa Screenshot Assistant",
            "Screenshot captured, analyzed, and added to history.",
            alert_type="screenshot",
            module="screenshot_assistant",
            severity="low",
            priority="low",
            category="success",
            suggested_action="Open Screenshot Assistant to review extracted text, summaries, and smart actions.",
            action_buttons=["Open Screenshot Assistant", "Copy Text", "Dismiss"],
            metadata={"screenshot_id": row.id, "file_path": str(path), "tags": tags, "privacy": settings},
        )
        return self._screenshot_detail(db, row)

    def list_screenshots(self, db: Session, limit: int = 50) -> list[dict]:
        rows = db.query(ScreenshotHistory).order_by(ScreenshotHistory.created_at.desc()).limit(limit).all()
        return [self._screenshot_dict(row) for row in rows]

    def screenshot_dashboard(self, db: Session) -> dict:
        recent = [self._screenshot_detail(db, row) for row in db.query(ScreenshotHistory).order_by(ScreenshotHistory.created_at.desc()).limit(20).all()]
        error_count = db.query(ErrorAnalysis).count()
        document_count = db.query(DocumentSummary).count()
        action_count = db.query(ScreenshotAction).count()
        settings = self.get_screenshot_settings(db)
        return {
            "recent": recent,
            "statistics": {
                "screenshots": db.query(ScreenshotHistory).count(),
                "errors_analyzed": error_count,
                "documents_summarized": document_count,
                "actions_taken": action_count,
                "ocr_results": db.query(OCRResult).count(),
            },
            "smart_actions": ["Copy Text", "Summarize", "Explain", "Save Notes", "Create Task", "Create Reminder", "Search Web", "Save to Timeline"],
            "capture_modes": ["full_screen", "active_window", "selected_area", "current_monitor", "multi_monitor"],
            "orbital": {"button": "Screenshot", "quick_actions": ["Capture Screen", "Analyze Screenshot", "View History", "Extract Text", "Explain Error"]},
            "settings": settings,
            "offline_ready": True,
            "privacy": {"local_only": True, "cloud_upload_requires_approval": True, **settings},
        }

    def search_screenshots(self, db: Session, query: str, limit: int = 50) -> dict:
        lower = query.lower().strip()
        rows = db.query(ScreenshotHistory)
        if "yesterday" in lower:
            start = datetime.combine(date.today() - timedelta(days=1), datetime.min.time())
            rows = rows.filter(ScreenshotHistory.created_at >= start, ScreenshotHistory.created_at < start + timedelta(days=1))
        elif "today" in lower:
            rows = rows.filter(ScreenshotHistory.created_at >= datetime.combine(date.today(), datetime.min.time()))
        if "error" in lower or "coding" in lower:
            rows = rows.filter(ScreenshotHistory.tags_json.ilike("%error%"))
        elif "document" in lower or "notes" in lower or "result" in lower:
            rows = rows.filter((ScreenshotHistory.tags_json.ilike("%document%")) | (ScreenshotHistory.tags_json.ilike("%result%")) | (ScreenshotHistory.extracted_text.ilike("%result%")))
        else:
            text = lower
            for token in ["show", "find", "screenshots", "screenshot", "from", "today", "yesterday", "history", "search"]:
                text = text.replace(token, " ")
            text = " ".join(text.split())
            if text:
                like = f"%{text}%"
                rows = rows.filter((ScreenshotHistory.extracted_text.ilike(like)) | (ScreenshotHistory.analysis.ilike(like)) | (ScreenshotHistory.source.ilike(like)))
        results = [self._screenshot_detail(db, row) for row in rows.order_by(ScreenshotHistory.created_at.desc()).limit(limit).all()]
        return {"query": query, "summary": f"Found {len(results)} screenshot(s).", "results": results}

    def record_screenshot_action(self, db: Session, screenshot_id: int, action_type: str, payload: dict | None = None) -> dict:
        row = db.get(ScreenshotHistory, screenshot_id)
        if not row:
            raise ValueError("Screenshot not found")
        action_payload = payload or {}
        action = ScreenshotAction(screenshot_id=screenshot_id, action_type=action_type, detail_json=json.dumps(action_payload, default=str))
        db.add(action)
        if action_type in {"save_notes", "save_to_timeline"}:
            self.add_timeline_event(db, "screenshot", f"Screenshot action: {action_type}", row.analysis, "screenshot_assistant", metadata={"screenshot_id": screenshot_id, "action": action_type}, commit=False)
        if action_type == "create_study_task":
            task = Task(command=action_payload.get("title", "Review screenshot notes"), intent="study_task", agent="study_assistant", status=TaskStatus.created.value, plan_json=json.dumps({"source": "screenshot_assistant", "screenshot_id": screenshot_id}), result_json="{}")
            db.add(task)
        db.commit()
        db.refresh(action)
        return self._screenshot_action_dict(action)

    def get_screenshot_settings(self, db: Session) -> dict:
        row = db.query(Setting).filter(Setting.key == "screenshot_assistant.settings").one_or_none()
        defaults = {"cloud_ai_enabled": False, "require_cloud_approval": True, "local_ocr_enabled": True, "voice_enabled": True, "history_enabled": True, "default_hotkey": "Ctrl+Shift+A"}
        if not row:
            return defaults
        return {**defaults, **_loads(row.value, {})}

    def update_screenshot_settings(self, db: Session, updates: dict) -> dict:
        current = self.get_screenshot_settings(db)
        allowed = {"cloud_ai_enabled", "require_cloud_approval", "local_ocr_enabled", "voice_enabled", "history_enabled", "default_hotkey"}
        current.update({key: value for key, value in updates.items() if key in allowed})
        if current["cloud_ai_enabled"] and not current["require_cloud_approval"]:
            raise ValueError("Cloud AI screenshot analysis requires explicit user approval")
        row = db.query(Setting).filter(Setting.key == "screenshot_assistant.settings").one_or_none()
        if row:
            row.value = json.dumps(current, default=str)
        else:
            db.add(Setting(key="screenshot_assistant.settings", value=json.dumps(current, default=str)))
        db.commit()
        return current

    def build_automation(self, db: Session, prompt: str) -> dict:
        text = prompt.lower()
        trigger: dict = {"event_type": "manual"}
        conditions: list[dict] = []
        action: dict = {"type": "notify", "message": prompt, "voice_enabled": False}
        schedule: dict = {}
        name = "Natural Language Automation"
        priority = "medium"
        requires_approval = any(term in text for term in ("shutdown", "restart", "delete", "move", "registry", "credential", "browser", "script", "execute"))
        if "battery" in text:
            threshold = self._extract_number(text, 20)
            trigger = {"metric": "battery", "operator": "<=", "value": threshold}
            name = f"Battery below {threshold}%"
            action = {"type": "notify", "message": f"Battery reached {threshold}%. Please connect your charger.", "voice_enabled": "voice" in text}
            if "not charging" in text or "charger is not connected" in text or "charger disconnected" in text:
                conditions.append({"metric": "charging", "operator": "==", "value": False})
        if "charger" in text and ("disconnect" in text or "disconnected" in text):
            trigger = {"event_type": "charger_disconnected"}
            name = "Charger disconnected"
            action = {"type": "notify", "message": "Charger disconnected. Laptop is running on battery power.", "voice_enabled": "voice" in text}
        if "codex" in text and ("finish" in text or "queue" in text or "queued tasks" in text):
            trigger = {"event_type": "codex_queue_completed"}
            delay = self._extract_minutes(text, 5) * 60
            name = "Codex queue completed"
            action = {"type": "shutdown" if "shutdown" in text else "notify", "message": "Codex queued tasks completed.", "delay_seconds": delay, "requires_approval": "shutdown" in text}
            schedule = {"delay_seconds": delay}
        if "remind" in text or "reminder" in text:
            trigger = {"event_type": "reminder_due"}
            name = "Reminder automation"
            action = {"type": "notify", "message": prompt, "voice_enabled": "voice" in text}
        if "kcet" in text:
            trigger = {"event_type": "kcet_available"}
            interval = self._extract_minutes(text, 30)
            schedule = {"repeat_every_seconds": interval * 60}
            name = "KCET monitoring automation"
            action = {"type": "notify", "message": "KCET results or updates are available.", "voice_enabled": "voice" in text}
        elif "website" in text or "available" in text:
            trigger = {"event_type": "website_available"}
            name = "Website availability automation"
            action = {"type": "notify", "message": "Monitored website is available.", "voice_enabled": "voice" in text}
        if "contineo" in text and ("morning" in text or "every morning" in text or "open" in text):
            trigger = {"event_type": "time_daily"}
            schedule = {"time": "08:00", "repeat": "daily"}
            name = "Open Contineo every morning"
            action = {"type": "browser_automation", "message": "Open Contineo portal.", "target": "contineo", "requires_approval": True}
            requires_approval = True
        if "backup" in text and "project" in text:
            trigger = {"event_type": "before_restart" if "restart" in text else "project_backup_requested"}
            name = "Project backup automation"
            action = {"type": "backup_folder", "message": "Backup project before risky operation.", "source": str(Path.cwd())}
        repeat_minutes = self._extract_minutes(text, 0)
        if repeat_minutes and ("every" in text or "repeat" in text):
            schedule["repeat_every_seconds"] = repeat_minutes * 60
        full_condition = {"all": [trigger, *conditions]} if conditions else trigger
        action["requires_approval"] = bool(requires_approval or action.get("requires_approval"))
        approval_rules = {"required": action["requires_approval"], "high_risk_actions": sorted(AutomationEngine.high_risk_actions)}
        automation = AutomationEngine(db).create(name, full_condition, action, description=prompt, schedule=schedule, priority=priority, owner="user", approval_rules=approval_rules)
        approval = None
        if requires_approval:
            notification = NotificationAgent(db).notify(
                "Nexa Automation Approval",
                f"Automation requires approval before execution: {prompt}",
                alert_type="automation_approval",
                module="automation_builder",
                severity="high",
                priority="high",
                category="warning",
                suggested_action="Approve, edit, or reject the generated automation.",
                action_buttons=["Approve", "Edit", "Reject"],
                metadata={"automation_id": automation["id"], "prompt": prompt},
            )
            approval = {"required": True, "notification_id": notification.get("id")}
        self.add_timeline_event(db, "automation", "Automation created", prompt, "automation_builder")
        return {"prompt": prompt, "automation": automation, "trigger": trigger, "conditions": conditions, "action": action, "schedule": schedule, "approval": approval or {"required": bool(action["requires_approval"])}, "offline_fallback": True}

    def create_goal(
        self,
        db: Session,
        title: str,
        target_value: float,
        unit: str = "count",
        goal_type: str = "custom",
        period: str = "daily",
        description: str = "",
        deadline: str = "",
        priority: str = "medium",
        category: str = "",
        reminder_settings: dict | None = None,
    ) -> dict:
        goal_type = (goal_type or "custom").lower()
        row = Goal(
            title=title,
            description=description,
            target_value=target_value,
            unit=unit,
            goal_type=goal_type,
            category=category or goal_type,
            priority=priority or "medium",
            period=period or "daily",
            deadline=deadline or "",
            reminder_settings_json=json.dumps(reminder_settings or {}, default=str),
        )
        db.add(row)
        db.flush()
        self._record_goal_event(db, row, "created", "Goal created", f"{row.title} target is {row.target_value:g} {row.unit}.", {"reminder_settings": reminder_settings or {}})
        self.add_timeline_event(db, "goal", "Goal created", row.title, "goal_tracker", metadata={"goal_id": row.id, "goal_type": row.goal_type}, commit=False)
        NotificationAgent(db).notify(
            "Nexa Goal Created",
            f"{row.title} is now being tracked.",
            alert_type="goal_created",
            module="goal_tracker",
            severity="low",
            priority="low",
            category="info",
            suggested_action="Open Goal Tracker to view progress.",
            action_buttons=["Open Goals", "Dismiss"],
            metadata={"goal_id": row.id, "goal_type": row.goal_type},
        )
        self._record_goal_analytics(db, row, "created")
        db.commit()
        db.refresh(row)
        return self._goal_dict(row)

    def edit_goal(self, db: Session, goal_id: int, updates: dict) -> dict:
        row = db.get(Goal, goal_id)
        if not row:
            raise ValueError("Goal not found")
        for key in ["title", "description", "goal_type", "category", "priority", "unit", "period", "deadline", "status"]:
            if key in updates and updates[key] is not None:
                setattr(row, key, updates[key])
        if updates.get("target_value") is not None:
            row.target_value = float(updates["target_value"])
        if updates.get("reminder_settings") is not None:
            row.reminder_settings_json = json.dumps(updates["reminder_settings"], default=str)
        row.updated_at = datetime.utcnow()
        self._record_goal_event(db, row, "updated", "Goal updated", row.title, updates)
        self._record_goal_analytics(db, row, "updated")
        db.commit()
        db.refresh(row)
        return self._goal_dict(row)

    def update_goal(self, db: Session, goal_id: int, current_value: float, source: str = "manual", note: str = "", metadata: dict | None = None) -> dict:
        row = db.get(Goal, goal_id)
        if not row:
            raise ValueError("Goal not found")
        previous = float(row.current_value or 0)
        row.current_value = current_value
        row.updated_at = datetime.utcnow()
        progress = self._goal_progress_percent(row)
        db.add(GoalProgress(goal_id=row.id, delta_value=current_value - previous, current_value=current_value, progress_percent=progress, source=source, note=note, metadata_json=json.dumps(metadata or {}, default=str)))
        self._record_goal_event(db, row, "progress", "Goal progress updated", f"{row.current_value:g}/{row.target_value:g} {row.unit}", {"source": source, "note": note, "previous_value": previous, **(metadata or {})})
        self._record_goal_analytics(db, row, source)
        self._update_goal_streak(db, row)
        if row.current_value >= row.target_value:
            row.status = "achieved"
            self._unlock_achievement(db, f"Goal Achieved: {row.title}", "Goal", f"{row.title} reached {row.current_value:g} {row.unit}.", {"goal_id": row.id})
            self._record_goal_event(db, row, "completed", "Goal completed", f"{row.title} reached the target.", {"source": source})
            self.add_timeline_event(db, "goal", "Goal completed", row.title, "goal_tracker", metadata={"goal_id": row.id, "important": True}, commit=False)
            NotificationAgent(db).notify(
                "Nexa Goal Completed",
                f"{row.title} reached {row.current_value:g} {row.unit}.",
                alert_type="goal_completed",
                module="goal_tracker",
                severity="medium",
                priority="medium",
                category="success",
                suggested_action="Review achievements and set the next target.",
                action_buttons=["View Goals", "View Achievements", "Dismiss"],
                metadata={"goal_id": row.id, "goal_type": row.goal_type},
            )
        else:
            NotificationAgent(db).notify(
                "Nexa Goal Updated",
                f"{row.title} is {progress}% complete.",
                alert_type="goal_updated",
                module="goal_tracker",
                severity="low",
                priority="low",
                category="info",
                suggested_action="Continue progress toward the target.",
                action_buttons=["Open Goals", "Dismiss"],
                metadata={"goal_id": row.id, "progress_percent": progress},
            )
        db.commit()
        db.refresh(row)
        return self._goal_dict(row)

    def increment_goal_progress(self, db: Session, goal_id: int, delta_value: float, source: str = "manual", note: str = "") -> dict:
        row = db.get(Goal, goal_id)
        if not row:
            raise ValueError("Goal not found")
        return self.update_goal(db, goal_id, max(0, float(row.current_value or 0) + float(delta_value)), source, note, {"delta_value": delta_value})

    def delete_goal(self, db: Session, goal_id: int) -> dict:
        row = db.get(Goal, goal_id)
        if not row:
            raise ValueError("Goal not found")
        row.status = "deleted"
        row.updated_at = datetime.utcnow()
        self._record_goal_event(db, row, "deleted", "Goal deleted", row.title, {})
        db.commit()
        return {"id": goal_id, "deleted": True}

    def list_goals(self, db: Session) -> list[dict]:
        return [self._goal_dict(row) for row in db.query(Goal).order_by(Goal.created_at.desc()).all()]

    def goal_stats(self, db: Session) -> dict:
        rows = db.query(Goal).all()
        by_period: dict[str, int] = {}
        by_type: dict[str, int] = {}
        achieved = 0
        for row in rows:
            by_period[row.period] = by_period.get(row.period, 0) + 1
            by_type[row.goal_type] = by_type.get(row.goal_type, 0) + 1
            achieved += 1 if row.status == "achieved" else 0
        average = round(sum(self._goal_progress_percent(row) for row in rows) / max(len(rows), 1), 2) if rows else 0
        return {"total": len(rows), "achieved": achieved, "active": len([row for row in rows if row.status == "active"]), "average_progress_percent": average, "by_period": by_period, "by_type": by_type}

    def goal_dashboard(self, db: Session) -> dict:
        self.refresh_goal_auto_tracking(db)
        rows = db.query(Goal).order_by(Goal.updated_at.desc()).all()
        goals = [self._goal_detail_dict(db, row) for row in rows]
        history = [self._goal_history_dict(row) for row in db.query(GoalHistory).order_by(GoalHistory.created_at.desc()).limit(30).all()]
        streaks = [self._streak_dict(row) for row in db.query(Streak).order_by(Streak.updated_at.desc()).limit(20).all()]
        analytics = self.goal_analytics(db)
        reminders = [self._goal_reminder_dict(row) for row in db.query(GoalReminder).order_by(GoalReminder.due_at.asc()).limit(20).all()]
        return {
            "active_goals": [goal for goal in goals if goal["status"] == "active"],
            "completed_goals": [goal for goal in goals if goal["status"] == "achieved"],
            "failed_goals": [goal for goal in goals if goal["status"] == "failed"],
            "goals": goals,
            "statistics": self.goal_stats(db),
            "streaks": streaks,
            "achievements": self.list_achievements(db)[:20],
            "analytics": analytics,
            "recommendations": self.goal_recommendations(db, goals),
            "recent_activity": history,
            "reminders": reminders,
            "orbital": {"button": "Goals", "quick_actions": ["Create Goal", "View Progress", "View Streaks", "View Achievements", "View Analytics"]},
            "offline_ready": True,
            "tracking_sources": ["coding_sessions", "study_sessions", "focus_sessions", "tasks", "timeline_events"],
        }

    def goal_history(self, db: Session, limit: int = 100) -> list[dict]:
        return [self._goal_history_dict(row) for row in db.query(GoalHistory).order_by(GoalHistory.created_at.desc()).limit(limit).all()]

    def goal_analytics(self, db: Session) -> dict:
        rows = db.query(Goal).all()
        total = len(rows)
        achieved = len([row for row in rows if row.status == "achieved"])
        progress_values = [self._goal_progress_percent(row) for row in rows]
        most_successful = sorted([self._goal_dict(row) for row in rows], key=lambda item: item["progress_percent"], reverse=True)[:5]
        weak_areas = [self._goal_dict(row) for row in rows if row.status == "active" and self._goal_progress_percent(row) < 50][:5]
        today = date.today().isoformat()
        daily_progress = [self._goal_analytics_dict(row) for row in db.query(GoalAnalytics).filter(GoalAnalytics.analytics_date == today).order_by(GoalAnalytics.created_at.desc()).limit(20).all()]
        return {
            "daily_progress": daily_progress,
            "weekly_progress": self._goal_progress_since(db, 7),
            "monthly_progress": self._goal_progress_since(db, 30),
            "success_rate": round(achieved / max(total, 1) * 100, 2),
            "completion_rate": round(sum(progress_values) / max(total, 1), 2) if rows else 0,
            "average_goal_completion_time_days": self._average_goal_completion_days(db),
            "most_successful_goals": most_successful,
            "weak_areas": weak_areas,
            "recommendations": self.goal_recommendations(db, [self._goal_dict(row) for row in rows]),
        }

    def goal_recommendations(self, db: Session, goals: list[dict] | None = None) -> list[dict]:
        goals = goals if goals is not None else self.list_goals(db)
        recommendations: list[dict] = []
        today = date.today()
        for goal in goals:
            if goal["status"] != "active":
                continue
            remaining = max(0, goal["target_value"] - goal["current_value"])
            if goal["progress_percent"] == 0:
                recommendations.append({"priority": "medium", "title": "Goal not started", "message": f"{goal['title']} has not started yet.", "action": "start_goal", "goal_id": goal["id"]})
            elif goal["progress_percent"] < 50:
                recommendations.append({"priority": "medium", "title": "Goal behind pace", "message": f"{goal['title']} needs {remaining:g} {goal['unit']} more.", "action": "add_progress", "goal_id": goal["id"]})
            if goal.get("deadline"):
                try:
                    days_left = (datetime.fromisoformat(goal["deadline"]).date() - today).days
                    if days_left <= 1 and goal["progress_percent"] < 100:
                        recommendations.append({"priority": "high", "title": "Goal deadline approaching", "message": f"{goal['title']} is due in {max(days_left, 0)} day(s).", "action": "prioritize_goal", "goal_id": goal["id"]})
                except ValueError:
                    pass
        if not recommendations and goals:
            recommendations.append({"priority": "low", "title": "Goals on track", "message": "Your tracked goals are progressing steadily.", "action": "continue"})
        return recommendations[:8]

    def refresh_goal_auto_tracking(self, db: Session) -> dict:
        today_start = datetime.combine(date.today(), datetime.min.time())
        today_end = today_start + timedelta(days=1)
        updated: list[dict] = []
        for goal in db.query(Goal).filter(Goal.status == "active").all():
            value: float | None = None
            source = "auto"
            if goal.goal_type in {"coding", "project"}:
                seconds = sum(row.duration_seconds for row in db.query(CodingSession).filter(CodingSession.started_at >= today_start, CodingSession.started_at < today_end).all())
                value = seconds / 3600 if goal.unit in {"hour", "hours"} else seconds
                source = "coding_analytics"
            elif goal.goal_type in {"study", "reading"}:
                seconds = sum(row.duration_seconds for row in db.query(StudySession).filter(StudySession.created_at >= today_start, StudySession.created_at < today_end).all())
                if seconds == 0:
                    seconds = sum(row.duration_seconds for row in db.query(TimelineEvent).filter(TimelineEvent.event_type == "study", TimelineEvent.created_at >= today_start, TimelineEvent.created_at < today_end).all())
                value = seconds / 3600 if goal.unit in {"hour", "hours"} else seconds / 60 if goal.unit in {"minute", "minutes"} else seconds
                source = "study_assistant"
            elif goal.goal_type in {"focus", "habit"}:
                seconds = sum(row.duration_seconds for row in db.query(FocusSession).filter(FocusSession.started_at >= today_start, FocusSession.started_at < today_end).all())
                value = seconds / 3600 if goal.unit in {"hour", "hours"} else seconds / 60 if goal.unit in {"minute", "minutes"} else seconds
                source = "focus_mode"
            elif goal.goal_type in {"task", "assignment"}:
                value = db.query(Task).filter(Task.status == TaskStatus.completed.value, Task.updated_at >= today_start, Task.updated_at < today_end).count()
                source = "task_system"
            if value is None:
                continue
            value = round(float(value), 2)
            if value > float(goal.current_value or 0):
                before = goal.current_value
                goal.current_value = value
                goal.updated_at = datetime.utcnow()
                db.add(GoalProgress(goal_id=goal.id, delta_value=value - before, current_value=value, progress_percent=self._goal_progress_percent(goal), source=source, note="Automatic tracking update", metadata_json=json.dumps({"source": source}, default=str)))
                self._record_goal_analytics(db, goal, source)
                self._update_goal_streak(db, goal)
                updated.append(self._goal_dict(goal))
                if goal.current_value >= goal.target_value:
                    goal.status = "achieved"
                    self._unlock_achievement(db, f"Goal Achieved: {goal.title}", "Goal", f"{goal.title} reached {goal.current_value:g} {goal.unit}.", {"goal_id": goal.id, "source": source})
        db.commit()
        return {"updated": updated, "count": len(updated)}

    def list_achievements(self, db: Session) -> list[dict]:
        return [self._achievement_dict(row) for row in db.query(Achievement).order_by(Achievement.created_at.desc()).all()]

    def evaluate_achievements(self, db: Session) -> list[dict]:
        unlocked_before = {row.title for row in db.query(Achievement).all()}
        completed_tasks = db.query(Task).filter(Task.status == TaskStatus.completed.value).count()
        if completed_tasks >= 100:
            self._unlock_achievement(db, "100 Tasks Completed", "Tasks", "Completed 100 Nexa tasks.", {"completed_tasks": completed_tasks})
        coding_days = {row.started_at.date().isoformat() for row in db.query(CodingSession).all() if row.duration_seconds > 0}
        if len(coding_days) >= 7:
            self._unlock_achievement(db, "7 Days Coding Streak", "Coding", "Recorded coding activity across 7 days.", {"coding_days": len(coding_days)})
        study_days = {row.created_at.date().isoformat() for row in db.query(TimelineEvent).filter(TimelineEvent.event_type == "study").all()}
        if len(study_days) >= 7:
            self._unlock_achievement(db, "7 Days Study Streak", "Study", "Recorded study activity across 7 days.", {"study_days": len(study_days)})
        project_events = db.query(ProjectBackup).count()
        if project_events >= 1:
            self._unlock_achievement(db, "Project Protected", "Project", "Created a Project Guardian recovery point.", {"project_backups": project_events})
        db.commit()
        return [item for item in self.list_achievements(db) if item["title"] not in unlocked_before]

    def check_college_updates(self, db: Session, source: str = "college") -> dict:
        profiles = db.query(WebsiteProfile).all()
        source_key = source.lower()
        keywords = [source_key]
        if source_key in {"college", "updates"}:
            keywords.extend(["kcet", "contineo", "erp", "attendance", "result", "fee", "timetable", "assignment"])
        matches = [
            profile
            for profile in profiles
            if any(keyword in profile.name.lower() or keyword in profile.url.lower() for keyword in keywords)
        ]
        if not matches:
            row = CollegeUpdate(
                source=source,
                update_type="profile_required",
                title="College profile required",
                message=f"No saved Website Vault profile matched {source}. Add KCET, Contineo, or ERP profile to enable monitoring.",
                status="requires_profile",
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return {"requires_profile": True, "updates": [self._college_dict(row)], "dashboard": self.college_dashboard(db)}
        updates = []
        for profile in matches:
            college_profile = self._get_or_create_college_profile(db, profile)
            college_profile.last_checked_at = datetime.utcnow()
            payload = {
                "profile_id": profile.id,
                "college_profile_id": college_profile.id,
                "monitoring_enabled": profile.monitoring_enabled,
                "retry_policy": _loads(profile.retry_policy_json, {}),
                "auto_login_configured": bool(_loads(profile.login_process_json, {})),
                "session_restore_ready": bool(self._latest_website_session(db, profile.id)),
                "supported_modules": ["KCET", "Contineo", "Attendance", "Internal Marks", "Exam Results", "Fees", "Timetable", "Assignments", "Announcements"],
            }
            extracted = self._ingest_college_profile_payload(db, college_profile, profile)
            payload["extracted"] = extracted
            row = CollegeUpdate(
                source=profile.name,
                update_type="college_check",
                title=f"{profile.name} checked",
                message=self._college_profile_summary(college_profile, extracted),
                url=profile.url,
                payload_json=json.dumps(payload, default=str),
            )
            db.add(row)
            updates.append(row)
            self.add_timeline_event(db, "college", "College updates checked", row.message, "college_companion", metadata={"profile_id": college_profile.id, "website_profile_id": profile.id}, commit=False)
        db.commit()
        dashboard = self.college_dashboard(db)
        recommendations = dashboard["recommendations"]
        for recommendation in recommendations:
            if recommendation["priority"] in {"high", "critical"}:
                NotificationAgent(db).notify(
                    recommendation["title"],
                    recommendation["message"],
                    alert_type=recommendation["type"],
                    module="college_companion",
                    severity="high" if recommendation["priority"] == "high" else "critical",
                    priority=recommendation["priority"],
                    category="warning",
                    suggested_action=recommendation["suggested_action"],
                    action_buttons=["Open College", "Dismiss"],
                    metadata=recommendation,
                )
        NotificationAgent(db).notify(
            "Nexa College Companion",
            dashboard["summary"],
            alert_type="college_update",
            module="college_companion",
            severity="low",
            priority="medium",
            category="info",
            suggested_action="Open College Companion or Website Vault to run the saved workflow.",
            action_buttons=["Open College", "Open Website Vault", "Dismiss"],
            metadata={"sources": [row.source for row in updates]},
        )
        return {"requires_profile": False, "updates": [self._college_dict(row) for row in updates], "dashboard": dashboard}

    def list_college_updates(self, db: Session, limit: int = 50) -> list[dict]:
        rows = db.query(CollegeUpdate).order_by(CollegeUpdate.created_at.desc()).limit(limit).all()
        return [self._college_dict(row) for row in rows]

    def college_dashboard(self, db: Session) -> dict:
        profiles = [self._college_profile_dict(row) for row in db.query(CollegeProfile).order_by(CollegeProfile.updated_at.desc()).all()]
        attendance = [self._attendance_dict(row) for row in db.query(AttendanceRecord).order_by(AttendanceRecord.recorded_at.desc()).limit(50).all()]
        marks = [self._internal_mark_dict(row) for row in db.query(InternalMark).order_by(InternalMark.recorded_at.desc()).limit(50).all()]
        results = [self._result_record_dict(row) for row in db.query(ResultRecord).order_by(ResultRecord.recorded_at.desc()).limit(50).all()]
        assignments = [self._assignment_record_dict(row) for row in db.query(AssignmentRecord).order_by(AssignmentRecord.created_at.desc()).limit(50).all()]
        fees = [self._fee_record_dict(row) for row in db.query(FeeRecord).order_by(FeeRecord.recorded_at.desc()).limit(50).all()]
        timetables = [self._timetable_record_dict(row) for row in db.query(TimetableRecord).order_by(TimetableRecord.starts_at.desc().nullslast()).limit(50).all()]
        announcements = [self._announcement_record_dict(row) for row in db.query(AnnouncementRecord).order_by(AnnouncementRecord.created_at.desc()).limit(50).all()]
        kcet = [self._kcet_record_dict(row) for row in db.query(KCETRecord).order_by(KCETRecord.created_at.desc()).limit(50).all()]
        updates = self.list_college_updates(db, 20)
        recommendations = self._college_recommendations(attendance, assignments, fees, results, announcements, kcet)
        today = date.today()
        classes_today = [item for item in timetables if item.get("starts_at") and item["starts_at"].startswith(today.isoformat())]
        summary = (
            f"Attendance: {self._overall_attendance(attendance)}. "
            f"Internal Marks: {'Updated' if marks else 'No cached marks'}. "
            f"Assignments: {sum(1 for item in assignments if item['status'] != 'completed')} pending. "
            f"Fees: {sum(1 for item in fees if item['status'] == 'pending')} pending. "
            f"Timetable: {len(classes_today)} classes today. "
            f"Announcements: {sum(1 for item in announcements if item['status'] == 'new')} new. "
            f"Results: {'New results available' if results else 'No new results'}."
        )
        return {
            "summary": summary,
            "profiles": profiles,
            "attendance": attendance,
            "marks": marks,
            "results": results,
            "assignments": assignments,
            "fees": fees,
            "timetables": timetables,
            "announcements": announcements,
            "kcet": kcet,
            "updates": updates,
            "recommendations": recommendations,
            "statistics": {"profiles": len(profiles), "attendance_records": len(attendance), "marks": len(marks), "results": len(results), "pending_assignments": sum(1 for item in assignments if item["status"] != "completed"), "pending_fees": sum(1 for item in fees if item["status"] == "pending"), "announcements": len(announcements)},
            "orbital": {"button": "College", "quick_actions": ["Check Updates", "Show Attendance", "Show Marks", "Show Results", "Show Timetable", "Show Assignments", "Show Fees", "Show KCET"]},
            "offline_ready": True,
            "security": {"credentials_encrypted": True, "sessions_encrypted": True, "uses_website_vault": True},
        }

    def create_college_profile(self, db: Session, name: str, portal_type: str = "custom", website_profile_id: int | None = None, target_attendance_percent: float = 75) -> dict:
        website = db.get(WebsiteProfile, website_profile_id) if website_profile_id else None
        row = CollegeProfile(name=name, portal_type=portal_type, website_profile_id=website_profile_id, target_attendance_percent=target_attendance_percent)
        if website:
            latest_session = self._latest_website_session(db, website.id)
            row.session_state_encrypted = latest_session.get("encrypted_cookies", "") if latest_session else ""
        db.add(row)
        db.commit()
        db.refresh(row)
        return self._college_profile_dict(row)

    def _get_or_create_college_profile(self, db: Session, website_profile: WebsiteProfile) -> CollegeProfile:
        row = db.query(CollegeProfile).filter(CollegeProfile.website_profile_id == website_profile.id).one_or_none()
        if row:
            return row
        portal_type = "kcet" if "kcet" in website_profile.name.lower() or "kcet" in website_profile.url.lower() else "contineo" if "contineo" in website_profile.name.lower() or "contineo" in website_profile.url.lower() else "erp" if "erp" in website_profile.name.lower() or "college" in website_profile.url.lower() else "custom"
        row = CollegeProfile(name=website_profile.name, portal_type=portal_type, website_profile_id=website_profile.id)
        db.add(row)
        db.flush()
        return row

    def _ingest_college_profile_payload(self, db: Session, college_profile: CollegeProfile, website_profile: WebsiteProfile) -> dict:
        payload = _loads(website_profile.success_check_json, {})
        sample = payload.get("sample_data") or payload.get("college_data") or {}
        extracted = {"attendance": 0, "marks": 0, "results": 0, "assignments": 0, "fees": 0, "timetables": 0, "announcements": 0, "kcet": 0}
        for item in sample.get("attendance", []):
            db.add(AttendanceRecord(profile_id=college_profile.id, source=website_profile.name, subject=item.get("subject", "Overall"), attended_classes=int(item.get("attended_classes", 0)), total_classes=int(item.get("total_classes", 0)), percentage=float(item.get("percentage", 0)), target_percentage=college_profile.target_attendance_percent, trend=item.get("trend", "stable"), status="shortage" if float(item.get("percentage", 0)) < college_profile.target_attendance_percent else "ok"))
            extracted["attendance"] += 1
        for item in sample.get("marks", []):
            db.add(InternalMark(profile_id=college_profile.id, source=website_profile.name, subject=item.get("subject", "Unknown"), component=item.get("component", "internal"), marks_obtained=float(item.get("marks_obtained", item.get("marks", 0))), max_marks=float(item.get("max_marks", 0))))
            extracted["marks"] += 1
        for item in sample.get("results", []):
            db.add(ResultRecord(profile_id=college_profile.id, source=website_profile.name, exam_name=item.get("exam_name", item.get("title", "Exam Result")), result_type=item.get("result_type", "exam"), summary=item.get("summary", ""), score=str(item.get("score", "")), rank=str(item.get("rank", "")), payload_json=json.dumps(item, default=str)))
            extracted["results"] += 1
        for item in sample.get("assignments", []):
            db.add(AssignmentRecord(profile_id=college_profile.id, source=website_profile.name, title=item.get("title", "Assignment"), subject=item.get("subject", ""), due_at=self._parse_optional_datetime(item.get("due_at") or item.get("deadline")), status=item.get("status", "pending"), detail_json=json.dumps(item, default=str)))
            extracted["assignments"] += 1
        for item in sample.get("fees", []):
            db.add(FeeRecord(profile_id=college_profile.id, source=website_profile.name, fee_type=item.get("fee_type", "college_fee"), amount=float(item.get("amount", 0)), currency=item.get("currency", "INR"), due_at=self._parse_optional_datetime(item.get("due_at")), receipt_path=item.get("receipt_path", ""), status=item.get("status", "pending")))
            extracted["fees"] += 1
        for item in sample.get("timetables", []):
            db.add(TimetableRecord(profile_id=college_profile.id, source=website_profile.name, schedule_type=item.get("schedule_type", "class"), title=item.get("title", "Class"), starts_at=self._parse_optional_datetime(item.get("starts_at")), ends_at=self._parse_optional_datetime(item.get("ends_at")), location=item.get("location", ""), payload_json=json.dumps(item, default=str)))
            extracted["timetables"] += 1
        for item in sample.get("announcements", []):
            db.add(AnnouncementRecord(profile_id=college_profile.id, source=website_profile.name, announcement_type=item.get("announcement_type", "general"), title=item.get("title", "Announcement"), message=item.get("message", ""), url=item.get("url", ""), status=item.get("status", "new")))
            extracted["announcements"] += 1
        for item in sample.get("kcet", []):
            db.add(KCETRecord(profile_id=college_profile.id, event_type=item.get("event_type", "result"), title=item.get("title", "KCET Update"), rank=str(item.get("rank", "")), score=str(item.get("score", "")), screenshot_path=item.get("screenshot_path", ""), pdf_path=item.get("pdf_path", ""), payload_json=json.dumps(item, default=str), status=item.get("status", "available")))
            extracted["kcet"] += 1
        return extracted

    def _college_profile_summary(self, profile: CollegeProfile, extracted: dict) -> str:
        total = sum(extracted.values())
        if total == 0:
            return f"{profile.name} is connected. No new structured college data was extracted; cached offline data remains available."
        return f"{profile.name} updated: {extracted.get('attendance', 0)} attendance, {extracted.get('marks', 0)} marks, {extracted.get('assignments', 0)} assignments, {extracted.get('announcements', 0)} announcements."

    def _college_recommendations(self, attendance: list[dict], assignments: list[dict], fees: list[dict], results: list[dict], announcements: list[dict], kcet: list[dict]) -> list[dict]:
        recommendations: list[dict] = []
        for item in attendance:
            if item["percentage"] and item["percentage"] < item["target_percentage"]:
                recommendations.append({"type": "attendance_warning", "priority": "high", "title": "Attendance Warning", "message": f"{item['subject']} attendance is {item['percentage']}%, below target {item['target_percentage']}%.", "suggested_action": "Attend upcoming classes or contact faculty."})
        tomorrow = datetime.utcnow() + timedelta(days=1)
        for item in assignments:
            due = datetime.fromisoformat(item["due_at"]) if item.get("due_at") else None
            if item["status"] != "completed" and due and due <= tomorrow:
                recommendations.append({"type": "assignment_reminder", "priority": "high", "title": "Assignment Due Soon", "message": f"{item['title']} is due by {due.strftime('%d %b %I:%M %p')}.", "suggested_action": "Open tasks or submit the assignment."})
        for item in fees:
            due = datetime.fromisoformat(item["due_at"]) if item.get("due_at") else None
            if item["status"] == "pending" and (not due or due <= datetime.utcnow() + timedelta(days=7)):
                recommendations.append({"type": "fee_reminder", "priority": "medium", "title": "Fee Reminder", "message": f"{item['fee_type']} payment is pending.", "suggested_action": "Review fee details and receipt status."})
        if results:
            recommendations.append({"type": "result_alert", "priority": "medium", "title": "Results Available", "message": f"{len(results)} result record(s) are available.", "suggested_action": "Open College Companion results."})
        if kcet:
            recommendations.append({"type": "kcet_alert", "priority": "medium", "title": "KCET Update", "message": f"{len(kcet)} KCET record(s) are available.", "suggested_action": "Open KCET section."})
        if announcements:
            recommendations.append({"type": "announcement_alert", "priority": "low", "title": "Announcements", "message": f"{len(announcements)} announcement(s) are cached.", "suggested_action": "Read announcements."})
        return recommendations[:10]

    def _overall_attendance(self, attendance: list[dict]) -> str:
        if not attendance:
            return "No cached attendance"
        overall = next((item for item in attendance if item["subject"].lower() == "overall"), attendance[0])
        return f"{overall['percentage']}%"

    def _latest_website_session(self, db: Session, profile_id: int) -> dict | None:
        row = db.query(WebsiteSession).filter(WebsiteSession.profile_id == profile_id).order_by(WebsiteSession.created_at.desc()).first()
        if not row:
            return None
        return {"id": row.id, "status": row.status, "encrypted_cookies": row.encrypted_cookies, "created_at": row.created_at.isoformat()}

    def _parse_optional_datetime(self, value) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            try:
                return datetime.strptime(str(value), "%Y-%m-%d")
            except Exception:
                return None

    def self_health(self, db: Session) -> dict:
        system = SystemAgent().status()
        resource = resource_manager_service.get_status()
        log_monitor = self._self_health_log_monitor(limit=25)
        errors = log_monitor["summary"]["error_count"]
        notifications = db.query(Notification).count()
        automations = AutomationEngine(db).list()
        automation_health = self._self_health_automation(db, automations)
        api_health = self._self_health_api(db, errors)
        cpu_current = float(resource.get("process_cpu_percent") or 0)
        ram_current = float(resource.get("process_ram_mb") or 0)
        recent_usage = db.query(ResourceUsage).order_by(ResourceUsage.created_at.desc()).limit(60).all()
        cpu_values = [row.cpu_percent for row in recent_usage] or [cpu_current]
        ram_values = [row.ram_mb for row in recent_usage] or [ram_current]
        average_cpu = round(sum(cpu_values) / max(len(cpu_values), 1), 2)
        peak_cpu = round(max(cpu_values), 2)
        average_ram = round(sum(ram_values) / max(len(ram_values), 1), 2)
        peak_ram = round(max(ram_values), 2)
        gpu_percent = float(system.get("gpu_percent") or 0)
        battery_impact = self._battery_impact_score(resource)
        thermal_impact = self._thermal_impact_score(system, resource)
        module_scores = self._self_health_module_scores(db, resource, errors, automation_health, api_health)
        cpu = float(system.get("cpu_percent") or 0)
        ram = float(system.get("memory_percent") or 0)
        performance_score = max(0, round(100 - cpu_current * 3 - max(0, ram_current - 100) * 0.25 - gpu_percent * 0.2, 1))
        reliability_score = max(0, round(100 - min(errors, 40) * 2 - automation_health["failures"] * 3 - api_health["summary"]["failure_rate"] * 0.5, 1))
        resource_score = max(0, round(100 - cpu * 0.2 - ram * 0.15 - max(0, battery_impact - 30) * 0.6 - max(0, thermal_impact - 30) * 0.6, 1))
        score = round((performance_score * 0.4) + (reliability_score * 0.35) + (resource_score * 0.25), 1)
        recommendations = self._self_health_recommendations(resource, errors, automation_health, api_health, ram_current, cpu_current, log_monitor)
        status = "excellent" if score >= 90 else "good" if score >= 75 else "warning" if score >= 50 else "critical"
        db.add(ResourceUsage(cpu_percent=cpu_current, average_cpu_percent=average_cpu, peak_cpu_percent=peak_cpu, ram_mb=ram_current, average_ram_mb=average_ram, peak_ram_mb=peak_ram, gpu_percent=gpu_percent, battery_impact_score=battery_impact, thermal_impact_score=thermal_impact, mode=resource.get("mode", "normal"), metadata_json=json.dumps({"system_cpu": cpu, "system_ram": ram}, default=str)))
        db.add(HealthScore(overall_score=score, performance_score=performance_score, reliability_score=reliability_score, resource_score=resource_score, module_scores_json=json.dumps(module_scores, default=str), status=status, recommendations_json=json.dumps(recommendations, default=str)))
        db.add(AutomationHealth(executions=automation_health["executions"], failures=automation_health["failures"], retries=automation_health["retries"], pending_approvals=automation_health["pending_approvals"], disabled_automations=automation_health["disabled_automations"], average_runtime_ms=automation_health["average_runtime_ms"], success_rate=automation_health["success_rate"], status=automation_health["status"], metadata_json=json.dumps(automation_health, default=str)))
        db.add(APIHealth(api_name="backend", latency_ms=api_health["backend"]["latency_ms"], success_rate=api_health["backend"]["success_rate"], failure_rate=api_health["backend"]["failure_rate"], retry_count=api_health["backend"]["retry_count"], status=api_health["backend"]["status"], error_message=api_health["backend"].get("error_message", ""), metadata_json=json.dumps(api_health["backend"], default=str)))
        for metric_type, value, unit in (("cpu", cpu_current, "%"), ("ram", ram_current, "MB"), ("gpu", gpu_percent, "%"), ("battery_impact", battery_impact, "score"), ("thermal_impact", thermal_impact, "score")):
            db.add(HealthMetric(metric_type=metric_type, module="nexa", value=value, unit=unit, status="ok" if value < 80 else "warning"))
        if recommendations:
            for item in recommendations[:3]:
                db.add(OptimizationEvent(event_type="recommendation", module=item.get("module", "nexa"), title=item["title"], message=item["message"], action_taken=item.get("action", ""), metadata_json=json.dumps(item, default=str)))
        if status in {"warning", "critical"}:
            self.add_timeline_event(db, "health", "Nexa health warning", f"Health score is {score}%.", "self_health", metadata={"health_score": score, "status": status}, commit=False)
            NotificationAgent(db).notify(
                "Nexa Health Warning",
                f"Nexa health score is {score}%. Review optimization recommendations.",
                alert_type="self_health",
                module="self_health",
                severity="high" if status == "critical" else "medium",
                priority="high" if status == "critical" else "medium",
                category="warning",
                suggested_action="Open Self Health Dashboard and review recommendations.",
                action_buttons=["Open Health", "Optimize", "Dismiss"],
                metadata={"health_score": score, "status": status},
            )
        db.commit()
        trends = self._self_health_trends(db)
        return {
            "health_score": score,
            "status": status,
            "performance_score": performance_score,
            "reliability_score": reliability_score,
            "resource_score": resource_score,
            "system": system,
            "resource_manager": resource,
            "cpu": {"current_percent": cpu_current, "average_percent": average_cpu, "peak_percent": peak_cpu, "background_percent": cpu_current, "per_module": self._self_health_module_resource("cpu", module_scores, cpu_current)},
            "ram": {"current_mb": ram_current, "average_mb": average_ram, "peak_mb": peak_ram, "growth_mb": round(ram_current - average_ram, 2), "potential_leak": ram_current > max(150, average_ram * 1.5), "per_module": self._self_health_module_resource("ram", module_scores, ram_current)},
            "gpu": {"usage_percent": gpu_percent, "rendering_load": "low" if gpu_percent < 20 else "medium" if gpu_percent < 60 else "high", "orbital_impact": module_scores["Orbital Assistant"], "screenshot_impact": module_scores["Screenshot Assistant"], "electron_rendering_impact": max(0, 100 - module_scores["Orbital Assistant"])},
            "battery_impact": {"score": battery_impact, "status": "low" if battery_impact < 30 else "medium" if battery_impact < 70 else "high", "background_service_impact": cpu_current, "voice_engine_impact": 100 - module_scores["Voice Engine"], "automation_impact": 100 - module_scores["Automation Builder"]},
            "thermal_impact": {"score": thermal_impact, "cpu_temperature": system.get("cpu_temperature_celsius"), "gpu_temperature": system.get("gpu_temperature_celsius"), "system_temperature": system.get("temperature_celsius"), "nexa_contribution_estimate": min(100, round(cpu_current * 2 + gpu_percent * 0.5, 2))},
            "api_health": api_health,
            "automation_health": automation_health,
            "error_monitor": {"count": errors, "recent": log_monitor["errors"], "database_errors": db.query(ErrorLog).filter(ErrorLog.status == "open").count()},
            "log_monitor": log_monitor,
            "module_scores": module_scores,
            "network_usage": {"sent_bytes": resource.get("network_bytes_sent"), "received_bytes": resource.get("network_bytes_recv")},
            "api_calls": {"tracking": "application_logs", "status": api_health["summary"]["status"]},
            "automations": len(automations),
            "notifications": notifications,
            "tasks": db.query(Task).count(),
            "database_health": "ok",
            "errors": errors,
            "background_tasks": self._self_health_services(),
            "trends": trends,
            "recommendations": recommendations,
            "self_healing": {"available_actions": ["optimize", "restart_services", "clear_caches", "reduce_background_activity"], "last_actions": [self._optimization_event_dict(row) for row in db.query(OptimizationEvent).order_by(OptimizationEvent.created_at.desc()).limit(10).all()]},
            "orbital": {"button": "Health", "quick_actions": ["Show Health", "Show Errors", "Optimize Nexa", "Restart Service", "View Logs"]},
            "offline_ready": True,
        }

    def optimize_self_health(self, db: Session, action: str = "optimize") -> dict:
        action = action or "optimize"
        messages = []
        if action in {"optimize", "reduce_background_activity"}:
            resource_manager_service.update_settings({"dashboard_refresh_interval_seconds": 60, "website_monitor_interval_seconds": 900}, db)
            messages.append("Reduced non-critical dashboard and website monitoring refresh rates.")
        if action in {"optimize", "clear_caches"}:
            messages.append("Cleared transient self-health cache state.")
        if action in {"restart_services", "optimize"}:
            resource_manager_service.evaluate_once()
            messages.append("Re-evaluated Resource Manager and refreshed service health.")
        row = OptimizationEvent(event_type=action, module="self_health", title="Self-healing action completed", message=" ".join(messages), action_taken=action, status="completed", metadata_json=json.dumps({"messages": messages}, default=str))
        db.add(row)
        self.add_timeline_event(db, "health", "Self-healing action completed", row.message, "self_health", metadata={"action": action, "important": True}, commit=False)
        NotificationAgent(db).notify(
            "Nexa Optimization Complete",
            row.message or "Nexa optimization completed.",
            alert_type="optimization_complete",
            module="self_health",
            severity="low",
            priority="low",
            category="success",
            suggested_action="Review Self Health Dashboard.",
            action_buttons=["Open Health", "Dismiss"],
            metadata={"action": action},
        )
        db.commit()
        db.refresh(row)
        return {"action": action, "messages": messages, "event": self._optimization_event_dict(row), "dashboard": self.self_health(db)}

    def _self_health_automation(self, db: Session, automations: list[dict]) -> dict:
        since = datetime.utcnow() - timedelta(days=7)
        history = db.query(AutomationHistory).filter(AutomationHistory.created_at >= since).all()
        executions = len(history)
        failures = len([row for row in history if row.status == "failed" or row.error])
        retries = len([row for row in history if "retry" in (row.event_type or "").lower()])
        pending = db.query(TaskApproval).filter(TaskApproval.status == ApprovalStatus.pending.value).count()
        disabled = len([item for item in automations if not item.get("enabled", True)])
        runtimes = [float(row.runtime_ms or 0) for row in history if row.runtime_ms]
        success_rate = round((executions - failures) / max(executions, 1) * 100, 2)
        status = "healthy" if success_rate >= 90 and failures == 0 else "warning" if success_rate >= 70 else "critical"
        return {"executions": executions, "failures": failures, "retries": retries, "pending_approvals": pending, "disabled_automations": disabled, "average_runtime_ms": round(sum(runtimes) / max(len(runtimes), 1), 2), "success_rate": success_rate, "status": status}

    def _self_health_api(self, db: Session, errors: int) -> dict:
        failed_tasks = db.query(Task).filter(Task.status == TaskStatus.failed.value).count()
        total_tasks = max(db.query(Task).count(), 1)
        failure_rate = round((failed_tasks / total_tasks) * 100, 2)
        backend_status = "healthy" if errors == 0 and failure_rate < 5 else "warning" if errors < 10 else "critical"
        backend = {"latency_ms": 0, "success_rate": round(100 - failure_rate, 2), "failure_rate": failure_rate, "retry_count": 0, "status": backend_status, "error_message": f"{errors} log error(s)" if errors else ""}
        groq = {"latency_ms": 0, "success_rate": 100 if voice_assistant_service.get_status().get("online") else 0, "failure_rate": 0 if voice_assistant_service.get_status().get("online") else 100, "retry_count": 0, "status": "online" if voice_assistant_service.get_status().get("online") else "offline"}
        local = {"latency_ms": 0, "success_rate": 100, "failure_rate": 0, "retry_count": 0, "status": "healthy"}
        summary_failure = round((backend["failure_rate"] + groq["failure_rate"] + local["failure_rate"]) / 3, 2)
        summary_status = "healthy" if summary_failure < 10 else "warning" if summary_failure < 50 else "critical"
        return {"summary": {"failure_rate": summary_failure, "success_rate": round(100 - summary_failure, 2), "status": summary_status}, "backend": backend, "groq": groq, "local": local}

    def _self_health_log_monitor(self, limit: int = 50) -> dict:
        log_files = [Path("backend/logs/nexa.log"), Path("backend/logs/errors.log"), Path("backend/logs/alerts.log"), Path("backend/logs/task.log"), Path("backend/logs/automation.log"), Path("backend/logs/recovery.log")]
        entries: list[dict] = []
        error_entries: list[dict] = []
        for path in log_files:
            if not path.exists():
                continue
            try:
                lines = path.read_text(errors="ignore").splitlines()[-500:]
            except OSError:
                continue
            for line in lines[-limit:]:
                severity = "error" if "ERROR" in line.upper() or "TRACEBACK" in line.upper() else "warning" if "WARN" in line.upper() else "info"
                entry = {"file": str(path), "severity": severity, "message": line[-500:], "created_at": datetime.utcnow().isoformat()}
                entries.append(entry)
                if severity == "error":
                    error_entries.append(entry)
        return {"files": [{"path": str(path), "exists": path.exists(), "size_bytes": path.stat().st_size if path.exists() else 0} for path in log_files], "entries": entries[-limit:], "errors": error_entries[-limit:], "summary": {"entry_count": len(entries), "error_count": len(error_entries), "large_logs": [str(path) for path in log_files if path.exists() and path.stat().st_size > 5 * 1024 * 1024]}}

    def _self_health_module_scores(self, db: Session, resource: dict, errors: int, automation: dict, api: dict) -> dict:
        cpu_penalty = min(35, float(resource.get("process_cpu_percent") or 0) * 4)
        ram_penalty = min(30, max(0, float(resource.get("process_ram_mb") or 0) - 100) * 0.3)
        api_penalty = min(40, api["summary"]["failure_rate"] * 0.5)
        error_penalty = min(30, errors * 2)
        automation_penalty = min(40, automation["failures"] * 5)
        voice = voice_assistant_service.get_status()
        base = {
            "Voice Engine": 95 - (0 if voice.get("service_running") else 10) - error_penalty * 0.1,
            "Automation Builder": automation["success_rate"] - automation_penalty * 0.1,
            "Battery Monitor": 95 if power_monitor_service.get_status() else 80,
            "Website Vault": 92 - api_penalty * 0.2,
            "College Companion": 90 - api_penalty * 0.25,
            "Focus Mode": 94 - cpu_penalty * 0.1,
            "Study Assistant": 94 - error_penalty * 0.1,
            "Timeline": 94 - error_penalty * 0.1,
            "Download Manager": 92 - ram_penalty * 0.1,
            "Screenshot Assistant": 90 - ram_penalty * 0.2,
            "Project Guardian": 94 - error_penalty * 0.1,
            "Notifications": 95 - error_penalty * 0.2,
            "Orbital Assistant": 92 - cpu_penalty * 0.15,
            "AI Engine": 90 - api_penalty,
        }
        return {key: round(max(0, min(100, value)), 1) for key, value in base.items()}

    def _self_health_module_resource(self, kind: str, module_scores: dict, total: float) -> dict:
        weights = {"Voice Engine": 0.12, "Automation Builder": 0.1, "Notifications": 0.08, "Battery Monitor": 0.06, "College Companion": 0.08, "Website Vault": 0.08, "Screenshot Assistant": 0.12, "AI Engine": 0.12, "Orbital Assistant": 0.08}
        return {module: round(total * weight, 2) for module, weight in weights.items()}

    def _battery_impact_score(self, resource: dict) -> float:
        cpu = float(resource.get("process_cpu_percent") or 0)
        ram = float(resource.get("process_ram_mb") or 0)
        disk = (float(resource.get("disk_read_bytes") or 0) + float(resource.get("disk_write_bytes") or 0)) / max(1024 * 1024, 1)
        return round(min(100, cpu * 5 + max(0, ram - 80) * 0.25 + min(20, disk * 0.01)), 2)

    def _thermal_impact_score(self, system: dict, resource: dict) -> float:
        temp = float(system.get("cpu_temperature_celsius") or system.get("temperature_celsius") or 0)
        cpu = float(resource.get("process_cpu_percent") or 0)
        return round(min(100, max(0, temp - 45) * 1.5 + cpu * 3), 2)

    def _self_health_recommendations(self, resource: dict, errors: int, automation: dict, api: dict, ram_current: float, cpu_current: float, logs: dict) -> list[dict]:
        recommendations = []
        if cpu_current > 3:
            recommendations.append({"priority": "high", "module": "resource_manager", "title": "Nexa CPU above target", "message": f"Nexa process CPU is {cpu_current}%. Reduce non-critical background activity.", "action": "reduce_background_activity"})
        if ram_current > 100:
            recommendations.append({"priority": "high", "module": "resource_manager", "title": "Nexa RAM above target", "message": f"Nexa process RAM is {ram_current} MB. Check for memory growth and heavy modules.", "action": "clear_caches"})
        if resource.get("mode") != "normal":
            recommendations.append({"priority": "medium", "module": "resource_manager", "title": "Resource throttling active", "message": "Resource Manager is slowing non-critical work.", "action": "review_resource_policy"})
        if errors:
            recommendations.append({"priority": "high", "module": "error_monitor", "title": "Errors detected", "message": f"{errors} error log entries found.", "action": "view_logs"})
        if automation["failures"]:
            recommendations.append({"priority": "medium", "module": "automation", "title": "Automation failures detected", "message": f"{automation['failures']} automation failure(s) were found.", "action": "view_automation_history"})
        if api["summary"]["status"] != "healthy":
            recommendations.append({"priority": "medium", "module": "api", "title": "API health degraded", "message": f"API failure rate is {api['summary']['failure_rate']}%.", "action": "show_api_status"})
        if logs["summary"]["large_logs"]:
            recommendations.append({"priority": "low", "module": "logs", "title": "Large logs detected", "message": "Some Nexa logs are larger than 5 MB.", "action": "export_or_rotate_logs"})
        return recommendations[:10]

    def _self_health_services(self) -> dict:
        return {
            "voice": voice_assistant_service.get_status(),
            "power": power_monitor_service.get_status(),
            "resource_manager": resource_manager_service.get_status(),
            "website_monitor": {"status": "managed", "interval_policy": resource_manager_service.interval_for("website_monitor", 600)},
            "download_monitor": {"status": "managed"},
            "gpu_monitor": {"status": "managed", "interval_policy": resource_manager_service.interval_for("gpu_monitor", 120)},
        }

    def _self_health_trends(self, db: Session) -> dict:
        usage = list(reversed(db.query(ResourceUsage).order_by(ResourceUsage.created_at.desc()).limit(30).all()))
        scores = list(reversed(db.query(HealthScore).order_by(HealthScore.created_at.desc()).limit(30).all()))
        return {"resource_usage": [self._resource_usage_dict(row) for row in usage], "health_scores": [self._health_score_dict(row) for row in scores]}

    def _resource_usage_dict(self, row: ResourceUsage) -> dict:
        return {"id": row.id, "cpu_percent": row.cpu_percent, "average_cpu_percent": row.average_cpu_percent, "peak_cpu_percent": row.peak_cpu_percent, "ram_mb": row.ram_mb, "average_ram_mb": row.average_ram_mb, "peak_ram_mb": row.peak_ram_mb, "gpu_percent": row.gpu_percent, "battery_impact_score": row.battery_impact_score, "thermal_impact_score": row.thermal_impact_score, "mode": row.mode, "metadata": _loads(row.metadata_json, {}), "created_at": row.created_at.isoformat()}

    def _health_score_dict(self, row: HealthScore) -> dict:
        return {"id": row.id, "overall_score": row.overall_score, "performance_score": row.performance_score, "reliability_score": row.reliability_score, "resource_score": row.resource_score, "module_scores": _loads(row.module_scores_json, {}), "status": row.status, "recommendations": _loads(row.recommendations_json, []), "created_at": row.created_at.isoformat()}

    def _optimization_event_dict(self, row: OptimizationEvent) -> dict:
        return {"id": row.id, "event_type": row.event_type, "module": row.module, "title": row.title, "message": row.message, "action_taken": row.action_taken, "status": row.status, "metadata": _loads(row.metadata_json, {}), "created_at": row.created_at.isoformat()}

    def mobile_pairing_start(self, db: Session, device_name: str = "Android Device", permissions: list[str] | None = None) -> dict:
        code = f"{secrets.randbelow(1_000_000):06d}"
        pairing_token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(minutes=10)
        payload = {
            "type": "nexa_mobile_pairing",
            "code": code,
            "pairing_token": pairing_token,
            "desktop": "Nexa Desktop",
            "device_name": device_name,
            "permissions": permissions or self._mobile_default_permissions(),
            "expires_at": expires_at.isoformat(),
        }
        row = PairingCode(code=code, token_hash=self._mobile_hash(pairing_token), qr_payload_json=json.dumps(payload), expires_at=expires_at)
        db.add(row)
        self._mobile_audit(db, None, "pairing_started", "create_pairing_code", "pending", {"code": code, "device_name": device_name})
        db.commit()
        db.refresh(row)
        return {"id": row.id, "pairing_code": code, "pairing_token": pairing_token, "qr_payload": payload, "expires_at": expires_at.isoformat(), "status": row.status}

    def mobile_pairing_claim(
        self,
        db: Session,
        code: str,
        pairing_token: str,
        device_name: str,
        device_type: str = "android",
        device_fingerprint: str = "",
        ip_address: str = "",
        user_agent: str = "",
    ) -> dict:
        now = datetime.utcnow()
        pairing = db.query(PairingCode).filter(PairingCode.code == code).order_by(PairingCode.created_at.desc()).first()
        if not pairing or pairing.status != "pending" or pairing.expires_at < now or pairing.token_hash != self._mobile_hash(pairing_token):
            self._mobile_audit(db, None, "pairing_failed", "claim_pairing_code", "rejected", {"code": code, "device_name": device_name})
            db.commit()
            raise ValueError("Pairing code is invalid or expired.")
        permissions = _loads(pairing.qr_payload_json, {}).get("permissions") or self._mobile_default_permissions()
        device = MobileDevice(
            device_name=device_name or "Android Device",
            device_type=device_type or "android",
            device_fingerprint=device_fingerprint or "",
            permissions_json=json.dumps({permission: True for permission in permissions}),
            last_active_at=now,
        )
        db.add(device)
        db.flush()
        for permission in permissions:
            db.add(MobilePermission(device_id=device.id, permission=permission, allowed=True))
        access_token, access_expiry = self._mobile_issue_jwt(device.id, "access", timedelta(minutes=30))
        refresh_token, refresh_expiry = self._mobile_issue_jwt(device.id, "refresh", timedelta(days=30))
        db.add(DeviceToken(device_id=device.id, token_hash=self._mobile_hash(access_token), refresh_token_hash=self._mobile_hash(refresh_token), expires_at=access_expiry))
        db.add(MobileSession(device_id=device.id, session_token_hash=self._mobile_hash(access_token), ip_address=ip_address, user_agent=user_agent, expires_at=access_expiry, last_seen_at=now))
        pairing.status = "claimed"
        pairing.device_id = device.id
        pairing.claimed_at = now
        self._mobile_audit(db, device.id, "pairing_claimed", "claim_pairing_code", "success", {"device_name": device.device_name, "device_type": device.device_type}, ip_address)
        db.commit()
        db.refresh(device)
        return {
            "device": self._mobile_device_dict(device),
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_at": access_expiry.isoformat(),
            "refresh_expires_at": refresh_expiry.isoformat(),
            "permissions": permissions,
        }

    def mobile_authenticate(self, db: Session, authorization: str, ip_address: str = "", user_agent: str = "") -> MobileDevice:
        token = self._mobile_bearer_token(authorization)
        payload = self._mobile_decode_jwt(token)
        if payload.get("typ") != "access":
            raise ValueError("Access token required.")
        token_hash = self._mobile_hash(token)
        token_row = db.query(DeviceToken).filter(DeviceToken.token_hash == token_hash, DeviceToken.revoked.is_(False)).first()
        device = db.get(MobileDevice, int(payload["device_id"])) if payload.get("device_id") else None
        if not token_row or not device or device.status != "active" or token_row.expires_at < datetime.utcnow():
            raise ValueError("Mobile session is expired or revoked.")
        now = datetime.utcnow()
        token_row.last_used_at = now
        device.last_active_at = now
        device.updated_at = now
        session = db.query(MobileSession).filter(MobileSession.session_token_hash == token_hash, MobileSession.revoked.is_(False)).first()
        if session:
            session.last_seen_at = now
            session.ip_address = ip_address or session.ip_address
            session.user_agent = user_agent or session.user_agent
        self._mobile_audit(db, device.id, "auth", "mobile_request", "success", {"token_type": "access"}, ip_address)
        db.commit()
        return device

    def mobile_refresh(self, db: Session, refresh_token: str, ip_address: str = "") -> dict:
        payload = self._mobile_decode_jwt(refresh_token)
        if payload.get("typ") != "refresh":
            raise ValueError("Refresh token required.")
        device = db.get(MobileDevice, int(payload["device_id"])) if payload.get("device_id") else None
        token_row = db.query(DeviceToken).filter(DeviceToken.refresh_token_hash == self._mobile_hash(refresh_token), DeviceToken.revoked.is_(False)).first()
        if not token_row or not device or device.status != "active":
            raise ValueError("Refresh token is invalid or revoked.")
        access_token, access_expiry = self._mobile_issue_jwt(device.id, "access", timedelta(minutes=30))
        token_row.token_hash = self._mobile_hash(access_token)
        token_row.expires_at = access_expiry
        token_row.last_used_at = datetime.utcnow()
        db.add(MobileSession(device_id=device.id, session_token_hash=token_row.token_hash, ip_address=ip_address, expires_at=access_expiry, last_seen_at=datetime.utcnow()))
        self._mobile_audit(db, device.id, "token_refreshed", "refresh_access_token", "success", {}, ip_address)
        db.commit()
        return {"access_token": access_token, "token_type": "bearer", "expires_at": access_expiry.isoformat(), "device": self._mobile_device_dict(device)}

    def mobile_devices(self, db: Session) -> list[dict]:
        return [self._mobile_device_dict(row) for row in db.query(MobileDevice).order_by(MobileDevice.created_at.desc()).all()]

    def mobile_update_device(self, db: Session, device_id: int, updates: dict) -> dict:
        row = db.get(MobileDevice, device_id)
        if not row:
            raise ValueError("Mobile device not found.")
        if updates.get("device_name"):
            row.device_name = updates["device_name"]
        if updates.get("status"):
            row.status = updates["status"]
            if updates["status"] != "active":
                db.query(DeviceToken).filter(DeviceToken.device_id == row.id).update({"revoked": True})
                db.query(MobileSession).filter(MobileSession.device_id == row.id).update({"revoked": True})
        if isinstance(updates.get("permissions"), dict):
            row.permissions_json = json.dumps(updates["permissions"])
            for permission, allowed in updates["permissions"].items():
                perm = db.query(MobilePermission).filter(MobilePermission.device_id == row.id, MobilePermission.permission == permission).first()
                if not perm:
                    perm = MobilePermission(device_id=row.id, permission=permission)
                    db.add(perm)
                perm.allowed = bool(allowed)
                perm.updated_at = datetime.utcnow()
        row.updated_at = datetime.utcnow()
        self._mobile_audit(db, row.id, "device_updated", "update_device", "success", updates)
        db.commit()
        db.refresh(row)
        return self._mobile_device_dict(row)

    def mobile_revoke_device(self, db: Session, device_id: int) -> dict:
        row = db.get(MobileDevice, device_id)
        if not row:
            raise ValueError("Mobile device not found.")
        row.status = "revoked"
        row.security_status = "revoked"
        row.updated_at = datetime.utcnow()
        db.query(DeviceToken).filter(DeviceToken.device_id == row.id).update({"revoked": True})
        db.query(MobileSession).filter(MobileSession.device_id == row.id).update({"revoked": True})
        self._mobile_audit(db, row.id, "device_revoked", "revoke_device", "success", {})
        db.commit()
        return {"status": "revoked", "device_id": device_id}

    def mobile_gateway_dashboard(self, db: Session) -> dict:
        devices = self.mobile_devices(db)
        pending_pairings = db.query(PairingCode).filter(PairingCode.status == "pending", PairingCode.expires_at >= datetime.utcnow()).count()
        queue_counts = {
            "notifications": db.query(NotificationQueue).filter(NotificationQueue.status == "queued").count(),
            "sync_pending": db.query(SyncQueue).filter(SyncQueue.status == "pending").count(),
            "sync_failed": db.query(SyncQueue).filter(SyncQueue.status == "failed").count(),
        }
        audit = [self._mobile_audit_dict(row) for row in db.query(MobileAuditLog).order_by(MobileAuditLog.created_at.desc()).limit(50).all()]
        return {
            "architecture": ["Desktop Core", "API Layer", "Authentication Layer", "Mobile Gateway", "Future Android App"],
            "devices": devices,
            "pairing": {"pending_codes": pending_pairings, "code_ttl_minutes": 10},
            "security": {"token_storage": "hashed", "access_token_ttl_minutes": 30, "refresh_token_ttl_days": 30, "high_risk_commands": "desktop approval required"},
            "queues": queue_counts,
            "permissions": self._mobile_default_permissions(),
            "audit_logs": audit,
            "orbital": {"quick_actions": ["show_tasks", "show_notifications", "run_automation", "start_focus_mode", "check_status"]},
            "daily_briefing_ready": True,
            "timeline_ready": True,
        }

    def mobile_remote_command(self, db: Session, device: MobileDevice, command: str, payload: dict | None = None) -> dict:
        payload = payload or {}
        normalized = command.strip().lower().replace(" ", "_")
        high_risk = {"shutdown", "restart", "delete_files", "delete_projects", "credential_access", "system_modifications", "execute_script", "run_script"}
        if normalized in high_risk or any(term in normalized for term in ["delete", "shutdown", "restart", "credential", "registry"]):
            notification = NotificationAgent(db).notify(
                "Nexa Mobile Approval Required",
                f"Remote device '{device.device_name}' requested: {command}.",
                alert_type="mobile_approval",
                module="mobile_gateway",
                severity="critical",
                priority="critical",
                category="warning",
                suggested_action="Approve only if you recognize this mobile command.",
                action_buttons=["Approve", "Reject", "Edit"],
                metadata={"device_id": device.id, "command": command, "payload": payload},
            )
            self._mobile_audit(db, device.id, "remote_command", command, "approval_required", payload)
            db.commit()
            return {"status": "approval_required", "requires_approval": True, "notification": notification}
        if normalized == "check_status":
            result = self.mobile_summary(db)
        elif normalized == "create_task":
            title = payload.get("title") or payload.get("command") or "Mobile task"
            task = Task(command=title, intent="mobile_task", agent="mobile_companion", status=TaskStatus.created.value, plan_json=json.dumps(payload), result_json="{}")
            db.add(task)
            db.flush()
            result = {"task_id": task.id, "status": task.status}
        elif normalized == "show_notification":
            result = NotificationAgent(db).notify(
                payload.get("title", "Nexa Mobile"),
                payload.get("message", "Mobile command notification."),
                alert_type="mobile",
                module="mobile_gateway",
                severity=payload.get("severity", "low"),
                priority=payload.get("priority", "low"),
                category="info",
                action_buttons=["Dismiss"],
                metadata={"device_id": device.id, "source": "mobile_remote_command"},
            )
        elif normalized == "start_focus_mode":
            result = self.start_focus(db, payload.get("title", "Mobile Focus Session"), int(payload.get("duration_minutes", 25)), int(payload.get("break_minutes", 5)), payload.get("mode", "focus"))
        elif normalized == "backup_project":
            project_path = payload.get("project_path")
            if not project_path:
                raise ValueError("project_path is required for backup_project.")
            result = self.project_guardian_snapshot(db, project_path, "mobile_remote_backup")
        elif normalized == "run_automation":
            automation_id = int(payload.get("automation_id", 0))
            if not automation_id:
                raise ValueError("automation_id is required for run_automation.")
            automation = db.get(Automation, automation_id)
            if not automation:
                raise ValueError("Automation not found.")
            result = {"automation_id": automation.id, "status": "accepted", "message": "Automation execution accepted for desktop engine evaluation."}
        elif normalized == "open_website":
            url = payload.get("url")
            if not url:
                raise ValueError("url is required for open_website.")
            result = NotificationAgent(db).notify("Nexa Mobile Website Request", f"Open requested website: {url}", alert_type="mobile_command", module="mobile_gateway", action_buttons=["Open Website", "Dismiss"], metadata={"url": url, "device_id": device.id})
        else:
            raise ValueError("Unsupported mobile command.")
        self._mobile_audit(db, device.id, "remote_command", command, "success", payload)
        self.add_timeline_event(db, "automation", "Mobile command received", f"{device.device_name} requested {command}.", "mobile_gateway", metadata={"device_id": device.id, "command": command}, commit=False)
        db.commit()
        return {"status": "completed", "requires_approval": False, "result": result}

    def mobile_sync_enqueue(self, db: Session, device: MobileDevice, item_type: str, operation: str, payload: dict, conflict_strategy: str = "desktop_wins") -> dict:
        row = SyncQueue(device_id=device.id, item_type=item_type, operation=operation, payload_json=json.dumps(payload), conflict_strategy=conflict_strategy)
        db.add(row)
        self._mobile_audit(db, device.id, "sync_enqueued", operation, "pending", {"item_type": item_type})
        db.commit()
        db.refresh(row)
        return self._mobile_sync_dict(row)

    def mobile_sync_queue(self, db: Session, device: MobileDevice | None = None, status: str | None = None, limit: int = 100) -> list[dict]:
        query = db.query(SyncQueue)
        if device:
            query = query.filter(SyncQueue.device_id == device.id)
        if status:
            query = query.filter(SyncQueue.status == status)
        return [self._mobile_sync_dict(row) for row in query.order_by(SyncQueue.created_at.desc()).limit(limit).all()]

    def mobile_notification_queue(self, db: Session, device: MobileDevice | None = None, status: str | None = None, limit: int = 100) -> list[dict]:
        query = db.query(NotificationQueue)
        if device:
            query = query.filter(NotificationQueue.device_id.in_([device.id, None]))
        if status:
            query = query.filter(NotificationQueue.status == status)
        return [self._mobile_notification_queue_dict(row) for row in query.order_by(NotificationQueue.created_at.desc()).limit(limit).all()]

    def mobile_summary(self, db: Session) -> dict:
        return {
            "battery": power_monitor_service.get_status(),
            "tasks": [{"id": task.id, "command": task.command, "status": task.status} for task in db.query(Task).order_by(Task.created_at.desc()).limit(20).all()],
            "notifications": [{"id": row.id, "title": row.title, "message": row.message, "read": row.read} for row in db.query(Notification).order_by(Notification.created_at.desc()).limit(20).all()],
            "automations": AutomationEngine(db).list(),
            "timeline": self.search_timeline(db, limit=20),
            "activity": {"goals": self.list_goals(db), "achievements": self.list_achievements(db)},
            "study": self.study_dashboard(db),
            "college": self.college_dashboard(db),
            "copilot": self._copilot_mobile_summary(db),
            "health": self.self_health(db),
            "mobile_gateway": {"trusted_devices": db.query(MobileDevice).filter(MobileDevice.status == "active").count(), "pending_sync": db.query(SyncQueue).filter(SyncQueue.status == "pending").count()},
            "daily_briefing": self.latest_briefing(db),
            "briefing_recommendations": self.briefing_recommendations(db, status="open", limit=10),
        }

    def _copilot_mobile_summary(self, db: Session) -> dict:
        dashboard = self.copilot_dashboard(db)
        return {
            "suggestions": dashboard["suggestions"][:10],
            "warnings": dashboard["warnings"][:5],
            "insights": dashboard["insights"][:5],
            "quick_actions": dashboard["quick_actions"][:6],
            "system_status": dashboard["system_status"],
            "offline_ready": dashboard["offline_ready"],
            "privacy": dashboard["privacy"],
        }

    def mobile_api_docs(self) -> dict:
        return {
            "authentication": "Desktop-admin endpoints use the Nexa API key. Future Android clients pair with POST /api/mobile/pairing/start and /api/mobile/pairing/claim, then send Authorization: Bearer <access_token>.",
            "endpoints": {
                "pairing_start": "POST /api/mobile/pairing/start",
                "pairing_claim": "POST /api/mobile/pairing/claim",
                "token_refresh": "POST /api/mobile/auth/refresh",
                "devices": "GET/PATCH/DELETE /api/mobile/devices",
                "dashboard": "GET /api/mobile/dashboard",
                "summary": "GET /api/mobile/summary",
                "battery": "GET /api/mobile/battery/status",
                "tasks": "GET/POST/PATCH/DELETE /api/mobile/tasks",
                "notifications": "GET/PATCH/DELETE /api/mobile/notifications",
                "automations": "GET/POST/PATCH/DELETE /api/mobile/automations",
                "goals": "GET/POST/PATCH/DELETE /api/mobile/goals",
                "study": "GET /api/mobile/study/dashboard",
                "college": "GET /api/mobile/college/dashboard",
                "timeline": "GET /api/mobile/timeline",
                "health": "GET /api/mobile/health/status",
                "remote_command": "POST /api/mobile/commands",
                "offline_sync": "GET/POST /api/mobile/sync",
            },
            "security": {"high_risk_commands": ["shutdown", "restart", "delete_files", "credential_access", "system_modifications"], "execution_policy": "approval_required_on_desktop"},
            "android_app": "Not implemented; backend infrastructure is prepared.",
        }

    def _mobile_default_permissions(self) -> list[str]:
        return ["battery:read", "tasks:read", "tasks:write", "notifications:read", "notifications:write", "automations:read", "goals:read", "study:read", "college:read", "timeline:read", "health:read", "commands:limited", "sync:write"]

    def _mobile_hash(self, value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _mobile_secret(self) -> bytes:
        settings = get_settings()
        return (settings.api_key or settings.database_url or "nexa-local-mobile-secret").encode("utf-8")

    def _mobile_issue_jwt(self, device_id: int, token_type: str, ttl: timedelta) -> tuple[str, datetime]:
        expires_at = datetime.utcnow() + ttl
        payload = {"device_id": device_id, "typ": token_type, "exp": int(expires_at.timestamp()), "nonce": secrets.token_urlsafe(10)}
        return self._mobile_sign_jwt(payload), expires_at

    def _mobile_sign_jwt(self, payload: dict) -> str:
        header = {"alg": "HS256", "typ": "JWT"}
        encoded_header = self._mobile_b64(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        encoded_payload = self._mobile_b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
        signature = self._mobile_b64(hmac.new(self._mobile_secret(), signing_input, hashlib.sha256).digest())
        return f"{encoded_header}.{encoded_payload}.{signature}"

    def _mobile_decode_jwt(self, token: str) -> dict:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid token format.")
        signing_input = f"{parts[0]}.{parts[1]}".encode("utf-8")
        expected = self._mobile_b64(hmac.new(self._mobile_secret(), signing_input, hashlib.sha256).digest())
        if not hmac.compare_digest(expected, parts[2]):
            raise ValueError("Invalid token signature.")
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(datetime.utcnow().timestamp()):
            raise ValueError("Token expired.")
        return payload

    def _mobile_b64(self, value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")

    def _mobile_bearer_token(self, authorization: str) -> str:
        if not authorization.lower().startswith("bearer "):
            raise ValueError("Authorization bearer token required.")
        return authorization.split(" ", 1)[1].strip()

    def _mobile_audit(self, db: Session, device_id: int | None, event_type: str, action: str, status: str, detail: dict, ip_address: str = "") -> None:
        db.add(MobileAuditLog(device_id=device_id, event_type=event_type, action=action, status=status, ip_address=ip_address, detail_json=json.dumps(detail)))

    def _mobile_device_dict(self, row: MobileDevice) -> dict:
        return {"id": row.id, "device_name": row.device_name, "device_type": row.device_type, "device_fingerprint": row.device_fingerprint, "status": row.status, "permissions": _loads(row.permissions_json, {}), "security_status": row.security_status, "last_active_at": _iso(row.last_active_at), "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat()}

    def _mobile_audit_dict(self, row: MobileAuditLog) -> dict:
        return {"id": row.id, "device_id": row.device_id, "event_type": row.event_type, "action": row.action, "status": row.status, "ip_address": row.ip_address, "detail": _loads(row.detail_json, {}), "created_at": row.created_at.isoformat()}

    def _mobile_sync_dict(self, row: SyncQueue) -> dict:
        return {"id": row.id, "device_id": row.device_id, "item_type": row.item_type, "operation": row.operation, "payload": _loads(row.payload_json, {}), "status": row.status, "retry_count": row.retry_count, "conflict_strategy": row.conflict_strategy, "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat(), "processed_at": _iso(row.processed_at)}

    def _mobile_notification_queue_dict(self, row: NotificationQueue) -> dict:
        return {"id": row.id, "device_id": row.device_id, "notification_id": row.notification_id, "event_type": row.event_type, "priority": row.priority, "payload": _loads(row.payload_json, {}), "status": row.status, "created_at": row.created_at.isoformat(), "delivered_at": _iso(row.delivered_at)}

    def _briefing_context(self, db: Session, settings: dict) -> dict:
        now = datetime.utcnow()
        today_start = datetime.combine(date.today(), datetime.min.time())
        yesterday_start = today_start - timedelta(days=1)
        yesterday_end = today_start
        power = power_monitor_service.get_status()
        tasks = db.query(Task).order_by(Task.created_at.desc()).limit(100).all()
        todays_tasks = [task.command for task in tasks if task.status != TaskStatus.completed.value][:8]
        assignments_due = [task.command for task in tasks if "assignment" in task.command.lower() and task.status != TaskStatus.completed.value][:5]
        deadline_tasks = [
            task.command
            for task in tasks
            if task.status != TaskStatus.completed.value and ("tomorrow" in task.command.lower() or "due" in task.command.lower() or "deadline" in task.command.lower())
        ][:5]
        coding_today = db.query(CodingSession).filter(CodingSession.started_at >= today_start).all()
        coding_yesterday = db.query(CodingSession).filter(CodingSession.started_at >= yesterday_start, CodingSession.started_at < yesterday_end).all()
        coding_today_seconds = sum(item.duration_seconds for item in coding_today)
        coding_yesterday_seconds = sum(item.duration_seconds for item in coding_yesterday)
        coding_projects = sorted({item.project for item in coding_yesterday + coding_today if item.project})[:5]
        coding_files = sum(item.files_modified for item in coding_yesterday + coding_today)
        coding_commits = sum(item.commits for item in coding_yesterday + coding_today)
        app_logs = db.query(ActivityLog).filter(ActivityLog.created_at >= yesterday_start).all()
        vscode_usage = sum(1 for item in app_logs if "code" in item.app_name.lower())
        cursor_usage = sum(1 for item in app_logs if "cursor" in item.app_name.lower())
        study_events = db.query(TimelineEvent).filter(TimelineEvent.event_type == "study", TimelineEvent.created_at >= yesterday_start).all()
        study_yesterday_seconds = sum(item.duration_seconds for item in study_events if item.created_at < yesterday_end)
        study_today_seconds = sum(item.duration_seconds for item in study_events if item.created_at >= today_start)
        study_plans = db.query(StudyPlan).filter(StudyPlan.status == "active").all()
        upcoming_exams = [self._study_plan_dict(plan, db) for plan in study_plans if plan.exam_date][:5]
        missed_topics: list[str] = []
        for plan in study_plans:
            missed_topics.extend(self._study_plan_dict(plan, db).get("missed_topics", []))
        goals = self.list_goals(db)
        achievements = self.list_achievements(db)[:5]
        college_updates = self.list_college_updates(db, limit=10)
        college_dashboard = self.college_dashboard(db)
        copilot_summary = self._copilot_mobile_summary(db)
        attendance_alerts = [item for item in college_updates if "attendance" in (item.get("update_type", "") + item.get("title", "")).lower()]
        website_profiles = db.query(WebsiteProfile).filter(WebsiteProfile.monitoring_enabled.is_(True)).all()
        unread_notifications = db.query(Notification).filter(Notification.read.is_(False)).count()
        pending_approvals = db.query(TaskApproval).filter(TaskApproval.status == ApprovalStatus.pending.value).count()
        notifications = db.query(Notification).order_by(Notification.created_at.desc()).limit(100).all()
        website_alerts = [row.title for row in notifications if "website" in row.alert_type.lower() or "website" in row.module.lower()][:5]
        automation_alerts = [row.title for row in notifications if "automation" in row.alert_type.lower() or "automation" in row.module.lower()][:5]
        automation_dashboard = AutomationEngine(db).dashboard()
        task_reminders = [row.title for row in notifications if "reminder" in row.alert_type.lower() or "reminder" in row.category.lower()][:5]
        system_warnings = [row.title for row in notifications if row.severity in {"high", "critical"}][:5]
        battery_alerts = [row.title for row in notifications if "battery" in row.alert_type.lower() or "battery" in row.module.lower()][:5]
        downloads_yesterday = db.query(DownloadHistory).filter(DownloadHistory.created_at >= yesterday_start, DownloadHistory.created_at < yesterday_end).all()
        download_cleanup = self.cleanup_suggestions(db, limit=5)
        download_duplicates = self.list_duplicate_files(db, limit=5)
        download_analytics = self.download_analytics(db, days=7)
        screenshots_yesterday = db.query(ScreenshotHistory).filter(ScreenshotHistory.created_at >= yesterday_start, ScreenshotHistory.created_at < yesterday_end).all()
        screenshot_errors = db.query(ErrorAnalysis).filter(ErrorAnalysis.created_at >= yesterday_start).order_by(ErrorAnalysis.created_at.desc()).limit(5).all()
        screenshot_documents = db.query(DocumentSummary).filter(DocumentSummary.created_at >= yesterday_start).order_by(DocumentSummary.created_at.desc()).limit(5).all()
        screenshot_actions = db.query(ScreenshotAction).filter(ScreenshotAction.created_at >= yesterday_start).order_by(ScreenshotAction.created_at.desc()).limit(10).all()
        recovery_reports = db.query(CrashReport).filter(CrashReport.created_at >= yesterday_start).order_by(CrashReport.created_at.desc()).limit(5).all()
        recovery_sessions = db.query(RecoverySession).filter(RecoverySession.status == "captured").order_by(RecoverySession.started_at.desc()).limit(5).all()
        recovery_incidents = db.query(IncidentReport).filter(IncidentReport.created_at >= yesterday_start).order_by(IncidentReport.created_at.desc()).limit(5).all()
        active_events = db.query(Task).filter(Task.status.in_(["created", "running", "pending_confirmation"])).count()
        goal_average = round(sum(goal["progress_percent"] for goal in goals) / max(len(goals), 1), 2) if goals else 0
        system_health = self._briefing_system_health()
        productivity_score = self._productivity_score(coding_yesterday_seconds, study_yesterday_seconds, len(todays_tasks), unread_notifications)
        return {
            "battery": power,
            "charging": power.get("is_charging"),
            "todays_tasks": todays_tasks,
            "tasks_total": len(tasks),
            "tasks_completed": sum(1 for task in tasks if task.status == TaskStatus.completed.value),
            "coding": {
                "today_seconds": coding_today_seconds,
                "yesterday_seconds": coding_yesterday_seconds,
                "vscode_usage": vscode_usage,
                "cursor_usage": cursor_usage,
                "projects": coding_projects,
                "git_commits": coding_commits,
                "files_modified": coding_files,
                "productivity_score": productivity_score,
            },
            "study": {
                "today_seconds": study_today_seconds,
                "yesterday_seconds": study_yesterday_seconds,
                "goal_progress": [goal for goal in goals if goal["goal_type"] == "study"],
                "upcoming_exams": upcoming_exams,
                "revision_status": "active" if study_plans else "not_configured",
                "assignments_due": assignments_due,
                "missed_topics": missed_topics[:8],
                "recommended_topics": missed_topics[:3],
            },
            "college": {
                "summary": college_dashboard["summary"],
                "attendance_updates": attendance_alerts,
                "internal_marks": college_dashboard["marks"] or [item for item in college_updates if "mark" in item["title"].lower()],
                "results": college_dashboard["results"] or [item for item in college_updates if "result" in item["title"].lower()],
                "announcements": college_dashboard["announcements"] or [item for item in college_updates if "announcement" in item["title"].lower()],
                "fees": college_dashboard["fees"] or [item for item in college_updates if "fee" in item["title"].lower()],
                "timetable_changes": college_dashboard["timetables"] or [item for item in college_updates if "timetable" in item["title"].lower()],
                "assignments": college_dashboard["assignments"],
                "recommendations": college_dashboard["recommendations"],
                "contineo_alerts": [item for item in college_updates if "contineo" in item["source"].lower()],
                "kcet_alerts": college_dashboard["kcet"] or [item for item in college_updates if "kcet" in item["source"].lower()],
                "website_monitoring_alerts": website_alerts,
            },
            "copilot": {
                "top_recommendations": copilot_summary["suggestions"][:5],
                "warnings": copilot_summary["warnings"],
                "insights": copilot_summary["insights"],
                "quick_actions": copilot_summary["quick_actions"],
                "system_status": copilot_summary["system_status"],
                "offline_ready": copilot_summary["offline_ready"],
                "privacy": copilot_summary["privacy"],
            },
            "goals": {"items": goals, "average_percent": goal_average, "achievements": achievements},
            "notifications": {
                "unread": unread_notifications,
                "pending_approvals": pending_approvals,
                "website_alerts": website_alerts,
                "automation_alerts": automation_alerts,
                "task_reminders": task_reminders,
                "system_warnings": system_warnings,
                "battery_alerts": battery_alerts,
            },
            "automations": {
                "active": len(automation_dashboard["active"]),
                "paused": len(automation_dashboard["paused"]),
                "failed": len(automation_dashboard["failed"]),
                "recent_executions": automation_dashboard["recent_executions"][:5],
                "statistics": automation_dashboard["statistics"],
                "recommendations": ["Review failed automations."] if automation_dashboard["failed"] else ["Automation system is healthy."],
                "pending_approvals": automation_dashboard["statistics"].get("pending_approvals", 0),
            },
            "downloads": {
                "yesterday_count": len(downloads_yesterday),
                "yesterday_size_bytes": sum(item.size_bytes for item in downloads_yesterday),
                "large_files": [self._download_dict(item) for item in downloads_yesterday if item.size_bytes >= 100 * 1024 * 1024][:5],
                "duplicates": download_duplicates,
                "cleanup_suggestions": download_cleanup,
                "analytics": download_analytics,
                "storage_growth": self._format_bytes(sum(item.size_bytes for item in downloads_yesterday)),
            },
            "screenshots": {
                "yesterday_count": len(screenshots_yesterday),
                "important": [self._screenshot_dict(item) for item in screenshots_yesterday[:5]],
                "errors_solved": [self._error_analysis_dict(item) for item in screenshot_errors],
                "documents_analyzed": [self._document_summary_dict(item) for item in screenshot_documents],
                "notes_generated": [self._screenshot_action_dict(item) for item in screenshot_actions if item.action_type in {"save_notes", "create_study_task"}],
                "learning_insights": [item.summary for item in screenshot_documents[:3]],
            },
            "recovery": {
                "recent_reports": [self._crash_report_dict(item) for item in recovery_reports],
                "open_sessions": [self._recovery_session_dict(item) for item in recovery_sessions],
                "incident_reports": [self._incident_report_dict(item) for item in recovery_incidents],
                "recommendations": self.recovery_recommendations(db),
                "status": "attention_needed" if recovery_reports or recovery_sessions else "ready",
            },
            "weather": self._weather_summary(settings.get("weather_location", "")),
            "website_alerts": len(website_profiles),
            "events": active_events,
            "system_health": system_health,
            "nexa_status": "All systems operational." if system_health["health_score"] >= 80 else "Nexa needs attention. Review health recommendations.",
            "scheduled_time": settings["time"],
            "generated_at": now.isoformat(),
        }

    def _prioritize_briefing_sections(self, context: dict) -> list[dict]:
        sections = [
            {"id": "battery", "title": "Battery", "priority": 95 if self._battery_low(context) else 30, "data": context["battery"]},
            {"id": "deadlines", "title": "Upcoming Deadlines", "priority": 90 if context["study"]["assignments_due"] else 45, "data": context["study"]["assignments_due"]},
            {"id": "study", "title": "Study Summary", "priority": 85 if context["study"]["upcoming_exams"] else 40, "data": context["study"]},
            {"id": "coding", "title": "Coding Summary", "priority": 80 if context["coding"]["yesterday_seconds"] >= 7200 else 35, "data": context["coding"]},
            {"id": "tasks", "title": "Today's Tasks", "priority": 75 if context["todays_tasks"] else 30, "data": context["todays_tasks"]},
            {"id": "college", "title": "College Companion", "priority": 70 if context["college"]["website_monitoring_alerts"] else 25, "data": context["college"]},
            {"id": "copilot", "title": "AI Copilot", "priority": 88 if context["copilot"]["warnings"] or context["copilot"]["top_recommendations"] else 24, "data": context["copilot"]},
            {"id": "goals", "title": "Goal Progress", "priority": 60 if context["goals"]["items"] else 20, "data": context["goals"]},
            {"id": "notifications", "title": "Notifications", "priority": 65 if context["notifications"]["unread"] else 20, "data": context["notifications"]},
            {"id": "automations", "title": "Automations", "priority": 68 if context["automations"]["failed"] or context["automations"]["pending_approvals"] else 22, "data": context["automations"]},
            {"id": "downloads", "title": "Downloads", "priority": 62 if context["downloads"]["cleanup_suggestions"] or context["downloads"]["duplicates"] else 18, "data": context["downloads"]},
            {"id": "screenshots", "title": "Screenshot Assistant", "priority": 64 if context["screenshots"]["errors_solved"] or context["screenshots"]["documents_analyzed"] else 18, "data": context["screenshots"]},
            {"id": "recovery", "title": "Emergency Recovery", "priority": 92 if context["recovery"]["recent_reports"] or context["recovery"]["open_sessions"] else 18, "data": context["recovery"]},
            {"id": "weather", "title": "Weather", "priority": 15 if context["weather"]["status"] == "offline" else 35, "data": context["weather"]},
            {"id": "system", "title": "System Health", "priority": 55 if context["system_health"]["health_score"] < 80 else 20, "data": context["system_health"]},
        ]
        return sorted(sections, key=lambda item: item["priority"], reverse=True)

    def _secretary_recommendations(self, context: dict) -> list[dict]:
        recommendations: list[dict] = []
        if self._battery_low(context):
            recommendations.append({"type": "battery", "priority": "high", "title": "Connect charger", "message": "Battery is low and the laptop is not charging.", "action": {"target": "battery"}})
        if context["study"]["assignments_due"]:
            recommendations.append({"type": "deadline", "priority": "high", "title": "Assignment deadline", "message": "You have assignment-related tasks that need review.", "action": {"target": "tasks"}})
        if context["coding"]["yesterday_seconds"] == 0:
            recommendations.append({"type": "coding_goal", "priority": "medium", "title": "Coding goal missed", "message": "No coding time was recorded yesterday.", "action": {"target": "coding"}})
        if context["study"]["missed_topics"]:
            recommendations.append({"type": "study_revision", "priority": "medium", "title": "Revise missed topics", "message": f"Recommended topics: {', '.join(context['study']['recommended_topics'])}.", "action": {"target": "study"}})
        if context["notifications"]["pending_approvals"]:
            recommendations.append({"type": "approval", "priority": "medium", "title": "Pending approvals", "message": f"{context['notifications']['pending_approvals']} approval(s) are waiting.", "action": {"target": "approvals"}})
        if context["automations"]["failed"] or context["automations"]["pending_approvals"]:
            recommendations.append({"type": "automation", "priority": "medium", "title": "Review automations", "message": f"{context['automations']['failed']} failed automation(s), {context['automations']['pending_approvals']} pending approval(s).", "action": {"target": "automations"}})
        if context["downloads"]["duplicates"] or context["downloads"]["cleanup_suggestions"]:
            recommendations.append({"type": "downloads", "priority": "medium", "title": "Review Downloads cleanup", "message": f"{len(context['downloads']['cleanup_suggestions'])} cleanup suggestion(s) and {len(context['downloads']['duplicates'])} duplicate(s) are waiting.", "action": {"target": "downloads"}})
        if context["screenshots"]["errors_solved"]:
            recommendations.append({"type": "screenshot_error", "priority": "medium", "title": "Review captured errors", "message": f"{len(context['screenshots']['errors_solved'])} screenshot error analysis item(s) are available.", "action": {"target": "screenshots"}})
        if context["recovery"]["recent_reports"] or context["recovery"]["open_sessions"]:
            recommendations.append({"type": "emergency_recovery", "priority": "high", "title": "Review recovery status", "message": f"{len(context['recovery']['recent_reports'])} recovery report(s) and {len(context['recovery']['open_sessions'])} captured session(s) need review.", "action": {"target": "recovery"}})
        if context["goals"]["items"] and context["goals"]["average_percent"] < 50:
            recommendations.append({"type": "goal", "priority": "medium", "title": "Goals need progress", "message": "Average goal progress is below 50%.", "action": {"target": "goals"}})
        if context["college"]["attendance_updates"]:
            recommendations.append({"type": "attendance", "priority": "high", "title": "Attendance alert", "message": "Review attendance updates from College Companion.", "action": {"target": "college"}})
        if context["copilot"]["warnings"] or context["copilot"]["top_recommendations"]:
            top = (context["copilot"]["warnings"] or context["copilot"]["top_recommendations"])[0]
            recommendations.append({
                "type": "copilot",
                "priority": top.get("severity", "medium"),
                "title": top.get("title", "Review Copilot recommendation"),
                "message": top.get("message", "Nexa Copilot has a context-aware recommendation."),
                "action": {"target": "copilot"},
            })
        if not recommendations:
            recommendations.append({"type": "secretary", "priority": "low", "title": "Plan looks clear", "message": "No urgent issues detected. Review tasks and keep the day focused.", "action": {"target": "dashboard"}})
        return recommendations

    def _briefing_insights(self, db: Session, context: dict) -> dict:
        previous = db.query(BriefingAnalytics).order_by(BriefingAnalytics.created_at.desc()).first()
        insights: dict = {"trend_messages": []}
        if previous:
            coding_delta = context["coding"]["yesterday_seconds"] - previous.coding_seconds
            study_delta = context["study"]["yesterday_seconds"] - previous.study_seconds
            if previous.coding_seconds:
                insights["trend_messages"].append(f"Coding changed {round(coding_delta / previous.coding_seconds * 100)}% versus the previous briefing.")
            if previous.study_seconds:
                insights["trend_messages"].append(f"Study time changed {round(study_delta / previous.study_seconds * 100)}% versus the previous briefing.")
            task_delta = context["tasks_completed"] - previous.tasks_completed
            insights["trend_messages"].append(f"Task completion changed by {task_delta}.")
        if not insights["trend_messages"]:
            insights["trend_messages"].append("This is the baseline briefing for future trend insights.")
        return insights

    def _briefing_summary(self, context: dict, sections: list[dict], recommendations: list[dict]) -> str:
        battery = context["battery"].get("battery_percent", "unknown")
        charging = "Yes" if context["charging"] else "No" if context["charging"] is False else "Unknown"
        top = recommendations[0]["message"] if recommendations else "No urgent recommendations."
        return (
            f"Good Morning. Battery: {battery}%. Charging: {charging}. "
            f"Tasks today: {len(context['todays_tasks'])}. "
            f"Coding yesterday: {self._duration(context['coding']['yesterday_seconds'])}. "
            f"Study yesterday: {self._duration(context['study']['yesterday_seconds'])}. "
            f"Deadlines: {len(context['study']['assignments_due'])}. "
            f"Unread notifications: {context['notifications']['unread']}. "
            f"Top priority: {sections[0]['title'] if sections else 'Overview'}. Secretary note: {top}"
        )

    def _voice_briefing_text(self, context: dict, recommendations: list[dict]) -> str:
        battery = context["battery"].get("battery_percent", "unknown")
        task_count = len(context["todays_tasks"])
        deadline_count = len(context["study"]["assignments_due"])
        return (
            f"Good morning. Battery is at {battery} percent. "
            f"You have {task_count} tasks today. "
            f"Coding time yesterday was {self._duration(context['coding']['yesterday_seconds'])}. "
            f"Study time yesterday was {self._duration(context['study']['yesterday_seconds'])}. "
            f"You have {deadline_count} upcoming assignment deadline{'s' if deadline_count != 1 else ''}. "
            f"{recommendations[0]['message'] if recommendations else 'Have a productive day.'}"
        )

    def _store_briefing_records(self, db: Session, row: DailyBriefing, payload: dict, recommendations: list[dict], context: dict, delivery_method: str, started: datetime) -> None:
        stats = {
            "generation_ms": round((datetime.utcnow() - started).total_seconds() * 1000, 2),
            "tasks_total": context["tasks_total"],
            "tasks_completed": context["tasks_completed"],
            "unread_notifications": context["notifications"]["unread"],
            "pending_approvals": context["notifications"]["pending_approvals"],
        }
        db.add(
            BriefingHistory(
                briefing_id=row.id,
                briefing_date=row.briefing_date,
                delivery_method=delivery_method,
                delivery_status="delivered" if row.notification_id else "generated",
                content_json=json.dumps(payload, default=str),
                statistics_json=json.dumps(stats, default=str),
                recommendations_json=json.dumps(recommendations, default=str),
            )
        )
        db.query(BriefingRecommendation).filter(BriefingRecommendation.briefing_id == row.id).delete()
        for item in recommendations:
            db.add(
                BriefingRecommendation(
                    briefing_id=row.id,
                    recommendation_type=item["type"],
                    title=item["title"],
                    message=item["message"],
                    priority=item["priority"],
                    action_json=json.dumps(item.get("action", {}), default=str),
                )
            )
        db.add(
            BriefingAnalytics(
                briefing_date=row.briefing_date,
                coding_seconds=context["coding"]["yesterday_seconds"],
                study_seconds=context["study"]["yesterday_seconds"],
                tasks_total=context["tasks_total"],
                tasks_completed=context["tasks_completed"],
                unread_notifications=context["notifications"]["unread"],
                pending_approvals=context["notifications"]["pending_approvals"],
                goal_average_percent=context["goals"]["average_percent"],
                productivity_score=context["coding"]["productivity_score"],
                insight_json=json.dumps(payload["insights"], default=str),
            )
        )

    def _get_or_create_briefing_schedule(self, db: Session) -> BriefingSchedule:
        row = db.query(BriefingSchedule).order_by(BriefingSchedule.created_at.asc()).first()
        if row:
            return row
        settings = self.get_briefing_settings(db)
        row = BriefingSchedule(
            enabled=bool(settings["enabled"]),
            schedule_time=settings["time"],
            days=settings["days"],
            on_startup=bool(settings["on_startup"]),
            speak=bool(settings["speak"]),
            notify=bool(settings["notify"]),
            delivery_methods_json=json.dumps(settings["delivery_methods"], default=str),
        )
        db.add(row)
        db.flush()
        return row

    def _weather_summary(self, location: str) -> dict:
        if not location:
            return {"status": "hidden", "location": "", "summary": "Weather location is not configured."}
        try:
            response = requests.get(f"https://wttr.in/{location}", params={"format": "j1"}, timeout=0.4)
            response.raise_for_status()
            data = response.json()
            current = (data.get("current_condition") or [{}])[0]
            temp = current.get("temp_C")
            description = ((current.get("weatherDesc") or [{}])[0]).get("value", "")
            return {"status": "online", "location": location, "temperature_celsius": temp, "summary": f"{temp} C, {description}".strip(", ")}
        except Exception:
            return {"status": "offline", "location": location, "summary": "Weather unavailable offline."}

    def _briefing_system_health(self) -> dict:
        system = SystemAgent().status()
        resource = resource_manager_service.get_status()
        cpu = float(system.get("cpu_percent") or 0)
        ram = float(system.get("memory_percent") or system.get("ram_percent") or 0)
        score = max(0, round(100 - cpu * 0.4 - ram * 0.2, 1))
        recommendations = []
        if resource.get("mode") != "normal":
            recommendations.append("Resource manager is throttling non-critical work.")
        return {"health_score": score, "system": system, "resource_manager": resource, "recommendations": recommendations}

    def _battery_low(self, context: dict) -> bool:
        percent = context["battery"].get("battery_percent")
        return isinstance(percent, int) and percent <= 20 and context.get("charging") is False

    def _productivity_score(self, coding_seconds: int, study_seconds: int, task_count: int, unread: int) -> float:
        score = 50 + min(25, coding_seconds / 3600 * 5) + min(20, study_seconds / 3600 * 5) - min(20, unread * 0.5) - min(10, task_count * 0.5)
        return round(max(0, min(100, score)), 2)

    def _duration(self, seconds: int) -> str:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if hours:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"

    def _parse_time(self, value: str) -> tuple[int, int]:
        try:
            hour, minute = value.split(":", 1)
            return max(0, min(23, int(hour))), max(0, min(59, int(minute)))
        except Exception:
            return 8, 0

    def _schedule_allows_today(self, settings: dict) -> bool:
        days = settings.get("days", "all")
        weekday = datetime.now().weekday()
        if days == "weekdays":
            return weekday < 5
        if days == "weekends":
            return weekday >= 5
        return True

    def _default_blocked_sites(self) -> list[str]:
        return ["youtube.com", "instagram.com", "facebook.com", "twitter.com", "x.com", "reddit.com"]

    def _ensure_blocked_site(self, db: Session, domain: str) -> None:
        normalized = domain.strip().lower().replace("https://", "").replace("http://", "").strip("/")
        if not normalized:
            return
        if not db.query(BlockedSite).filter(BlockedSite.domain == normalized).one_or_none():
            db.add(BlockedSite(domain=normalized, reason="Focus Mode Active"))

    def _ensure_blocked_app(self, db: Session, app_name: str) -> None:
        normalized = app_name.strip()
        if not normalized:
            return
        if not db.query(BlockedApp).filter(BlockedApp.app_name == normalized).one_or_none():
            db.add(BlockedApp(app_name=normalized, reason="Focus Mode Active"))

    def _active_focus_row(self, db: Session, session_id: int | None = None, include_paused: bool = False) -> FocusSession:
        statuses = ["active", "paused"] if include_paused else ["active"]
        row = db.get(FocusSession, session_id) if session_id else db.query(FocusSession).filter(FocusSession.status.in_(statuses)).order_by(FocusSession.started_at.desc()).first()
        if not row or row.status not in statuses:
            raise ValueError("Active focus session not found")
        return row

    def _focus_history(self, db: Session, session_id: int | None, event_type: str, detail: dict) -> None:
        db.add(FocusHistory(session_id=session_id, event_type=event_type, detail_json=json.dumps(detail, default=str)))

    def _focus_goal_completion(self, db: Session, session_id: int) -> float:
        goals = db.query(FocusGoal).filter(FocusGoal.session_id == session_id).all()
        if not goals:
            return 0
        return round(sum(goal.completion_percent for goal in goals) / len(goals), 2)

    def _focus_productivity_score(self, focus_seconds: int, break_seconds: int, distractions: int, goal_completion: float, tasks_completed: int) -> float:
        focus_points = min(35, focus_seconds / 3600 * 20)
        break_points = 10 if break_seconds > 0 else 5
        goal_points = min(30, goal_completion * 0.3)
        task_points = min(15, tasks_completed * 5)
        penalty = min(35, distractions * 8)
        return round(max(0, min(100, 35 + focus_points + break_points + goal_points + task_points - penalty)), 2)

    def _focus_recommendations(self, score: float, distractions: int, goal_completion: float) -> list[dict]:
        recommendations = []
        if distractions:
            recommendations.append({"type": "distraction", "message": "Reduce blocked distraction attempts next session."})
        if goal_completion < 80:
            recommendations.append({"type": "goal", "message": "Set a smaller focus goal or extend the session."})
        if score >= 85:
            recommendations.append({"type": "streak", "message": "Strong focus session. Consider starting another cycle after a break."})
        if not recommendations:
            recommendations.append({"type": "baseline", "message": "Session complete. Keep blockers enabled for the next session."})
        return recommendations

    def _copilot_context(self, db: Session) -> dict:
        now = datetime.utcnow()
        today_start = datetime.combine(date.today(), datetime.min.time())
        yesterday_start = today_start - timedelta(days=1)
        power = power_monitor_service.get_status()
        resource = resource_manager_service.get_status()
        latest_activity = db.query(ActivityLog).order_by(ActivityLog.created_at.desc()).first()
        active_focus = db.query(FocusSession).filter(FocusSession.status.in_(["active", "paused"])).order_by(FocusSession.started_at.desc()).first()
        coding_today = db.query(CodingSession).filter(CodingSession.started_at >= today_start).all()
        coding_yesterday = db.query(CodingSession).filter(CodingSession.started_at >= yesterday_start, CodingSession.started_at < today_start).all()
        study_dashboard = self.study_dashboard(db)
        college_dashboard = self.college_dashboard(db)
        goal_dashboard = self.goal_dashboard(db)
        health = self.self_health(db)
        latest_project = db.query(ProjectHealth).order_by(ProjectHealth.created_at.desc()).first()
        latest_error = db.query(TimelineEvent).filter((TimelineEvent.title.ilike("%error%")) | (TimelineEvent.description.ilike("%error%")) | (TimelineEvent.event_type == "coding_error")).order_by(TimelineEvent.created_at.desc()).first()
        active_tasks = db.query(Task).filter(Task.status.in_(["created", "pending_confirmation", "running"])).order_by(Task.created_at.desc()).limit(25).all()
        notifications_unread = db.query(Notification).filter(Notification.read.is_(False)).count()
        automation_dashboard = AutomationEngine(db).dashboard()
        activity_type = self._copilot_activity_type(latest_activity, active_focus, latest_error)
        priority_context = self._copilot_priority(power, health, active_tasks, college_dashboard, goal_dashboard)
        return {
            "captured_at": now.isoformat(),
            "priority_context": priority_context,
            "activity": {
                "type": activity_type,
                "latest": {"activity_type": latest_activity.activity_type, "app_name": latest_activity.app_name, "project": latest_activity.project, "window_title": _loads(latest_activity.detail_json, {}).get("window_title", ""), "created_at": latest_activity.created_at.isoformat()} if latest_activity else {},
                "idle": not latest_activity or (now - latest_activity.created_at).total_seconds() > 1800,
                "coding_today_seconds": sum(item.duration_seconds for item in coding_today),
                "coding_yesterday_seconds": sum(item.duration_seconds for item in coding_yesterday),
            },
            "battery": power,
            "resource": resource,
            "focus": self._focus_dict(active_focus) if active_focus else None,
            "study": study_dashboard,
            "college": college_dashboard,
            "goals": goal_dashboard,
            "tasks": [{"id": task.id, "command": task.command, "status": task.status, "plan": _loads(task.plan_json, {})} for task in active_tasks],
            "notifications": {"unread": notifications_unread},
            "automations": automation_dashboard,
            "health": health,
            "project": self._project_health_dict(latest_project) if latest_project else None,
            "coding_error": self._timeline_dict(latest_error) if latest_error else None,
            "privacy": {"mode": self.get_copilot_settings(db)["privacy_mode"], "cloud_upload": False, "local_processing": True},
        }

    def _copilot_candidates(self, db: Session, context: dict, settings: dict) -> list[dict]:
        modules = settings.get("modules", {})
        candidates: list[dict] = []
        battery = context["battery"].get("battery_percent")
        charging = context["battery"].get("is_charging")
        if modules.get("battery", True) and isinstance(battery, (int, float)):
            if battery <= 10 and not charging:
                candidates.append(self._copilot_candidate("battery", "Critical battery level", f"Battery is {battery}% and the laptop is not charging. Connect the charger immediately.", "critical", "battery", {"type": "open", "target": "battery"}))
            elif battery <= 20 and not charging:
                candidates.append(self._copilot_candidate("battery", "Battery needs attention", f"Battery is {battery}% and the charger is disconnected.", "high", "battery", {"type": "open", "target": "battery"}))
            elif battery >= 95 and charging:
                candidates.append(self._copilot_candidate("battery_health", "Battery near full", "Battery is above 95%. Consider unplugging to reduce battery wear.", "medium", "battery", {"type": "open", "target": "battery"}))
        if modules.get("health", True):
            health_score = context["health"].get("health_score", 100)
            if health_score < 60:
                candidates.append(self._copilot_candidate("health", "Nexa needs optimization", f"Nexa health score is {health_score}%. Review resource and error recommendations.", "high", "self_health", {"type": "open", "target": "resources"}))
            if context["resource"].get("mode") in {"thermal_protection", "load_shedding", "power_saving"}:
                candidates.append(self._copilot_candidate("resource", "Reduce background activity", "Resource Manager is throttling non-critical work. Delay heavy automations until the system cools down.", "medium", "resource_manager", {"type": "open", "target": "resources"}))
        if modules.get("coding", True) and context.get("coding_error"):
            error = context["coding_error"]
            candidates.append(self._copilot_candidate("coding_error", "Coding issue detected", f"{error['title']}: Nexa can explain the likely cause and create a fix task.", "medium", "coding_copilot", {"type": "open", "target": "coding", "timeline_event_id": error["id"]}))
        if modules.get("study", True):
            focus = context.get("focus")
            if focus and focus.get("mode") in {"study", "focus"} and int(focus.get("duration_seconds") or 0) >= 7200:
                candidates.append(self._copilot_candidate("study_break", "Long study session detected", "You have been focused for about 2 hours. Take a short break before continuing.", "medium", "study_copilot", {"type": "start_break", "target": "focus"}))
            for exam in context["study"].get("exam_countdowns", [])[:3]:
                if exam.get("days_remaining") is not None and exam["days_remaining"] <= 5:
                    candidates.append(self._copilot_candidate("exam", f"{exam['subject']} exam is close", f"{exam['days_remaining']} day(s) remaining. Prioritize revision and practice.", "high", "study_copilot", {"type": "open", "target": "study"}))
        if modules.get("college", True):
            for item in context["college"].get("recommendations", [])[:3]:
                priority = "high" if item.get("priority") == "high" else "medium"
                candidates.append(self._copilot_candidate("college", item.get("title", "College update needs attention"), item.get("message", "Review College Companion updates."), priority, "college_copilot", {"type": "open", "target": "college"}))
        if modules.get("goals", True):
            for item in context["goals"].get("recommendations", [])[:3]:
                candidates.append(self._copilot_candidate("goal", item.get("title", "Goal needs progress"), item.get("message", "Review goal progress and next action."), item.get("priority", "medium"), "goal_copilot", {"type": "open", "target": "goals"}))
        if modules.get("project", True) and context.get("project"):
            project = context["project"]
            if project.get("risk_level") in {"high", "critical"} or project.get("backup_age_hours", 0) >= 24:
                candidates.append(self._copilot_candidate("project_backup", "Project backup recommended", "Project Guardian detected backup or Git risk. Create a snapshot before continuing.", "high", "project_copilot", {"type": "open", "target": "guardian", "project_id": project.get("project_id")}))
        if context["tasks"]:
            deadline_tasks = [task for task in context["tasks"] if "assignment" in task["command"].lower() or "tomorrow" in task["command"].lower() or "due" in task["command"].lower()]
            if deadline_tasks:
                candidates.append(self._copilot_candidate("deadline", "Deadline needs attention", f"{len(deadline_tasks)} task(s) look deadline-sensitive. Review assignments and reminders.", "high", "task_copilot", {"type": "open", "target": "tasks", "task_ids": [task["id"] for task in deadline_tasks]}))
        if context["automations"].get("failed"):
            candidates.append(self._copilot_candidate("automation", "Automation failures detected", "One or more automations failed recently. Review history before depending on them.", "medium", "automation_copilot", {"type": "open", "target": "automation"}))
        return candidates[:12]

    def _copilot_candidate(self, suggestion_type: str, title: str, message: str, severity: str, module: str, action: dict, metadata: dict | None = None) -> dict:
        return {"type": suggestion_type, "title": title, "message": message, "severity": severity, "module": module, "action": action, "metadata": metadata or {}}

    def _copilot_activity_type(self, latest_activity: ActivityLog | None, active_focus: FocusSession | None, latest_error: TimelineEvent | None) -> str:
        if latest_error and (datetime.utcnow() - latest_error.created_at).total_seconds() < 3600:
            return "coding_error"
        if active_focus:
            return active_focus.mode or "focus"
        if not latest_activity:
            return "idle"
        lower = f"{latest_activity.activity_type} {latest_activity.app_name} {latest_activity.project}".lower()
        if any(term in lower for term in ["code", "cursor", "terminal", "git", "coding"]):
            return "coding"
        if any(term in lower for term in ["study", "pdf", "notes", "exam"]):
            return "study"
        if any(term in lower for term in ["browser", "chrome", "edge", "website"]):
            return "browsing"
        if any(term in lower for term in ["game", "steam"]):
            return "gaming"
        return latest_activity.activity_type or "active"

    def _copilot_priority(self, power: dict, health: dict, tasks: list[Task], college: dict, goals: dict) -> str:
        battery = power.get("battery_percent")
        if isinstance(battery, (int, float)) and battery <= 10 and not power.get("is_charging"):
            return "critical"
        if health.get("health_score", 100) < 50:
            return "critical"
        if any("assignment" in task.command.lower() or "tomorrow" in task.command.lower() for task in tasks):
            return "high"
        if college.get("recommendations") or goals.get("recommendations"):
            return "medium"
        return "normal"

    def _create_suggestion(self, db: Session, suggestion_type: str, title: str, message: str, severity: str, action: dict, module: str = "copilot_engine", metadata: dict | None = None) -> dict:
        existing = (
            db.query(CopilotSuggestion)
            .filter(CopilotSuggestion.suggestion_type == suggestion_type, CopilotSuggestion.title == title, CopilotSuggestion.status == "open", CopilotSuggestion.created_at >= datetime.utcnow() - timedelta(minutes=30))
            .order_by(CopilotSuggestion.created_at.desc())
            .first()
        )
        if existing:
            return self._suggestion_dict(existing)
        row = CopilotSuggestion(suggestion_type=suggestion_type, title=title, message=message, severity=severity, action_json=json.dumps(action), module=module)
        db.add(row)
        db.flush()
        if severity in {"high", "critical"}:
            db.add(CopilotWarning(warning_type=suggestion_type, module=module, title=title, message=message, severity=severity, metadata_json=json.dumps(metadata or {}, default=str)))
        db.add(CopilotAction(suggestion_id=row.id, action_type=action.get("type", "open"), title=title, payload_json=json.dumps(action, default=str)))
        db.add(CopilotHistory(event_type="suggestion_created", suggestion_id=row.id, title=title, detail_json=json.dumps({"severity": severity, "module": module, "metadata": metadata or {}}, default=str)))
        self.add_timeline_event(db, "copilot", title, message, "copilot_engine", metadata={"suggestion_id": row.id, "severity": severity}, commit=False)
        return self._suggestion_dict(row)

    def _record_copilot_insights(self, db: Session, context: dict) -> None:
        insights: list[tuple[str, str, str, str, str]] = []
        coding_today = context["activity"].get("coding_today_seconds", 0)
        coding_yesterday = context["activity"].get("coding_yesterday_seconds", 0)
        if coding_yesterday and coding_today > coding_yesterday * 1.2:
            insights.append(("coding_trend", "Coding momentum increased", "Coding time is up compared with yesterday.", "Keep one focused session for the highest-priority project.", "low"))
        if context["study"].get("summary", {}).get("active_plans", 0) and not context["focus"]:
            insights.append(("study_planning", "Study plan is ready", "A study plan is active but no focus session is running.", "Start a study focus session when ready.", "low"))
        if context["goals"].get("summary", {}).get("active", 0) and context["goals"].get("summary", {}).get("average_progress", 100) < 50:
            insights.append(("goal_progress", "Goal progress is behind", "Average goal progress is below 50%.", "Pick one goal and complete the next small step today.", "medium"))
        if not insights:
            insights.append(("baseline", "Copilot context captured", "Nexa has refreshed local context and found no unusual trend.", "Keep working; Copilot will notify only when useful.", "low"))
        for insight_type, title, message, recommendation, severity in insights:
            exists = db.query(CopilotInsight).filter(CopilotInsight.insight_type == insight_type, CopilotInsight.title == title, CopilotInsight.created_at >= datetime.utcnow() - timedelta(hours=12)).first()
            if not exists:
                db.add(CopilotInsight(insight_type=insight_type, title=title, message=message, recommendation=recommendation, severity=severity, metadata_json=json.dumps({"activity_type": context["activity"]["type"]}, default=str)))

    def _record_copilot_analytics(self, db: Session, generated: int) -> None:
        key = date.today().isoformat()
        row = db.query(CopilotAnalytics).filter(CopilotAnalytics.analytics_date == key).one_or_none()
        if not row:
            row = CopilotAnalytics(analytics_date=key)
            db.add(row)
        row.suggestions_generated = int(row.suggestions_generated or 0) + generated
        row.suggestions_acted = db.query(CopilotSuggestion).filter(CopilotSuggestion.status == "acted").count()
        row.warnings_open = db.query(CopilotWarning).filter(CopilotWarning.status == "open").count()
        row.critical_count = db.query(CopilotSuggestion).filter(CopilotSuggestion.severity == "critical", CopilotSuggestion.created_at >= datetime.combine(date.today(), datetime.min.time())).count()
        row.helpful_score = max(0, min(100, 100 - row.warnings_open * 5 + row.suggestions_acted * 2))
        row.metadata_json = json.dumps({"offline_ready": True, "local_processing": True}, default=str)
        row.updated_at = datetime.utcnow()

    def _copilot_quick_actions(self, suggestions: list[dict]) -> list[dict]:
        actions = [{"id": "refresh_context", "label": "Refresh Context", "action": {"type": "evaluate_copilot"}}]
        targets = {item.get("action", {}).get("target") for item in suggestions}
        if "focus" in targets or any(item["suggestion_type"] in {"study_break", "focus"} for item in suggestions):
            actions.append({"id": "start_focus", "label": "Start Focus Mode", "action": {"type": "start_focus"}})
        if "guardian" in targets:
            actions.append({"id": "backup_project", "label": "Backup Project", "action": {"type": "open", "target": "guardian"}})
        if "resources" in targets:
            actions.append({"id": "optimize_nexa", "label": "Optimize Nexa", "action": {"type": "open", "target": "resources"}})
        if "college" in targets:
            actions.append({"id": "check_college", "label": "Check College", "action": {"type": "open", "target": "college"}})
        if "study" in targets:
            actions.append({"id": "launch_study_plan", "label": "Launch Study Plan", "action": {"type": "open", "target": "study"}})
        return actions[:8]

    def _copilot_system_status(self, suggestions: list[dict], warnings: list[dict]) -> dict:
        critical = sum(1 for item in suggestions if item["severity"] == "critical") + sum(1 for item in warnings if item["severity"] == "critical" and item["status"] == "open")
        high = sum(1 for item in suggestions if item["severity"] == "high")
        status = "critical" if critical else "attention" if high else "ready"
        return {"status": status, "critical": critical, "high": high, "message": "Critical recommendations require action." if critical else "Copilot is monitoring local context."}

    def _unlock_achievement(self, db: Session, title: str, badge: str, description: str, metadata: dict) -> None:
        existing = db.query(Achievement).filter(Achievement.title == title).one_or_none()
        if existing:
            return
        db.add(Achievement(title=title, badge=badge, description=description, progress_percent=100, unlocked=True, unlocked_at=datetime.utcnow(), metadata_json=json.dumps(metadata, default=str)))
        NotificationAgent(db).notify(
            "Nexa Achievement Unlocked",
            description,
            alert_type="achievement",
            module="achievement_system",
            severity="low",
            priority="medium",
            category="success",
            suggested_action="Open achievements to view your badge.",
            action_buttons=["View Achievement", "Dismiss"],
            metadata=metadata,
        )

    def _file_digest(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _downloads_root(self, folder: str | None = None, must_exist: bool = True) -> Path:
        root = Path(folder).expanduser() if folder else Path.home() / "Downloads"
        root = root.resolve()
        if must_exist and not root.exists():
            raise ValueError("Downloads folder does not exist")
        return root

    def _download_files(self, root: Path) -> list[Path]:
        return [
            path
            for path in root.iterdir()
            if path.is_file() and path.suffix.lower() not in self.incomplete_download_suffixes and not path.name.startswith("~$")
        ]

    def _download_category(self, path: Path, db: Session | None = None) -> str:
        extension = path.suffix.lower()
        if db is not None:
            rules = db.query(DownloadRule).filter(DownloadRule.enabled.is_(True)).order_by(DownloadRule.priority.asc()).all()
            lower_name = path.name.lower()
            for rule in rules:
                pattern = rule.pattern.lower().strip()
                if rule.match_type == "extension" and extension == pattern:
                    return rule.category
                if rule.match_type == "name_contains" and pattern in lower_name:
                    return rule.category
                if rule.match_type == "mime":
                    mime_type = mimetypes.guess_type(path.name)[0] or ""
                    if mime_type.startswith(pattern):
                        return rule.category
        return self.download_categories.get(extension, "Others")

    def _category_folder(self, category: str) -> str:
        return {
            "PDF": "PDFs",
            "Archives": "Archives",
            "Images": "Images",
            "Videos": "Videos",
            "Audio": "Audio",
            "Documents": "Documents",
            "Programs": "Programs",
            "Code Files": "Code",
            "Spreadsheets": "Spreadsheets",
            "Presentations": "Presentations",
            "Ebooks": "Ebooks",
            "Others": "Others",
        }.get(category, category.replace(" ", "_") or "Others")

    def _unique_destination(self, destination: Path) -> Path:
        if not destination.exists():
            return destination
        stem = destination.stem
        suffix = destination.suffix
        parent = destination.parent
        counter = 2
        while True:
            candidate = parent / f"{stem} ({counter}){suffix}"
            if not candidate.exists():
                return candidate
            counter += 1

    def _download_file_metadata(self, path: Path, category: str, digest: str | None = None) -> dict:
        stat = path.stat()
        return {
            "file_path": str(path),
            "file_name": path.name,
            "category": category,
            "extension": path.suffix.lower(),
            "mime_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            "size_bytes": stat.st_size,
            "size_label": self._format_bytes(stat.st_size),
            "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "digest": digest or "",
        }

    def _upsert_download_history(self, db: Session, path: Path, category: str, size: int, duplicate: str, recommendation: str, status: str) -> DownloadHistory:
        existing = db.query(DownloadHistory).filter(DownloadHistory.file_path == str(path)).order_by(DownloadHistory.created_at.desc()).first()
        row = existing or DownloadHistory(file_path=str(path), file_name=path.name)
        row.file_path = str(path)
        row.file_name = path.name
        row.category = category
        row.size_bytes = size
        row.duplicate_of = duplicate
        row.recommendation = recommendation
        row.status = status
        if not existing:
            db.add(row)
        db.flush()
        return row

    def _record_cleanup_suggestion(self, db: Session, path: Path, suggestion_type: str, title: str, message: str, size: int, severity: str, metadata: dict) -> CleanupSuggestion:
        existing = db.query(CleanupSuggestion).filter(CleanupSuggestion.file_path == str(path), CleanupSuggestion.suggestion_type == suggestion_type, CleanupSuggestion.status == "open").first()
        row = existing or CleanupSuggestion(file_path=str(path), suggestion_type=suggestion_type, title=title)
        row.title = title
        row.message = message
        row.size_bytes = size
        row.severity = severity
        row.metadata_json = json.dumps(metadata, default=str)
        if not existing:
            db.add(row)
        db.flush()
        return row

    def _record_download_analytics(self, db: Session, category_stats: dict[str, dict]) -> None:
        today = date.today().isoformat()
        for category, stats in category_stats.items():
            row = db.query(DownloadAnalytics).filter(DownloadAnalytics.analytics_date == today, DownloadAnalytics.category == category).first()
            if row is None:
                row = DownloadAnalytics(analytics_date=today, category=category)
                db.add(row)
            row.file_count = stats["file_count"]
            row.total_size_bytes = stats["total_size_bytes"]
            row.large_file_count = stats["large_file_count"]
            row.duplicate_count = stats["duplicate_count"]

    def _notify_download_event(self, db: Session, title: str, message: str, suggested_action: str, category: str) -> None:
        severity = "medium" if category in {"warning", "critical"} else "low"
        NotificationAgent(db).notify(
            f"Nexa Download Manager: {title}",
            message,
            alert_type="download_manager",
            module="download_manager",
            severity=severity,
            priority=severity,
            category=category,
            suggested_action=suggested_action,
            action_buttons=["Open Download Manager", "Dismiss"],
            voice_message="Download manager needs your attention." if category == "warning" else "",
            metadata={"source": "smart_download_manager"},
        )

    def _extract_size_threshold(self, text: str, default: int) -> int:
        import re

        match = re.search(r"(\d+(?:\.\d+)?)\s*(gb|mb)", text)
        if not match:
            return default
        value = float(match.group(1))
        unit = match.group(2)
        return int(value * (1024 ** 3 if unit == "gb" else 1024 ** 2))

    def _query_category(self, text: str) -> str | None:
        aliases = {
            "pdf": "PDF",
            "pdfs": "PDF",
            "zip": "Archives",
            "zips": "Archives",
            "archive": "Archives",
            "archives": "Archives",
            "image": "Images",
            "images": "Images",
            "video": "Videos",
            "videos": "Videos",
            "audio": "Audio",
            "music": "Audio",
            "document": "Documents",
            "documents": "Documents",
            "program": "Programs",
            "installer": "Programs",
            "installers": "Programs",
            "code": "Code Files",
            "spreadsheet": "Spreadsheets",
            "presentation": "Presentations",
            "ebook": "Ebooks",
        }
        return next((category for token, category in aliases.items() if token in text), None)

    def _download_statistics(self, recent: list[dict], analytics: dict, duplicates: list[dict], cleanup: list[dict]) -> dict:
        return {
            "files_indexed": len(recent),
            "storage_indexed_bytes": sum(item.get("size_bytes", 0) for item in recent),
            "storage_indexed_label": self._format_bytes(sum(item.get("size_bytes", 0) for item in recent)),
            "duplicates": len(duplicates),
            "cleanup_suggestions": len(cleanup),
            "categories": len(analytics.get("by_category", [])),
            "health_score": max(0, 100 - min(40, len(duplicates) * 5) - min(30, len(cleanup) * 3)),
        }

    def _format_bytes(self, value: int) -> str:
        size = float(value)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024 or unit == "TB":
                return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
            size /= 1024

    def _try_local_ocr(self, path: Path, language: str = "eng") -> str:
        try:
            import pytesseract
            from PIL import Image

            return pytesseract.image_to_string(Image.open(path), lang=language or "eng").strip()
        except Exception:
            return ""

    def _analyze_screenshot_text(self, path: Path, text: str) -> dict:
        lower = text.lower()
        error = self._screenshot_error_analysis(text)
        document_type = self._screenshot_document_type(lower)
        key_points = self._extract_key_points(text)
        study_notes = self._study_notes_from_text(text, document_type)
        if text:
            if error:
                summary = f"{error['error_type']} detected. Probable cause: {error['probable_cause']}"
            elif document_type == "result":
                summary = "Result or marks page detected. Nexa extracted the important visible details for review."
            elif document_type == "website":
                summary = "Website screenshot detected. Nexa extracted visible page text, links, forms, and possible actions."
            elif document_type == "code":
                summary = "Code screenshot detected. Nexa extracted code context and stored it for explanation or review."
            elif document_type == "document":
                summary = "Document or study material detected. Nexa generated a local summary and study notes."
            elif document_type == "ui_issue":
                summary = "Application or UI issue detected. Nexa generated troubleshooting steps."
            else:
                summary = "Screenshot text was extracted and stored for search and summarization."
        else:
            summary = "Screenshot captured and saved. Local OCR is unavailable or did not extract readable text."
        return {"summary": summary, "error": error, "document_type": document_type, "key_points": key_points, "study_notes": study_notes, "ocr_confidence": 0.8 if text else 0.0}

    def _screenshot_tags(self, path: Path, text: str, analysis: str, local_analysis: dict) -> list[str]:
        tags = ["screenshot", local_analysis["document_type"]]
        lower = f"{text} {analysis}".lower()
        if local_analysis.get("error") or any(token in lower for token in ["error", "exception", "traceback", "failed"]):
            tags.append("error")
        if local_analysis["document_type"] in {"code", "ui_issue"} or path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            tags.append("visual")
        if "result" in lower or "marks" in lower or "attendance" in lower:
            tags.append("result")
        return sorted(set(tags))

    def _screenshot_error_analysis(self, text: str) -> dict | None:
        lower = text.lower()
        markers = ["traceback", "exception", "error:", "failed", "syntaxerror", "typeerror", "referenceerror", "ts", "npm err", "fatal:"]
        if not any(marker in lower for marker in markers):
            return None
        language = "Python" if "traceback" in lower or ".py" in lower or "syntaxerror" in lower else "JavaScript/TypeScript" if "npm" in lower or "react" in lower or "typescript" in lower or "referenceerror" in lower else "Git" if "fatal:" in lower or "git" in lower else "Unknown"
        framework = "React" if "react" in lower or "jsx" in lower or "tsx" in lower else "Electron" if "electron" in lower else "Node" if "npm" in lower or "node" in lower else ""
        error_type = "Build Error" if "build" in lower or "npm err" in lower else "Runtime Error" if "traceback" in lower or "exception" in lower else "Git Error" if "fatal:" in lower else "Code Error"
        fixes = [
            "Read the first error line and fix the earliest failing file or command.",
            "Check imports, missing dependencies, and mismatched function or variable names.",
            "Re-run the failing command after the smallest targeted fix.",
        ]
        if language == "Python":
            fixes.insert(1, "Verify the traceback file path and line number, then inspect the variable or import named there.")
        if framework == "React":
            fixes.insert(1, "Check component props, hook usage, TypeScript types, and build output around the referenced file.")
        if language == "Git":
            fixes.insert(1, "Check repository state with git status before retrying the operation.")
        return {"error_type": error_type, "language": language, "framework": framework, "probable_cause": self._first_meaningful_line(text) or "A command or application reported an error.", "suggested_fixes": fixes, "severity": "high" if "critical" in lower or "fatal" in lower else "medium"}

    def _screenshot_document_type(self, lower: str) -> str:
        if any(token in lower for token in ["traceback", "exception", "syntaxerror", "typeerror", "npm err", "fatal:"]):
            return "code"
        if any(token in lower for token in ["http://", "https://", "login", "submit", "button", "form", "website"]):
            return "website"
        if any(token in lower for token in ["kcet", "result", "marks", "attendance", "rank", "score"]):
            return "result"
        if any(token in lower for token in ["question", "assignment", "chapter", "unit", "exam", "timetable", "notes"]):
            return "document"
        if any(token in lower for token in ["dialog", "install", "missing", "not responding", "layout", "button not"]):
            return "ui_issue"
        if any(token in lower for token in ["function", "class ", "const ", "import ", "def "]):
            return "code"
        return "general"

    def _extract_text_entities(self, text: str) -> dict:
        import re

        return {
            "urls": re.findall(r"https?://[^\s)]+", text),
            "emails": re.findall(r"[\w.\-+]+@[\w.\-]+\.\w+", text),
            "dates": re.findall(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b", text),
            "numbers": re.findall(r"\b\d+(?:\.\d+)?%?\b", text)[:50],
        }

    def _extract_key_points(self, text: str, limit: int = 6) -> list[str]:
        lines = [line.strip(" -\t") for line in text.splitlines() if len(line.strip()) >= 8]
        if not lines and text:
            lines = [part.strip() for part in text.replace("\n", " ").split(".") if len(part.strip()) >= 8]
        return lines[:limit]

    def _study_notes_from_text(self, text: str, document_type: str) -> list[str]:
        points = self._extract_key_points(text, 5)
        if document_type not in {"document", "result", "code"}:
            return points[:3]
        return [f"Review: {point}" for point in points[:5]]

    def _first_meaningful_line(self, text: str) -> str:
        for line in text.splitlines():
            clean = line.strip()
            if clean and any(token in clean.lower() for token in ["error", "exception", "traceback", "failed", "fatal", "syntax"]):
                return clean[:300]
        return ""

    def _briefing_dict(self, row: DailyBriefing) -> dict:
        return {"id": row.id, "briefing_date": row.briefing_date, "title": row.title, "summary": row.summary, "payload": _loads(row.payload_json, {}), "spoken": row.spoken, "notification_id": row.notification_id, "created_at": row.created_at.isoformat()}

    def _briefing_history_dict(self, row: BriefingHistory) -> dict:
        return {
            "id": row.id,
            "briefing_id": row.briefing_id,
            "briefing_date": row.briefing_date,
            "delivery_method": row.delivery_method,
            "delivery_status": row.delivery_status,
            "content": _loads(row.content_json, {}),
            "statistics": _loads(row.statistics_json, {}),
            "recommendations": _loads(row.recommendations_json, []),
            "user_action": row.user_action,
            "created_at": row.created_at.isoformat(),
        }

    def _briefing_recommendation_dict(self, row: BriefingRecommendation) -> dict:
        return {
            "id": row.id,
            "briefing_id": row.briefing_id,
            "recommendation_type": row.recommendation_type,
            "title": row.title,
            "message": row.message,
            "priority": row.priority,
            "action": _loads(row.action_json, {}),
            "status": row.status,
            "created_at": row.created_at.isoformat(),
        }

    def _briefing_analytics_dict(self, row: BriefingAnalytics) -> dict:
        return {
            "id": row.id,
            "briefing_date": row.briefing_date,
            "coding_seconds": row.coding_seconds,
            "study_seconds": row.study_seconds,
            "tasks_total": row.tasks_total,
            "tasks_completed": row.tasks_completed,
            "unread_notifications": row.unread_notifications,
            "pending_approvals": row.pending_approvals,
            "goal_average_percent": row.goal_average_percent,
            "productivity_score": row.productivity_score,
            "insight": _loads(row.insight_json, {}),
            "created_at": row.created_at.isoformat(),
        }

    def _focus_dict(self, row: FocusSession) -> dict:
        return {"id": row.id, "title": row.title, "mode": row.mode, "status": row.status, "started_at": row.started_at.isoformat(), "ended_at": _iso(row.ended_at), "duration_seconds": row.duration_seconds, "break_seconds": row.break_seconds, "tasks_completed": row.tasks_completed, "distraction_count": row.distraction_count, "productivity_score": row.productivity_score, "detail": _loads(row.detail_json, {})}

    def _focus_goal_dict(self, row: FocusGoal) -> dict:
        return {"id": row.id, "session_id": row.session_id, "title": row.title, "goal_type": row.goal_type, "target_minutes": row.target_minutes, "completed_minutes": row.completed_minutes, "completion_percent": row.completion_percent, "status": row.status, "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat()}

    def _focus_history_dict(self, row: FocusHistory) -> dict:
        return {"id": row.id, "session_id": row.session_id, "event_type": row.event_type, "detail": _loads(row.detail_json, {}), "created_at": row.created_at.isoformat()}

    def _focus_analytics_dict(self, row: FocusAnalytics) -> dict:
        return {"id": row.id, "session_id": row.session_id, "focus_seconds": row.focus_seconds, "break_seconds": row.break_seconds, "distraction_count": row.distraction_count, "tasks_completed": row.tasks_completed, "goal_completion_percent": row.goal_completion_percent, "productivity_score": row.productivity_score, "recommendations": _loads(row.recommendations_json, []), "created_at": row.created_at.isoformat()}

    def _blocked_site_dict(self, row: BlockedSite) -> dict:
        return {"id": row.id, "domain": row.domain, "enabled": row.enabled, "category": row.category, "reason": row.reason, "created_at": row.created_at.isoformat()}

    def _blocked_app_dict(self, row: BlockedApp) -> dict:
        return {"id": row.id, "app_name": row.app_name, "enabled": row.enabled, "category": row.category, "reason": row.reason, "created_at": row.created_at.isoformat()}

    def _days_until(self, raw_date: str) -> int | None:
        if not raw_date:
            return None
        try:
            return (date.fromisoformat(raw_date) - date.today()).days
        except ValueError:
            return None

    def _build_daily_study_plan(self, topics: list[str], days_available: int | None, minutes_per_day: int) -> list[dict]:
        if not topics:
            return []
        days = max(1, days_available or len(topics))
        plan = []
        for index, topic in enumerate(topics):
            day_offset = min(index, max(days - 1, 0))
            phase = "study"
            if days <= 3 or index >= max(0, len(topics) - 2):
                phase = "revision"
            plan.append(
                {
                    "day": day_offset + 1,
                    "date": (date.today() + timedelta(days=day_offset)).isoformat(),
                    "topic": topic,
                    "phase": phase,
                    "estimated_minutes": max(30, min(120, minutes_per_day // max(1, min(3, len(topics))))),
                    "status": "pending",
                }
            )
        if days >= 5:
            plan.append({"day": max(1, days - 1), "date": (date.today() + timedelta(days=max(0, days - 2))).isoformat(), "topic": "Practice test", "phase": "practice", "estimated_minutes": min(180, minutes_per_day), "status": "pending"})
            plan.append({"day": days, "date": (date.today() + timedelta(days=max(0, days - 1))).isoformat(), "topic": "Final revision", "phase": "final_revision", "estimated_minutes": min(180, minutes_per_day), "status": "pending"})
        return plan

    def _ensure_revision_plan(self, db: Session, subject_id: int, chapter_id: int | None, title: str, exam_date: str = "") -> None:
        existing = db.query(RevisionPlan).filter(RevisionPlan.subject_id == subject_id, RevisionPlan.chapter_id == chapter_id, RevisionPlan.title == title).first()
        if existing:
            return
        today = date.today()
        dates = [
            ("first_revision", today + timedelta(days=1)),
            ("second_revision", today + timedelta(days=3)),
            ("final_revision", date.fromisoformat(exam_date) - timedelta(days=1) if exam_date else today + timedelta(days=7)),
        ]
        for plan_type, scheduled in dates:
            db.add(RevisionPlan(subject_id=subject_id, chapter_id=chapter_id, plan_type=plan_type, title=title, scheduled_date=scheduled.isoformat(), estimated_minutes=45 if plan_type != "final_revision" else 90))

    def _recalculate_subject(self, db: Session, subject_id: int) -> None:
        subject = db.get(StudySubject, subject_id)
        if not subject:
            return
        chapters = db.query(StudyChapter).filter(StudyChapter.subject_id == subject_id).all()
        completion = round(sum(item.completion_percent for item in chapters) / max(len(chapters), 1), 2)
        days_remaining = self._days_until(subject.exam_date)
        urgency_bonus = 0 if days_remaining is None else max(0, 20 - min(20, days_remaining))
        subject.completion_percent = completion
        subject.readiness_score = round(max(0, min(100, completion * 0.75 + min(25, len([c for c in chapters if c.last_studied_at]) * 5) - urgency_bonus * 0.2)), 2)
        subject.updated_at = datetime.utcnow()
        db.commit()

    def _update_study_analytics(self, db: Session, session: StudySession) -> None:
        analytics_date = session.created_at.date().isoformat()
        row = db.query(StudyAnalytics).filter(StudyAnalytics.analytics_date == analytics_date, StudyAnalytics.subject_id == session.subject_id).one_or_none()
        if not row:
            row = StudyAnalytics(analytics_date=analytics_date, subject_id=session.subject_id)
            db.add(row)
        row.study_seconds = int(row.study_seconds or 0) + int(session.duration_seconds or 0)
        row.revision_seconds = int(row.revision_seconds or 0) + int(session.revision_seconds or 0)
        row.practice_seconds = int(row.practice_seconds or 0) + int(session.practice_seconds or 0)
        row.topics_completed = int(row.topics_completed or 0)
        row.readiness_score = self._study_readiness_for_subject(db, session.subject_id)
        row.recommendations_json = json.dumps(self.study_recommendations(db)[:3], default=str)
        db.commit()

    def _study_readiness_for_subject(self, db: Session, subject_id: int | None) -> float:
        if not subject_id:
            return 0
        subject = db.get(StudySubject, subject_id)
        return subject.readiness_score if subject else 0

    def _unlock_study_achievement(self, db: Session, title: str, category: str, description: str, metadata: dict | None = None) -> None:
        existing = db.query(StudyAchievement).filter(StudyAchievement.title == title, StudyAchievement.description == description).one_or_none()
        if existing:
            return
        row = StudyAchievement(title=title, category=category, description=description, metadata_json=json.dumps(metadata or {}, default=str))
        db.add(row)
        db.commit()
        NotificationAgent(db).notify(
            "Nexa Study Achievement",
            description,
            alert_type="study_achievement",
            module="study_assistant",
            severity="low",
            priority="low",
            category="success",
            suggested_action="Review your study dashboard.",
            action_buttons=["Open Study Dashboard", "Dismiss"],
            metadata=metadata or {},
        )

    def _evaluate_study_achievements(self, db: Session) -> None:
        study_days = {row.created_at.date().isoformat() for row in db.query(StudySession).all()}
        if len(study_days) >= 7:
            self._unlock_study_achievement(db, "7 Day Study Streak", "Streak", "Recorded study sessions across 7 days.", {"study_days": len(study_days)})
        completed_subjects = db.query(StudySubject).filter(StudySubject.completion_percent >= 100).all()
        for subject in completed_subjects:
            self._unlock_study_achievement(db, "Completed Subject", "Progress", f"Completed {subject.name}.", {"subject_id": subject.id})

    def _study_subject_dict(self, row: StudySubject | None, db: Session) -> dict:
        if not row:
            return {}
        chapters = db.query(StudyChapter).filter(StudyChapter.subject_id == row.id).all()
        sessions = db.query(StudySession).filter(StudySession.subject_id == row.id).order_by(StudySession.created_at.desc()).all()
        last_session = sessions[0] if sessions else None
        days_remaining = self._days_until(row.exam_date)
        return {
            "id": row.id,
            "name": row.name,
            "priority": row.priority,
            "difficulty": row.difficulty,
            "exam_date": row.exam_date,
            "days_remaining": days_remaining,
            "hours_remaining": None if days_remaining is None else max(0, days_remaining * 24),
            "target_score": row.target_score,
            "completion_percent": row.completion_percent,
            "readiness_score": row.readiness_score,
            "preparation_status": "ready" if row.readiness_score >= 80 else "needs_attention" if row.readiness_score < 50 else "on_track",
            "chapters_completed": len([item for item in chapters if item.completion_percent >= 100]),
            "chapters_total": len(chapters),
            "study_seconds": sum(item.duration_seconds for item in sessions),
            "revision_seconds": sum(item.revision_seconds for item in sessions),
            "practice_seconds": sum(item.practice_seconds for item in sessions),
            "days_since_studied": None if not last_session else (date.today() - last_session.created_at.date()).days,
            "chapters": [self._study_chapter_dict(item) for item in chapters],
            "status": row.status,
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
        }

    def _study_chapter_dict(self, row: StudyChapter) -> dict:
        return {"id": row.id, "subject_id": row.subject_id, "unit": row.unit, "title": row.title, "topics": _loads(row.topics_json, []), "priority": row.priority, "difficulty": row.difficulty, "completion_percent": row.completion_percent, "status": row.status, "last_studied_at": _iso(row.last_studied_at), "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat()}

    def _study_session_dict(self, row: StudySession) -> dict:
        return {"id": row.id, "subject_id": row.subject_id, "chapter_id": row.chapter_id, "subject_name": row.subject_name, "chapter_title": row.chapter_title, "topic": row.topic, "session_type": row.session_type, "duration_seconds": row.duration_seconds, "revision_seconds": row.revision_seconds, "practice_seconds": row.practice_seconds, "focus_session_id": row.focus_session_id, "notes": row.notes, "started_at": row.started_at.isoformat(), "ended_at": _iso(row.ended_at), "created_at": row.created_at.isoformat()}

    def _study_goal_dict(self, row: StudyGoal) -> dict:
        return {"id": row.id, "subject_id": row.subject_id, "title": row.title, "goal_type": row.goal_type, "target_value": row.target_value, "current_value": row.current_value, "unit": row.unit, "deadline": row.deadline, "progress_percent": row.progress_percent, "status": row.status, "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat()}

    def _exam_schedule_dict(self, row: ExamSchedule, db: Session) -> dict:
        subject = db.get(StudySubject, row.subject_id) if row.subject_id else None
        days = self._days_until(row.exam_date)
        readiness = subject.readiness_score if subject else row.readiness_score
        return {"id": row.id, "subject_id": row.subject_id, "subject_name": subject.name if subject else "", "title": row.title, "exam_date": row.exam_date, "days_remaining": days, "hours_remaining": None if days is None else max(0, days * 24), "exam_type": row.exam_type, "target_score": row.target_score, "readiness_score": readiness, "preparation_status": "ready" if readiness >= 80 else "needs_attention" if readiness < 50 else "on_track", "status": row.status, "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat()}

    def _revision_plan_dict(self, row: RevisionPlan, db: Session) -> dict:
        subject = db.get(StudySubject, row.subject_id) if row.subject_id else None
        chapter = db.get(StudyChapter, row.chapter_id) if row.chapter_id else None
        return {"id": row.id, "subject_id": row.subject_id, "subject_name": subject.name if subject else "", "chapter_id": row.chapter_id, "chapter_title": chapter.title if chapter else row.title, "plan_type": row.plan_type, "title": row.title, "scheduled_date": row.scheduled_date, "estimated_minutes": row.estimated_minutes, "status": row.status, "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat()}

    def _study_analytics_dict(self, row: StudyAnalytics) -> dict:
        return {"id": row.id, "analytics_date": row.analytics_date, "subject_id": row.subject_id, "study_seconds": row.study_seconds, "revision_seconds": row.revision_seconds, "practice_seconds": row.practice_seconds, "topics_completed": row.topics_completed, "readiness_score": row.readiness_score, "recommendations": _loads(row.recommendations_json, []), "created_at": row.created_at.isoformat()}

    def _study_achievement_dict(self, row: StudyAchievement) -> dict:
        return {"id": row.id, "title": row.title, "category": row.category, "description": row.description, "unlocked": row.unlocked, "metadata": _loads(row.metadata_json, {}), "created_at": row.created_at.isoformat()}

    def _study_plan_dict(self, row: StudyPlan, db: Session) -> dict:
        progress = db.query(StudyProgress).filter(StudyProgress.plan_id == row.id).all()
        exam_countdown_days = None
        if row.exam_date:
            try:
                exam_countdown_days = (date.fromisoformat(row.exam_date) - date.today()).days
            except ValueError:
                exam_countdown_days = None
        missed_topics = [item.topic for item in progress if item.progress_percent < 100]
        revision_plan = [{"topic": item.topic, "next_revision": (item.updated_at.date() + timedelta(days=max(1, 3 - item.revision_count))).isoformat()} for item in progress]
        return {"id": row.id, "title": row.title, "exam_date": row.exam_date, "exam_countdown_days": exam_countdown_days, "syllabus": _loads(row.syllabus_json, []), "daily_plan": _loads(row.daily_plan_json, []), "revision_plan": revision_plan, "missed_topics": missed_topics, "status": row.status, "progress_percent": row.progress_percent, "progress": [{"id": item.id, "topic": item.topic, "status": item.status, "revision_count": item.revision_count, "progress_percent": item.progress_percent, "notes": item.notes, "updated_at": item.updated_at.isoformat()} for item in progress], "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat()}

    def _memory_importance(self, event_type: str, title: str, duration_seconds: int = 0, metadata: dict | None = None) -> float:
        base = {
            "coding": 70,
            "study": 75,
            "focus": 65,
            "goal": 85,
            "automation": 55,
            "download": 45,
            "college": 70,
            "project": 80,
            "achievement": 90,
            "briefing": 40,
            "notification": 30,
        }.get(event_type, 45)
        lowered = title.lower()
        if any(word in lowered for word in ["completed", "achieved", "finished", "created", "exam", "backup", "submitted"]):
            base += 15
        if duration_seconds >= 3600:
            base += 10
        if metadata and metadata.get("important"):
            base += 20
        return round(max(0, min(100, base)), 2)

    def _memory_category(self, event_type: str) -> str:
        return {
            "coding": "Coding",
            "study": "Study",
            "focus": "Focus",
            "goal": "Goals",
            "automation": "Automations",
            "download": "Downloads",
            "college": "College",
            "project": "Projects",
            "achievement": "Achievements",
            "briefing": "Briefings",
        }.get(event_type, "General")

    def _timeline_range(self, period: str, reference_date: str | None = None) -> tuple[date, date]:
        ref = date.fromisoformat(reference_date) if reference_date else date.today()
        if period == "week":
            start = ref - timedelta(days=ref.weekday())
            return start, start + timedelta(days=6)
        if period == "month":
            start = ref.replace(day=1)
            next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
            return start, next_month - timedelta(days=1)
        if period == "year":
            return ref.replace(month=1, day=1), ref.replace(month=12, day=31)
        return ref, ref

    def _timeline_stats(self, events: list[dict]) -> dict:
        by_type: dict[str, int] = {}
        duration_by_type: dict[str, int] = {}
        projects: set[str] = set()
        for event in events:
            event_type = event["event_type"]
            by_type[event_type] = by_type.get(event_type, 0) + 1
            duration_by_type[event_type] = duration_by_type.get(event_type, 0) + int(event.get("duration_seconds") or 0)
            if event.get("project"):
                projects.add(event["project"])
        return {
            "total_events": len(events),
            "by_type": by_type,
            "duration_by_type": duration_by_type,
            "coding_seconds": duration_by_type.get("coding", 0),
            "study_seconds": duration_by_type.get("study", 0),
            "focus_seconds": duration_by_type.get("focus", 0),
            "tasks_completed": len([event for event in events if event["event_type"] == "task" and "completed" in event["title"].lower()]),
            "goals_achieved": len([event for event in events if event["event_type"] == "goal" and ("achieved" in event["title"].lower() or "completed" in event["title"].lower())]),
            "achievements": len([event for event in events if "achievement" in event["event_type"] or "achieved" in event["title"].lower()]),
            "projects": sorted(projects),
        }

    def _timeline_highlights(self, events: list[dict]) -> list[dict]:
        ranked = sorted(events, key=lambda item: item.get("metadata", {}).get("importance", 0), reverse=True)
        return ranked[:8]

    def _timeline_recommendations(self, stats: dict) -> list[dict]:
        recommendations = []
        if stats.get("study_seconds", 0) == 0:
            recommendations.append({"type": "study", "message": "No study time recorded in this period. Schedule one focused study session."})
        if stats.get("coding_seconds", 0) == 0:
            recommendations.append({"type": "coding", "message": "No coding time recorded in this period. Record coding work or start a focus session."})
        if stats.get("goals_achieved", 0) == 0:
            recommendations.append({"type": "goal", "message": "No goals were completed. Pick one small goal to finish next."})
        if not recommendations:
            recommendations.append({"type": "momentum", "message": "Good activity balance. Keep recording meaningful milestones."})
        return recommendations

    def _timeline_summary_text(self, period: str, stats: dict, highlights: list[dict]) -> str:
        coding = self._duration(stats.get("coding_seconds", 0))
        study = self._duration(stats.get("study_seconds", 0))
        focus = self._duration(stats.get("focus_seconds", 0))
        return f"{period.title()} summary: {stats.get('total_events', 0)} meaningful events, {coding} coding, {study} study, {focus} focus, {stats.get('goals_achieved', 0)} goals achieved, and {stats.get('achievements', 0)} achievements."

    def _memory_search_summary(self, query: str, results: list[dict]) -> str:
        if not results:
            return f"No timeline memories matched '{query}'."
        stats = self._timeline_stats(results)
        return f"Found {len(results)} memories: {self._duration(stats.get('coding_seconds', 0))} coding, {self._duration(stats.get('study_seconds', 0))} study, {stats.get('goals_achieved', 0)} goals achieved."

    def _generate_timeline_insights(self, db: Session, period: str, stats: dict) -> None:
        insights = []
        if stats.get("study_seconds", 0) > stats.get("coding_seconds", 0):
            insights.append(("study_trend", "Study led this period", "Study time exceeded coding time.", "Keep revision and practice balanced."))
        if stats.get("focus_seconds", 0) >= 3600:
            insights.append(("focus_trend", "Strong focus time", "You recorded at least one hour of focus time.", "Use breaks to sustain momentum."))
        if stats.get("goals_achieved", 0) > 0:
            insights.append(("goal_progress", "Goal progress improved", "At least one goal was achieved.", "Capture the next goal while momentum is high."))
        for insight_type, title, message, recommendation in insights:
            exists = db.query(TimelineInsight).filter(TimelineInsight.insight_type == insight_type, TimelineInsight.title == title).order_by(TimelineInsight.created_at.desc()).first()
            if exists and (datetime.utcnow() - exists.created_at).total_seconds() < 3600:
                continue
            db.add(TimelineInsight(insight_type=insight_type, title=title, message=message, severity="low", recommendation=recommendation, metadata_json=json.dumps({"period": period}, default=str)))
        db.commit()

    def _memory_categories(self, db: Session) -> list[dict]:
        defaults = [
            ("Coding", "Development work and project activity", "#38bdf8", "code"),
            ("Study", "Study sessions, chapters, exams, revisions", "#facc15", "book"),
            ("Focus", "Focus sessions, breaks, distractions", "#a78bfa", "timer"),
            ("Goals", "Goal progress and completions", "#34d399", "target"),
            ("College", "College updates, attendance, results", "#fb7185", "graduation"),
            ("Projects", "Backups, commits, milestones", "#60a5fa", "briefcase"),
        ]
        for name, description, color, icon in defaults:
            if not db.query(MemoryCategory).filter(MemoryCategory.name == name).first():
                db.add(MemoryCategory(name=name, description=description, color=color, icon=icon))
        db.commit()
        return [{"id": row.id, "name": row.name, "description": row.description, "color": row.color, "icon": row.icon, "created_at": row.created_at.isoformat()} for row in db.query(MemoryCategory).order_by(MemoryCategory.name.asc()).all()]

    def _timeline_summary_dict(self, row: TimelineSummary) -> dict:
        return {"id": row.id, "period": row.period, "start_date": row.start_date, "end_date": row.end_date, "summary": row.summary, "stats": _loads(row.stats_json, {}), "highlights": _loads(row.highlights_json, []), "recommendations": _loads(row.recommendations_json, []), "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat()}

    def _timeline_insight_dict(self, row: TimelineInsight) -> dict:
        return {"id": row.id, "insight_type": row.insight_type, "title": row.title, "message": row.message, "severity": row.severity, "recommendation": row.recommendation, "metadata": _loads(row.metadata_json, {}), "created_at": row.created_at.isoformat()}

    def _timeline_dict(self, row: TimelineEvent) -> dict:
        return {"id": row.id, "event_type": row.event_type, "title": row.title, "description": row.description, "source": row.source, "project": row.project, "duration_seconds": row.duration_seconds, "metadata": _loads(row.metadata_json, {}), "created_at": row.created_at.isoformat()}

    def _ensure_project(self, db: Session, source: Path) -> Project:
        row = db.query(Project).filter(Project.path == str(source)).order_by(Project.updated_at.desc()).first()
        git_status = self.git_status(str(source))
        if not row:
            row = Project(name=source.name, path=str(source), project_type="git" if git_status.get("is_git_repo") else "code")
            db.add(row)
            db.flush()
        row.name = source.name
        row.git_branch = git_status.get("branch", "")
        row.commit_hash = git_status.get("commit_hash", "")
        row.metadata_json = json.dumps({"is_git_repo": git_status.get("is_git_repo", False)}, default=str)
        row.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        return row

    def _create_project_backup(self, source: Path, action: str) -> Path:
        backup_root = Path.home() / "NexaBackups" / "ProjectGuardian"
        backup_root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        safe_action = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in action)[:80]
        destination = backup_root / f"{source.name}-{safe_action}-{stamp}"
        if source.is_dir():
            shutil.copytree(source, destination, ignore=self._project_ignore)
        else:
            destination = backup_root / f"{source.stem}-{safe_action}-{stamp}{source.suffix}"
            shutil.copy2(source, destination)
        return destination

    def _project_ignore(self, directory: str, names: list[str]) -> set[str]:
        ignored = {
            "node_modules",
            ".git",
            "__pycache__",
            ".venv",
            "dist",
            "build",
            ".next",
            ".turbo",
            ".cache",
            ".env",
            ".env.local",
            ".env.production",
            "id_rsa",
            "id_ed25519",
        }
        return {name for name in names if name in ignored or name.endswith((".pem", ".key", ".pfx"))}

    def _record_project_event(self, db: Session, project_id: int | None, event_type: str, title: str, message: str = "", severity: str = "low", metadata: dict | None = None) -> None:
        db.add(ProjectEvent(project_id=project_id, event_type=event_type, title=title, message=message, severity=severity, metadata_json=json.dumps(metadata or {}, default=str)))

    def _capture_recovery_session_row(self, db: Session, session_type: str, applications: list[dict], project_path: str | None = None, commit: bool = True) -> RecoverySession:
        root = Path(project_path).expanduser().resolve() if project_path else Path.cwd()
        workspace_state = {
            "workspace_path": str(root),
            "captured_at": datetime.utcnow().isoformat(),
            "applications": applications,
            "git_status": self.git_status(str(root)) if root.exists() else {"is_git_repo": False},
            "tasks_active": db.query(Task).filter(Task.status.in_(["created", "running", "pending_confirmation"])).count(),
        }
        restore_plan = []
        normalized_apps = applications or [{"name": "Workspace", "process": "", "workspace_path": str(root)}]
        for item in normalized_apps:
            app_name = item.get("name") or item.get("app_name") or "Workspace"
            app_workspace = item.get("workspace_path") or str(root)
            restore_command = self._restore_command_for_application(app_name, app_workspace)
            restore_plan.append({"application": app_name, "workspace_path": app_workspace, "command": restore_command, "requires_user_review": True})
        session = RecoverySession(session_type=session_type, workspace_state_json=json.dumps(workspace_state, default=str), restore_plan_json=json.dumps(restore_plan, default=str), metadata_json=json.dumps({"project_path": str(root), "offline_ready": True}, default=str))
        db.add(session)
        db.flush()
        for item in normalized_apps:
            app_name = item.get("name") or item.get("app_name") or "Workspace"
            workspace_path = item.get("workspace_path") or str(root)
            db.add(
                RecoveredApplication(
                    session_id=session.id,
                    app_name=app_name,
                    process_name=item.get("process") or item.get("process_name") or self._process_for_application(app_name),
                    workspace_path=workspace_path,
                    open_files_json=json.dumps(item.get("open_files", []), default=str),
                    terminal_state_json=json.dumps(item.get("terminal") or item.get("terminal_state") or {}, default=str),
                    restore_command=self._restore_command_for_application(app_name, workspace_path),
                    metadata_json=json.dumps(item, default=str),
                )
            )
        db.add(RecoveryHistory(event_type="session_captured", title="Recovery session captured", message=f"Captured {session_type} recovery state.", metadata_json=json.dumps({"session_id": session.id, "project_path": str(root)}, default=str)))
        if commit:
            db.commit()
            db.refresh(session)
        return session

    def _record_recovery_event(self, db: Session, event_type: str, title: str, message: str, severity: str = "medium", metadata: dict | None = None) -> None:
        db.add(RecoveryEvent(event_type=event_type, title=title, message=message, severity=severity, metadata_json=json.dumps(metadata or {}, default=str)))
        db.add(RecoveryHistory(event_type=event_type, title=title, message=message, status="recorded", metadata_json=json.dumps(metadata or {}, default=str)))
        self._write_recovery_log("system_events.log", f"{event_type}: {title} - {message}")

    def _application_from_crash_type(self, crash_type: str) -> str:
        lowered = crash_type.lower()
        if "vscode" in lowered or "vs_code" in lowered:
            return "VS Code"
        if "cursor" in lowered:
            return "Cursor"
        if "terminal" in lowered:
            return "Terminal"
        if "bsod" in lowered or "power" in lowered or "shutdown" in lowered:
            return "Windows"
        if "nexa" in lowered:
            return "Nexa"
        return ""

    def _process_for_application(self, application: str) -> str:
        lookup = {"vs code": "Code.exe", "vscode": "Code.exe", "cursor": "Cursor.exe", "terminal": "WindowsTerminal.exe", "windows": "System", "nexa": "Nexa.exe"}
        return lookup.get(application.lower(), "")

    def _restore_command_for_application(self, application: str, workspace_path: str) -> str:
        lower = application.lower()
        if "code" in lower:
            return f'code "{workspace_path}"'
        if "cursor" in lower:
            return f'cursor "{workspace_path}"'
        if "terminal" in lower:
            return f'wt -d "{workspace_path}"'
        if application == "Workspace":
            return f'open "{workspace_path}"'
        return ""

    def _recovery_recommendations_for(self, crash_type: str, application: str) -> list[str]:
        recommendations = ["Review the recovery dashboard before reopening sensitive files.", "Create or refresh Project Guardian snapshots for active projects."]
        if application.lower() in {"vs code", "cursor"}:
            recommendations.append("Reopen the captured workspace and check Git status before continuing.")
        if "power" in crash_type.lower() or "bsod" in crash_type.lower() or "shutdown" in crash_type.lower():
            recommendations.append("Check Windows reliability history and battery/power events.")
        if application.lower() == "terminal":
            recommendations.append("Review recent terminal commands before retrying failed operations.")
        return recommendations

    def _write_recovery_log(self, file_name: str, message: str) -> None:
        stamp = datetime.utcnow().isoformat()
        for root in (Path("logs"), Path("backend/logs")):
            try:
                root.mkdir(parents=True, exist_ok=True)
                with (root / file_name).open("a", encoding="utf-8") as handle:
                    handle.write(f"{stamp} {message}\n")
            except OSError:
                logger.exception("Failed to write recovery log")

    def _extract_number(self, text: str, default: int) -> int:
        match = re.search(r"(\d+)", text)
        return int(match.group(1)) if match else default

    def _extract_minutes(self, text: str, default: int) -> int:
        match = re.search(r"(\d+)\s*(minute|minutes|min|mins)", text)
        if match:
            return int(match.group(1))
        if "hour" in text:
            hour = re.search(r"(\d+)\s*(hour|hours)", text)
            return int(hour.group(1)) * 60 if hour else default
        return default

    def _setting_value(self, db: Session, key: str, default: str = "") -> str:
        row = db.query(Setting).filter(Setting.key == key).first()
        return row.value if row else default

    def _set_setting_value(self, db: Session, key: str, value: str) -> None:
        row = db.query(Setting).filter(Setting.key == key).first()
        if row is None:
            row = Setting(key=key, value=value)
            db.add(row)
        else:
            row.value = value
            row.updated_at = datetime.utcnow()

    def _project_dict(self, row: Project) -> dict:
        return {"id": row.id, "name": row.name, "path": row.path, "project_type": row.project_type, "git_branch": row.git_branch, "commit_hash": row.commit_hash, "last_backup_at": _iso(row.last_backup_at), "health_score": row.health_score, "status": row.status, "metadata": _loads(row.metadata_json, {}), "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat()}

    def _project_snapshot_dict(self, row: ProjectSnapshot) -> dict:
        return {"id": row.id, "project_id": row.project_id, "project_path": row.project_path, "project_name": row.project_name, "action": row.action, "git_status": _loads(row.git_status_json, {}), "modified_files": _loads(row.modified_files_json, []), "commit_hash": row.commit_hash, "branch_name": row.branch_name, "backup_path": row.backup_path, "metadata": _loads(row.metadata_json, {}), "status": row.status, "created_at": row.created_at.isoformat()}

    def _recovery_point_dict(self, row: RecoveryPoint) -> dict:
        return {"id": row.id, "project_id": row.project_id, "snapshot_id": row.snapshot_id, "backup_id": row.backup_id, "title": row.title, "restore_path": row.restore_path, "recovery_type": row.recovery_type, "status": row.status, "metadata": _loads(row.metadata_json, {}), "created_at": row.created_at.isoformat(), "restored_at": _iso(row.restored_at)}

    def _git_history_dict(self, row: GitHistory) -> dict:
        return {"id": row.id, "project_id": row.project_id, "project_path": row.project_path, "operation": row.operation, "branch_name": row.branch_name, "commit_hash": row.commit_hash, "status": _loads(row.status_json, {}), "snapshot_id": row.snapshot_id, "risk_level": row.risk_level, "created_at": row.created_at.isoformat()}

    def _project_health_dict(self, row: ProjectHealth) -> dict:
        return {"id": row.id, "project_id": row.project_id, "health_score": row.health_score, "uncommitted_files": row.uncommitted_files, "backup_age_hours": row.backup_age_hours, "risk_level": row.risk_level, "recommendations": _loads(row.recommendations_json, []), "created_at": row.created_at.isoformat()}

    def _project_event_dict(self, row: ProjectEvent) -> dict:
        return {"id": row.id, "project_id": row.project_id, "event_type": row.event_type, "title": row.title, "message": row.message, "severity": row.severity, "metadata": _loads(row.metadata_json, {}), "created_at": row.created_at.isoformat()}

    def _crash_report_dict(self, row: CrashReport) -> dict:
        return {"id": row.id, "crash_type": row.crash_type, "source": row.source, "application": row.application, "severity": row.severity, "message": row.message, "stack_trace": row.stack_trace, "diagnostics": _loads(row.diagnostics_json, {}), "status": row.status, "created_at": row.created_at.isoformat(), "resolved_at": _iso(row.resolved_at)}

    def _recovery_event_dict(self, row: RecoveryEvent) -> dict:
        return {"id": row.id, "event_type": row.event_type, "source": row.source, "title": row.title, "message": row.message, "severity": row.severity, "metadata": _loads(row.metadata_json, {}), "created_at": row.created_at.isoformat()}

    def _recovery_session_dict(self, row: RecoverySession) -> dict:
        return {"id": row.id, "session_type": row.session_type, "status": row.status, "started_at": row.started_at.isoformat(), "ended_at": _iso(row.ended_at), "workspace_state": _loads(row.workspace_state_json, {}), "restore_plan": _loads(row.restore_plan_json, []), "restored_items": _loads(row.restored_items_json, []), "metadata": _loads(row.metadata_json, {})}

    def _incident_report_dict(self, row: IncidentReport) -> dict:
        return {"id": row.id, "incident_type": row.incident_type, "title": row.title, "summary": row.summary, "applications_affected": _loads(row.applications_affected_json, []), "recovery_actions": _loads(row.recovery_actions_json, []), "recovered_items": _loads(row.recovered_items_json, []), "errors": _loads(row.errors_json, []), "recommendations": _loads(row.recommendations_json, []), "status": row.status, "created_at": row.created_at.isoformat(), "resolved_at": _iso(row.resolved_at)}

    def _recovered_application_dict(self, row: RecoveredApplication) -> dict:
        return {"id": row.id, "session_id": row.session_id, "app_name": row.app_name, "process_name": row.process_name, "workspace_path": row.workspace_path, "open_files": _loads(row.open_files_json, []), "terminal_state": _loads(row.terminal_state_json, {}), "restore_command": row.restore_command, "status": row.status, "metadata": _loads(row.metadata_json, {}), "created_at": row.created_at.isoformat()}

    def _recovery_history_dict(self, row: RecoveryHistory) -> dict:
        return {"id": row.id, "event_type": row.event_type, "title": row.title, "message": row.message, "status": row.status, "metadata": _loads(row.metadata_json, {}), "created_at": row.created_at.isoformat()}

    def _project_backup_dict(self, row: ProjectBackup) -> dict:
        return {"id": row.id, "project_path": row.project_path, "action": row.action, "backup_path": row.backup_path, "status": row.status, "detail": _loads(row.detail_json, {}), "created_at": row.created_at.isoformat()}

    def _download_dict(self, row: DownloadHistory) -> dict:
        return {"id": row.id, "file_path": row.file_path, "file_name": row.file_name, "category": row.category, "size_bytes": row.size_bytes, "size_label": self._format_bytes(row.size_bytes), "duplicate_of": row.duplicate_of, "recommendation": row.recommendation, "status": row.status, "created_at": row.created_at.isoformat()}

    def _download_rule_dict(self, row: DownloadRule) -> dict:
        return {"id": row.id, "name": row.name, "match_type": row.match_type, "pattern": row.pattern, "category": row.category, "destination": row.destination, "enabled": row.enabled, "priority": row.priority, "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat()}

    def _duplicate_file_dict(self, row: DuplicateFile) -> dict:
        return {"id": row.id, "file_path": row.file_path, "file_name": Path(row.file_path).name, "duplicate_of": row.duplicate_of, "duplicate_type": row.duplicate_type, "digest": row.digest, "size_bytes": row.size_bytes, "size_label": self._format_bytes(row.size_bytes), "status": row.status, "recommendation": row.recommendation, "created_at": row.created_at.isoformat()}

    def _cleanup_suggestion_dict(self, row: CleanupSuggestion) -> dict:
        return {"id": row.id, "file_path": row.file_path, "file_name": Path(row.file_path).name, "suggestion_type": row.suggestion_type, "title": row.title, "message": row.message, "size_bytes": row.size_bytes, "size_label": self._format_bytes(row.size_bytes), "severity": row.severity, "status": row.status, "metadata": _loads(row.metadata_json, {}), "created_at": row.created_at.isoformat()}

    def _storage_report_dict(self, row: StorageReport) -> dict:
        return {"id": row.id, "root_path": row.root_path, "total_files": row.total_files, "total_size_bytes": row.total_size_bytes, "total_size_label": self._format_bytes(row.total_size_bytes), "category_breakdown": _loads(row.category_breakdown_json, {}), "large_files": _loads(row.large_files_json, []), "duplicate_count": row.duplicate_count, "cleanup_recommendations": _loads(row.cleanup_recommendations_json, []), "created_at": row.created_at.isoformat()}

    def _screenshot_dict(self, row: ScreenshotHistory) -> dict:
        return {"id": row.id, "file_path": row.file_path, "source": row.source, "extracted_text": row.extracted_text, "analysis": row.analysis, "tags": _loads(row.tags_json, []), "created_at": row.created_at.isoformat()}

    def _screenshot_detail(self, db: Session, row: ScreenshotHistory) -> dict:
        payload = self._screenshot_dict(row)
        ocr = db.query(OCRResult).filter(OCRResult.screenshot_id == row.id).order_by(OCRResult.created_at.desc()).first()
        error = db.query(ErrorAnalysis).filter(ErrorAnalysis.screenshot_id == row.id).order_by(ErrorAnalysis.created_at.desc()).first()
        summary = db.query(DocumentSummary).filter(DocumentSummary.screenshot_id == row.id).order_by(DocumentSummary.created_at.desc()).first()
        extracted = db.query(ExtractedText).filter(ExtractedText.screenshot_id == row.id).order_by(ExtractedText.created_at.desc()).limit(10).all()
        actions = db.query(ScreenshotAction).filter(ScreenshotAction.screenshot_id == row.id).order_by(ScreenshotAction.created_at.desc()).limit(20).all()
        payload.update({
            "ocr": self._ocr_result_dict(ocr) if ocr else None,
            "error_analysis": self._error_analysis_dict(error) if error else None,
            "document_summary": self._document_summary_dict(summary) if summary else None,
            "extracted": [self._extracted_text_dict(item) for item in extracted],
            "actions": [self._screenshot_action_dict(item) for item in actions],
        })
        return payload

    def _ocr_result_dict(self, row: OCRResult) -> dict:
        return {"id": row.id, "screenshot_id": row.screenshot_id, "engine": row.engine, "language": row.language, "extracted_text": row.extracted_text, "confidence": row.confidence, "entities": _loads(row.entities_json, {}), "status": row.status, "created_at": row.created_at.isoformat()}

    def _error_analysis_dict(self, row: ErrorAnalysis) -> dict:
        return {"id": row.id, "screenshot_id": row.screenshot_id, "error_type": row.error_type, "language": row.language, "framework": row.framework, "probable_cause": row.probable_cause, "suggested_fixes": _loads(row.suggested_fixes_json, []), "severity": row.severity, "created_at": row.created_at.isoformat()}

    def _document_summary_dict(self, row: DocumentSummary) -> dict:
        return {"id": row.id, "screenshot_id": row.screenshot_id, "document_type": row.document_type, "summary": row.summary, "key_points": _loads(row.key_points_json, []), "study_notes": _loads(row.study_notes_json, []), "created_at": row.created_at.isoformat()}

    def _extracted_text_dict(self, row: ExtractedText) -> dict:
        return {"id": row.id, "screenshot_id": row.screenshot_id, "text_type": row.text_type, "value": row.value, "metadata": _loads(row.metadata_json, {}), "created_at": row.created_at.isoformat()}

    def _screenshot_action_dict(self, row: ScreenshotAction) -> dict:
        return {"id": row.id, "screenshot_id": row.screenshot_id, "action_type": row.action_type, "status": row.status, "detail": _loads(row.detail_json, {}), "created_at": row.created_at.isoformat()}

    def _goal_progress_percent(self, row: Goal) -> float:
        return 100 if row.target_value <= 0 else round(min(100, max(0, row.current_value) / row.target_value * 100), 2)

    def _goal_dict(self, row: Goal) -> dict:
        progress = self._goal_progress_percent(row)
        remaining = round(max(0, row.target_value - row.current_value), 2)
        return {
            "id": row.id,
            "title": row.title,
            "description": getattr(row, "description", ""),
            "goal_type": row.goal_type,
            "category": getattr(row, "category", row.goal_type),
            "priority": getattr(row, "priority", "medium"),
            "target_value": row.target_value,
            "current_value": row.current_value,
            "remaining_value": remaining,
            "unit": row.unit,
            "period": row.period,
            "deadline": getattr(row, "deadline", ""),
            "reminder_settings": _loads(getattr(row, "reminder_settings_json", "{}"), {}),
            "status": row.status,
            "progress_percent": progress,
            "estimated_completion": self._goal_forecast(row),
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
        }

    def _goal_detail_dict(self, db: Session, row: Goal) -> dict:
        payload = self._goal_dict(row)
        progress = db.query(GoalProgress).filter(GoalProgress.goal_id == row.id).order_by(GoalProgress.created_at.desc()).limit(10).all()
        streak = db.query(Streak).filter(Streak.goal_id == row.id).order_by(Streak.updated_at.desc()).first()
        payload.update({
            "progress_history": [self._goal_progress_dict(item) for item in progress],
            "streak": self._streak_dict(streak) if streak else None,
        })
        return payload

    def _goal_forecast(self, row: Goal) -> dict:
        remaining = max(0, float(row.target_value or 0) - float(row.current_value or 0))
        daily_rate = max(float(row.current_value or 0), 0.01) if row.period == "daily" else max(float(row.current_value or 0) / 7, 0.01)
        days = 0 if remaining <= 0 else round(remaining / daily_rate, 1)
        return {"remaining_value": round(remaining, 2), "estimated_completion_days": days}

    def _record_goal_event(self, db: Session, row: Goal, event_type: str, title: str, message: str, metadata: dict | None = None) -> None:
        db.add(GoalHistory(goal_id=row.id, event_type=event_type, title=title, message=message, status=row.status, metadata_json=json.dumps(metadata or {}, default=str)))

    def _record_goal_analytics(self, db: Session, row: Goal, source: str = "manual") -> None:
        progress = self._goal_progress_percent(row)
        today = date.today().isoformat()
        completion_rate = round(float(row.current_value or 0) / max(float(row.target_value or 1), 1) * 100, 2)
        db.add(GoalAnalytics(goal_id=row.id, analytics_date=today, progress_value=row.current_value, progress_percent=progress, completion_rate=completion_rate, estimated_completion_days=self._goal_forecast(row)["estimated_completion_days"], metadata_json=json.dumps({"source": source, "goal_type": row.goal_type}, default=str)))

    def _update_goal_streak(self, db: Session, row: Goal) -> None:
        today = date.today()
        today_key = today.isoformat()
        streak = db.query(Streak).filter(Streak.goal_id == row.id, Streak.streak_type == row.period).one_or_none()
        if not streak:
            streak = Streak(goal_id=row.id, streak_type=row.period, current_count=1, best_count=1, last_activity_date=today_key, metadata_json=json.dumps({"goal_type": row.goal_type}, default=str))
            db.add(streak)
            return
        if streak.last_activity_date == today_key:
            streak.current_count = max(1, streak.current_count)
        else:
            try:
                previous = datetime.fromisoformat(streak.last_activity_date).date()
            except ValueError:
                previous = today - timedelta(days=10)
            streak.current_count = streak.current_count + 1 if (today - previous).days == 1 else 1
            streak.last_activity_date = today_key
        streak.best_count = max(streak.best_count, streak.current_count)
        streak.updated_at = datetime.utcnow()
        if streak.current_count in {7, 30, 100}:
            self._unlock_achievement(db, f"{streak.current_count} Day {row.goal_type.title()} Streak", "Streak", f"{row.title} has a {streak.current_count} day streak.", {"goal_id": row.id, "streak": streak.current_count})

    def _goal_progress_since(self, db: Session, days: int) -> list[dict]:
        start = datetime.utcnow() - timedelta(days=days)
        rows = db.query(GoalProgress).filter(GoalProgress.created_at >= start).order_by(GoalProgress.created_at.desc()).limit(100).all()
        return [self._goal_progress_dict(row) for row in rows]

    def _average_goal_completion_days(self, db: Session) -> float:
        completed = db.query(Goal).filter(Goal.status == "achieved").all()
        if not completed:
            return 0
        days = [max(0, (row.updated_at - row.created_at).total_seconds() / 86400) for row in completed]
        return round(sum(days) / len(days), 2)

    def _goal_progress_dict(self, row: GoalProgress) -> dict:
        return {"id": row.id, "goal_id": row.goal_id, "delta_value": row.delta_value, "current_value": row.current_value, "progress_percent": row.progress_percent, "source": row.source, "note": row.note, "metadata": _loads(row.metadata_json, {}), "created_at": row.created_at.isoformat()}

    def _goal_history_dict(self, row: GoalHistory) -> dict:
        return {"id": row.id, "goal_id": row.goal_id, "event_type": row.event_type, "title": row.title, "message": row.message, "status": row.status, "metadata": _loads(row.metadata_json, {}), "created_at": row.created_at.isoformat()}

    def _streak_dict(self, row: Streak) -> dict:
        return {"id": row.id, "goal_id": row.goal_id, "streak_type": row.streak_type, "current_count": row.current_count, "best_count": row.best_count, "last_activity_date": row.last_activity_date, "status": row.status, "metadata": _loads(row.metadata_json, {}), "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat()}

    def _goal_analytics_dict(self, row: GoalAnalytics) -> dict:
        return {"id": row.id, "goal_id": row.goal_id, "analytics_date": row.analytics_date, "progress_value": row.progress_value, "progress_percent": row.progress_percent, "completion_rate": row.completion_rate, "estimated_completion_days": row.estimated_completion_days, "metadata": _loads(row.metadata_json, {}), "created_at": row.created_at.isoformat()}

    def _goal_reminder_dict(self, row: GoalReminder) -> dict:
        return {"id": row.id, "goal_id": row.goal_id, "reminder_type": row.reminder_type, "message": row.message, "due_at": _iso(row.due_at), "status": row.status, "metadata": _loads(row.metadata_json, {}), "created_at": row.created_at.isoformat(), "sent_at": _iso(row.sent_at)}

    def _achievement_dict(self, row: Achievement) -> dict:
        return {"id": row.id, "title": row.title, "badge": row.badge, "description": row.description, "progress_percent": row.progress_percent, "unlocked": row.unlocked, "unlocked_at": _iso(row.unlocked_at), "metadata": _loads(row.metadata_json, {}), "created_at": row.created_at.isoformat()}

    def _suggestion_dict(self, row: CopilotSuggestion) -> dict:
        return {"id": row.id, "suggestion_type": row.suggestion_type, "title": row.title, "message": row.message, "severity": row.severity, "module": row.module, "action": _loads(row.action_json, {}), "status": row.status, "created_at": row.created_at.isoformat(), "acted_at": _iso(row.acted_at)}

    def _context_snapshot_dict(self, row: ContextSnapshot) -> dict:
        return {"id": row.id, "current_app": row.current_app, "current_window": row.current_window, "activity_type": row.activity_type, "priority_context": row.priority_context, "payload": _loads(row.payload_json, {}), "privacy_mode": row.privacy_mode, "created_at": row.created_at.isoformat()}

    def _copilot_insight_dict(self, row: CopilotInsight) -> dict:
        return {"id": row.id, "insight_type": row.insight_type, "title": row.title, "message": row.message, "period": row.period, "severity": row.severity, "recommendation": row.recommendation, "metadata": _loads(row.metadata_json, {}), "created_at": row.created_at.isoformat()}

    def _copilot_warning_dict(self, row: CopilotWarning) -> dict:
        return {"id": row.id, "warning_type": row.warning_type, "module": row.module, "title": row.title, "message": row.message, "severity": row.severity, "status": row.status, "metadata": _loads(row.metadata_json, {}), "created_at": row.created_at.isoformat(), "resolved_at": _iso(row.resolved_at)}

    def _copilot_action_dict(self, row: CopilotAction) -> dict:
        return {"id": row.id, "suggestion_id": row.suggestion_id, "action_type": row.action_type, "title": row.title, "payload": _loads(row.payload_json, {}), "status": row.status, "result": _loads(row.result_json, {}), "created_at": row.created_at.isoformat(), "executed_at": _iso(row.executed_at)}

    def _copilot_history_dict(self, row: CopilotHistory) -> dict:
        return {"id": row.id, "event_type": row.event_type, "suggestion_id": row.suggestion_id, "title": row.title, "detail": _loads(row.detail_json, {}), "status": row.status, "created_at": row.created_at.isoformat()}

    def _copilot_analytics_dict(self, row: CopilotAnalytics) -> dict:
        return {"id": row.id, "analytics_date": row.analytics_date, "suggestions_generated": row.suggestions_generated, "suggestions_acted": row.suggestions_acted, "warnings_open": row.warnings_open, "critical_count": row.critical_count, "helpful_score": row.helpful_score, "metadata": _loads(row.metadata_json, {}), "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat()}

    def _college_dict(self, row: CollegeUpdate) -> dict:
        return {"id": row.id, "source": row.source, "update_type": row.update_type, "title": row.title, "message": row.message, "url": row.url, "status": row.status, "payload": _loads(row.payload_json, {}), "created_at": row.created_at.isoformat()}

    def _college_profile_dict(self, row: CollegeProfile) -> dict:
        return {"id": row.id, "name": row.name, "portal_type": row.portal_type, "website_profile_id": row.website_profile_id, "target_attendance_percent": row.target_attendance_percent, "status": row.status, "auto_login_ready": bool(row.website_profile_id), "session_restore_ready": bool(row.session_state_encrypted), "last_checked_at": _iso(row.last_checked_at), "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat()}

    def _attendance_dict(self, row: AttendanceRecord) -> dict:
        return {"id": row.id, "profile_id": row.profile_id, "source": row.source, "subject": row.subject, "attended_classes": row.attended_classes, "total_classes": row.total_classes, "percentage": row.percentage, "target_percentage": row.target_percentage, "trend": row.trend, "status": row.status, "recorded_at": row.recorded_at.isoformat()}

    def _internal_mark_dict(self, row: InternalMark) -> dict:
        percent = round(row.marks_obtained / row.max_marks * 100, 2) if row.max_marks else 0
        return {"id": row.id, "profile_id": row.profile_id, "source": row.source, "subject": row.subject, "component": row.component, "marks_obtained": row.marks_obtained, "max_marks": row.max_marks, "percentage": percent, "status": row.status, "recorded_at": row.recorded_at.isoformat()}

    def _result_record_dict(self, row: ResultRecord) -> dict:
        return {"id": row.id, "profile_id": row.profile_id, "source": row.source, "exam_name": row.exam_name, "result_type": row.result_type, "summary": row.summary, "score": row.score, "rank": row.rank, "payload": _loads(row.payload_json, {}), "status": row.status, "recorded_at": row.recorded_at.isoformat()}

    def _assignment_record_dict(self, row: AssignmentRecord) -> dict:
        return {"id": row.id, "profile_id": row.profile_id, "source": row.source, "title": row.title, "subject": row.subject, "due_at": _iso(row.due_at), "status": row.status, "detail": _loads(row.detail_json, {}), "created_at": row.created_at.isoformat()}

    def _fee_record_dict(self, row: FeeRecord) -> dict:
        return {"id": row.id, "profile_id": row.profile_id, "source": row.source, "fee_type": row.fee_type, "amount": row.amount, "currency": row.currency, "due_at": _iso(row.due_at), "receipt_path": row.receipt_path, "status": row.status, "recorded_at": row.recorded_at.isoformat()}

    def _timetable_record_dict(self, row: TimetableRecord) -> dict:
        return {"id": row.id, "profile_id": row.profile_id, "source": row.source, "schedule_type": row.schedule_type, "title": row.title, "starts_at": _iso(row.starts_at), "ends_at": _iso(row.ends_at), "location": row.location, "payload": _loads(row.payload_json, {}), "created_at": row.created_at.isoformat()}

    def _announcement_record_dict(self, row: AnnouncementRecord) -> dict:
        return {"id": row.id, "profile_id": row.profile_id, "source": row.source, "announcement_type": row.announcement_type, "title": row.title, "message": row.message, "url": row.url, "status": row.status, "created_at": row.created_at.isoformat()}

    def _kcet_record_dict(self, row: KCETRecord) -> dict:
        return {"id": row.id, "profile_id": row.profile_id, "event_type": row.event_type, "title": row.title, "rank": row.rank, "score": row.score, "screenshot_path": row.screenshot_path, "pdf_path": row.pdf_path, "payload": _loads(row.payload_json, {}), "status": row.status, "created_at": row.created_at.isoformat()}


evolution_service = EvolutionService()
