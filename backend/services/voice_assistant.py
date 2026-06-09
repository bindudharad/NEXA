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
from backend.database.models import Automation, CustomPersonality, Notification, Task, TimelineEvent, VoiceAnalytics, VoiceHistory, VoiceInteraction, VoiceProfile, VoiceSetting, WakeWordHistory
from backend.database.session import SessionLocal
from backend.services.power_monitor import power_monitor_service

logger = logging.getLogger("nexa.voice")


@dataclass
class VoiceAssistantSettings:
    enabled: bool = True
    wake_word_enabled: bool = True
    wake_phrases: list[str] = field(default_factory=lambda: ["nexa", "hey nexa", "hello nexa", "nexa activate", "nexa wake up"])
    activation_response: str = "Yes?"
    response_style: str = "professional"
    custom_personality_id: int | None = None
    custom_wake_responses: list[str] = field(default_factory=list)
    custom_completion_responses: list[str] = field(default_factory=list)
    custom_reminder_responses: list[str] = field(default_factory=list)
    custom_error_responses: list[str] = field(default_factory=list)
    custom_notification_responses: dict = field(default_factory=dict)
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
    voice_pitch: int = 0
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
    wake_responses = {"Yes?", "I'm listening.", "How can I help?", "Ready.", "What would you like me to do?", "Nexa activated.", "Yes, how may I assist you?", "Hey! How can I help?", "At your service.", "You summoned me?"}
    built_in_profiles = {
        "professional": {
            "name": "Professional",
            "description": "Formal, clear, and work-focused.",
            "wake": ["Yes, how may I assist you?", "How may I assist you?"],
            "completion": ["Task completed successfully.", "The task has been completed."],
            "reminder": ["You have a scheduled reminder.", "A reminder is due."],
            "error": ["I could not complete that request.", "An error occurred while processing the request."],
            "notifications": {"battery_low": "Battery level is low. Please connect your charger.", "automation": "Automation executed successfully.", "website": "The monitored website is now available."},
        },
        "friendly": {
            "name": "Friendly",
            "description": "Warm, helpful, and casual.",
            "wake": ["Hey! How can I help?", "I'm listening."],
            "completion": ["Done! You're all set.", "Your task is done."],
            "reminder": ["You have a reminder coming up.", "Quick reminder for you."],
            "error": ["I couldn't get that done yet.", "Something got in the way."],
            "notifications": {"battery_low": "Looks like your battery is getting low.", "automation": "Your automation is done.", "website": "That website is available now."},
        },
        "jarvis": {
            "name": "Jarvis",
            "description": "Elegant, efficient assistant style.",
            "wake": ["At your service.", "Ready when you are."],
            "completion": ["The requested operation has been completed.", "The requested task has been completed."],
            "reminder": ["A reminder has been scheduled.", "Your reminder is now due."],
            "error": ["I was unable to complete the operation.", "The operation could not be completed."],
            "notifications": {"battery_low": "Power reserves are low.", "automation": "Automation sequence completed.", "website": "The monitored site is available."},
        },
        "minimal": {
            "name": "Minimal",
            "description": "Short, fast, and direct.",
            "wake": ["Yes?", "Ready."],
            "completion": ["Done.", "Completed."],
            "reminder": ["Reminder.", "Due now."],
            "error": ["Failed.", "Error."],
            "notifications": {"battery_low": "Battery low.", "automation": "Automation done.", "website": "Website available."},
        },
        "funny": {
            "name": "Funny",
            "description": "Lighthearted without being noisy.",
            "wake": ["You summoned me?", "Ready for another mission?"],
            "completion": ["Mission accomplished.", "Achievement unlocked: task completed."],
            "reminder": ["Your reminder has entered the chat.", "Tiny nudge: you have something due."],
            "error": ["That did not go as planned.", "I hit a tiny wall there."],
            "notifications": {"battery_low": "Your laptop is asking for food.", "automation": "Mission accomplished.", "website": "The website gates are open."},
        },
        "silent": {
            "name": "Silent",
            "description": "No spoken responses, visual feedback only.",
            "wake": [""],
            "completion": [""],
            "reminder": [""],
            "error": [""],
            "notifications": {},
        },
    }

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
            self.ensure_profiles(db)
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
        if updates.get("response_style") and "activation_response" not in updates:
            style = "minimal" if updates["response_style"] == "concise" else updates["response_style"]
            if style == "silent":
                current["activation_response"] = ""
            elif style in self.built_in_profiles:
                current["activation_response"] = self.built_in_profiles[style]["wake"][0]
        settings = VoiceAssistantSettings(**current)
        self._validate(settings)
        previous = self.get_settings(db).response_style
        owns_db = db is None
        db = db or self.db_factory()
        try:
            self.ensure_profiles(db)
            value = json.dumps(asdict(settings), default=str)
            row = db.query(VoiceSetting).filter(VoiceSetting.key == self.settings_key).one_or_none()
            if row:
                row.value_json = value
                row.updated_at = datetime.utcnow()
            else:
                db.add(VoiceSetting(key=self.settings_key, value_json=value))
            if previous != settings.response_style:
                db.add(VoiceHistory(event_type="personality_changed", personality=settings.response_style, input_text=previous, response_text=f"Voice personality changed to {settings.response_style}.", context_json=json.dumps({"from": previous, "to": settings.response_style})))
                db.add(TimelineEvent(event_type="voice", title="Voice personality changed", description=f"Nexa voice personality changed from {previous} to {settings.response_style}.", source="voice_assistant", metadata_json=json.dumps({"from": previous, "to": settings.response_style, "important": True})))
                NotificationAgent(db).notify(
                    "Nexa Voice Personality",
                    f"Voice personality changed to {settings.response_style}.",
                    alert_type="voice_personality",
                    module="voice_assistant",
                    severity="low",
                    priority="low",
                    category="info",
                    suggested_action="Test the wake response or adjust voice settings.",
                    action_buttons=["Test Voice", "Dismiss"],
                    metadata={"from": previous, "to": settings.response_style},
                )
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
        response = "" if settings.response_style == "silent" else self.personality_response("wake", settings.activation_response or "Yes?", {"phrase": phrase}) if settings.response_style == "custom" else settings.activation_response or self.personality_response("wake", "Yes?", {"phrase": phrase})
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
        if self._should_speak(settings, response):
            self.speak(response)
        self._record("wake_detected", phrase, response, self._mode(settings), "completed", {"source": source})
        with self.db_factory() as db:
            db.add(WakeWordHistory(phrase=phrase, source=source, personality=settings.response_style, response_text=response, status="detected"))
            self._analytics(db, settings.response_style, wake=1, spoken=1 if response and settings.voice_enabled else 0)
            db.commit()
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
            response = self.personality_response(self._response_context(result), result["response"], {"command": command, "result": result})
            status = "completed"
        except Exception as exc:
            response = self.personality_response("error", f"I could not complete that locally: {exc}", {"command": command, "error": str(exc)})
            result = {"handled": False, "error": str(exc)}
            status = "failed"
            logger.exception("Voice command failed command=%s", command)
        if self._should_speak(settings, response):
            self.speak(response)
        with self._lock:
            self.status.microphone_status = "speaking" if self._should_speak(settings, response) else "listening"
            self.status.last_response = response
            self.status.last_error = result.get("error")
        if self._should_speak(settings, response):
            threading.Timer(2.5, self._return_to_listening).start()
        self._record("voice_command", command, response, mode, status, {"source": source, "result": result})
        with self.db_factory() as db:
            self._analytics(db, settings.response_style, commands=1, spoken=1 if self._should_speak(settings, response) else 0, errors=1 if status == "failed" else 0)
            db.commit()
        return {"command": command, "response": response, "mode": mode, "status": status, "result": result}

    def speak(self, text: str) -> None:
        settings = self.get_settings()
        if not self._should_speak(settings, text):
            return
        text = self.personality_response("notification", text, {})
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.Volume = {settings.voice_volume}; $s.Rate = {settings.voice_speed}; "
            f"$s.Speak({json.dumps(text)});"
        )
        try:
            subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False)
            logger.info("Voice response spoken text=%s", text)
            with self.db_factory() as db:
                self._analytics(db, settings.response_style, spoken=1)
                db.commit()
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

    def ensure_profiles(self, db: Session | None = None) -> None:
        owns_db = db is None
        db = db or self.db_factory()
        try:
            existing = {row.profile_key for row in db.query(VoiceProfile).all()}
            for key, profile in self.built_in_profiles.items():
                if key in existing:
                    continue
                db.add(
                    VoiceProfile(
                        profile_key=key,
                        name=profile["name"],
                        style=key,
                        description=profile["description"],
                        wake_responses_json=json.dumps(profile["wake"]),
                        completion_responses_json=json.dumps(profile["completion"]),
                        reminder_responses_json=json.dumps(profile["reminder"]),
                        error_responses_json=json.dumps(profile["error"]),
                        notification_responses_json=json.dumps(profile["notifications"]),
                        tts_settings_json=json.dumps({"language": "en-US", "volume": 85, "speed": 0, "pitch": 0}),
                        built_in=True,
                    )
                )
            db.commit()
        finally:
            if owns_db:
                db.close()

    def profiles(self) -> list[dict]:
        with self.db_factory() as db:
            self.ensure_profiles(db)
            return [self._profile_dict(row) for row in db.query(VoiceProfile).order_by(VoiceProfile.built_in.desc(), VoiceProfile.name.asc()).all()]

    def create_custom_personality(self, payload: dict) -> dict:
        with self.db_factory() as db:
            row = CustomPersonality(
                name=payload.get("name", "Custom Personality"),
                greeting_style=payload.get("greeting_style", ""),
                wake_responses_json=json.dumps(payload.get("wake_responses") or ["I'm listening."]),
                completion_responses_json=json.dumps(payload.get("completion_responses") or ["Done."]),
                reminder_responses_json=json.dumps(payload.get("reminder_responses") or ["You have a reminder."]),
                error_responses_json=json.dumps(payload.get("error_responses") or ["I could not complete that."]),
                notification_responses_json=json.dumps(payload.get("notification_responses") or {}),
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._custom_personality_dict(row)

    def update_custom_personality(self, personality_id: int, payload: dict) -> dict:
        with self.db_factory() as db:
            row = db.get(CustomPersonality, personality_id)
            if not row:
                raise ValueError("Custom personality not found")
            for key, attr in {
                "name": "name",
                "greeting_style": "greeting_style",
                "wake_responses": "wake_responses_json",
                "completion_responses": "completion_responses_json",
                "reminder_responses": "reminder_responses_json",
                "error_responses": "error_responses_json",
                "notification_responses": "notification_responses_json",
            }.items():
                if key not in payload:
                    continue
                value = payload[key] if key in {"name", "greeting_style"} else json.dumps(payload[key], default=str)
                setattr(row, attr, value)
            if "enabled" in payload:
                row.enabled = bool(payload["enabled"])
            row.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(row)
            return self._custom_personality_dict(row)

    def delete_custom_personality(self, personality_id: int) -> dict:
        with self.db_factory() as db:
            row = db.get(CustomPersonality, personality_id)
            if not row:
                raise ValueError("Custom personality not found")
            row.enabled = False
            row.updated_at = datetime.utcnow()
            db.commit()
            return {"id": personality_id, "deleted": True}

    def dashboard(self) -> dict:
        settings = self.get_settings()
        with self.db_factory() as db:
            self.ensure_profiles(db)
            history = [self._voice_history_dict(row) for row in db.query(VoiceHistory).order_by(VoiceHistory.created_at.desc()).limit(50).all()]
            wake = [self._wake_history_dict(row) for row in db.query(WakeWordHistory).order_by(WakeWordHistory.created_at.desc()).limit(50).all()]
            analytics = [self._voice_analytics_dict(row) for row in db.query(VoiceAnalytics).order_by(VoiceAnalytics.created_at.desc()).limit(30).all()]
            custom = [self._custom_personality_dict(row) for row in db.query(CustomPersonality).order_by(CustomPersonality.updated_at.desc()).all()]
            return {
                "current_personality": settings.response_style,
                "voice_status": self.get_status(),
                "wake_word_status": {"enabled": settings.wake_word_enabled, "phrases": settings.wake_phrases, "privacy_mode": settings.privacy_mode},
                "voice_statistics": self._voice_statistics(analytics),
                "recent_responses": history,
                "wake_history": wake,
                "voice_history": history,
                "profiles": [self._profile_dict(row) for row in db.query(VoiceProfile).order_by(VoiceProfile.name.asc()).all()],
                "custom_personalities": custom,
                "offline_ready": True,
            }

    def personality_response(self, context: str, default: str, detail: dict | None = None) -> str:
        settings = self.get_settings()
        style = settings.response_style
        if style == "concise":
            style = "minimal"
        if style == "silent":
            return ""
        detail = detail or {}
        profile = self._active_profile(settings)
        if context == "wake":
            return self._first_response(profile.get("wake", []), default)
        if context in {"completion", "task_completed"}:
            return self._first_response(profile.get("completion", []), default)
        if context == "reminder":
            return self._first_response(profile.get("reminder", []), default)
        if context == "error":
            return self._first_response(profile.get("error", []), default)
        if context in {"battery_low", "automation", "website", "notification"}:
            mapped = profile.get("notifications", {}).get(context) or profile.get("notifications", {}).get(self._notification_context(default))
            return mapped or default
        if context == "daily_briefing":
            if style == "minimal":
                return default.replace("Good morning. ", "").split(" Have a productive day.")[0]
            if style == "friendly":
                return default.replace("Good morning.", "Good morning!").replace("Have a productive day.", "Have a good one.")
            if style == "jarvis":
                return default.replace("Good morning.", "Good morning. Your briefing is ready.")
            if style == "funny":
                return default.replace("Good morning.", "Good morning. Daily mission briefing loaded.")
        if context == "battery_status":
            return self._battery_personality_response(default, style)
        return default

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
        if "create automation" in lower:
            from backend.services.evolution import evolution_service

            with self.db_factory() as db:
                prompt = command.split("automation", 1)[-1].strip() or command
                result = evolution_service.build_automation(db, prompt)
            return {"handled": True, "response": f"Automation created: {result['automation']['name']}.", "action": "automation_create", "result": result}
        if "battery" in lower or "charging" in lower:
            status = power_monitor_service.get_status()
            percent = status.get("battery_percent")
            charging = status.get("is_charging")
            response = f"Battery is currently {percent if percent is not None else 'unknown'} percent"
            response += " and charging." if charging else " and running on battery power." if charging is False else "."
            return {"handled": True, "response": response, "action": "battery_status", "status": status}
        if "nexa health" in lower or "show errors" in lower or "optimize nexa" in lower or "show api status" in lower or "restart service" in lower or "nexa cpu" in lower or "nexa ram" in lower:
            from backend.services.evolution import evolution_service

            with self.db_factory() as db:
                if "optimize nexa" in lower:
                    result = evolution_service.optimize_self_health(db, "optimize")
                    return {"handled": True, "response": "Nexa optimization completed.", "action": "self_health_optimize", "result": result}
                if "restart service" in lower:
                    result = evolution_service.optimize_self_health(db, "restart_services")
                    return {"handled": True, "response": "Nexa service health has been refreshed.", "action": "self_health_restart_services", "result": result}
                dashboard = evolution_service.self_health(db)
                if "show errors" in lower:
                    return {"handled": True, "response": f"Nexa has {dashboard['error_monitor']['count']} recent error log entries.", "action": "self_health_errors", "dashboard": dashboard}
                if "show api status" in lower:
                    return {"handled": True, "response": f"API health is {dashboard['api_health']['summary']['status']} with {dashboard['api_health']['summary']['success_rate']} percent success.", "action": "self_health_api", "dashboard": dashboard}
                if "nexa cpu" in lower:
                    return {"handled": True, "response": f"Nexa CPU usage is {dashboard['cpu']['current_percent']} percent.", "action": "self_health_cpu", "dashboard": dashboard}
                if "nexa ram" in lower:
                    return {"handled": True, "response": f"Nexa RAM usage is {dashboard['ram']['current_mb']} megabytes.", "action": "self_health_ram", "dashboard": dashboard}
                return {"handled": True, "response": f"Nexa health is {dashboard['health_score']} percent and status is {dashboard['status']}.", "action": "self_health_dashboard", "dashboard": dashboard}
        if "system health" in lower or "cpu" in lower or "memory" in lower:
            status = system.status()
            return {"handled": True, "response": f"CPU is {status['cpu_percent']} percent and memory is {status['ram_percent']} percent.", "action": "system_health", "status": status}
        if "show notifications" in lower or "view notifications" in lower:
            with self.db_factory() as db:
                count = db.query(Notification).filter(Notification.read.is_(False)).count()
            return {"handled": True, "response": f"You have {count} unread notifications.", "action": "notifications"}
        if "create goal" in lower or "show goals" in lower or "show progress" in lower or "mark goal complete" in lower or "show streaks" in lower or "show achievements" in lower:
            from backend.services.evolution import evolution_service

            with self.db_factory() as db:
                if "create goal" in lower:
                    title = command.split("goal", 1)[-1].strip(" .") or "New Goal"
                    target = self._extract_number(lower, 1)
                    unit = "hours" if "hour" in lower else "minutes" if "minute" in lower else "pages" if "page" in lower else "count"
                    goal_type = "coding" if "code" in lower or "coding" in lower else "study" if "study" in lower else "reading" if "read" in lower else "custom"
                    goal = evolution_service.create_goal(db, title, target, unit, goal_type, "daily")
                    return {"handled": True, "response": f"Goal created: {goal['title']}.", "action": "goal_create", "goal": goal}
                dashboard = evolution_service.goal_dashboard(db)
                if "mark goal complete" in lower:
                    active = dashboard["active_goals"][0] if dashboard["active_goals"] else None
                    if not active:
                        return {"handled": True, "response": "No active goals are available to complete.", "action": "goal_complete_empty"}
                    goal = evolution_service.update_goal(db, active["id"], active["target_value"], "voice", "Marked complete by voice command")
                    return {"handled": True, "response": f"Goal completed: {goal['title']}.", "action": "goal_complete", "goal": goal}
                if "show streaks" in lower:
                    return {"handled": True, "response": f"You have {len(dashboard['streaks'])} active goal streak(s).", "action": "goal_streaks", "dashboard": dashboard}
                if "show achievements" in lower:
                    return {"handled": True, "response": f"You have {len(dashboard['achievements'])} achievement(s).", "action": "goal_achievements", "dashboard": dashboard}
                active_count = len(dashboard["active_goals"])
                average = dashboard["statistics"].get("average_progress_percent", 0)
                return {"handled": True, "response": f"You have {active_count} active goals with {average} percent average progress.", "action": "goal_dashboard", "dashboard": dashboard}
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
        if "recovery dashboard" in lower or "show recovery" in lower or "crash reports" in lower or "restore session" in lower or "recover vscode" in lower or "recover cursor" in lower or "terminal recovery" in lower or "power loss recovery" in lower:
            from backend.services.evolution import evolution_service

            with self.db_factory() as db:
                dashboard = evolution_service.recovery_dashboard(db)
                if "restore session" in lower:
                    latest = dashboard["recovery_sessions"][0] if dashboard["recovery_sessions"] else None
                    if latest:
                        restored = evolution_service.restore_recovery_session(db, latest["id"])
                        return {"handled": True, "response": "Latest recovery session has been marked restored. Review the restore plan before reopening sensitive work.", "action": "recovery_session_restore", "session": restored}
                    return {"handled": True, "response": "No recovery sessions are available.", "action": "recovery_session_restore", "session": None}
                if "crash reports" in lower:
                    return {"handled": True, "response": f"There are {dashboard['summary']['crash_reports']} crash reports, with {dashboard['summary']['open_reports']} still open.", "action": "recovery_crash_reports", "dashboard": dashboard}
                if "recover vscode" in lower or "recover cursor" in lower or "terminal recovery" in lower or "power loss recovery" in lower:
                    app = "VS Code" if "vscode" in lower else "Cursor" if "cursor" in lower else "Terminal" if "terminal" in lower else "Windows"
                    event = "power_loss" if "power loss" in lower else f"{app.lower().replace(' ', '_')}_recovery_request"
                    result = evolution_service.simulate_recovery_event(db, event, app)
                    return {"handled": True, "response": f"{app} recovery state captured. Open Emergency Recovery to review restore options.", "action": "recovery_capture", "result": result}
            return {"handled": True, "response": f"Emergency Recovery health is {round(dashboard['summary']['health_score'])} percent with {dashboard['summary']['recovery_sessions']} recovery sessions available.", "action": "recovery_dashboard", "dashboard": dashboard}
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
        if "create automation" in lower or "show automations" in lower or "pause automation" in lower or "resume automation" in lower or "automation history" in lower:
            from backend.automation import AutomationEngine
            from backend.services.evolution import evolution_service

            with self.db_factory() as db:
                engine = AutomationEngine(db)
                if "create automation" in lower:
                    prompt = command.split("automation", 1)[-1].strip() or command
                    result = evolution_service.build_automation(db, prompt)
                    return {"handled": True, "response": f"Automation created: {result['automation']['name']}.", "action": "automation_create", "result": result}
                if "pause automation" in lower or "resume automation" in lower:
                    items = engine.list()
                    if not items:
                        return {"handled": True, "response": "No automations are available.", "action": "automation_toggle", "automation": None}
                    row = db.get(Automation, items[0]["id"])
                    row.enabled = "resume automation" in lower
                    db.commit()
                    return {"handled": True, "response": f"Automation {row.name} {'resumed' if row.enabled else 'paused'}.", "action": "automation_toggle", "automation": engine.serialize(row)}
                if "automation history" in lower:
                    history = engine.history(20)
                    return {"handled": True, "response": f"You have {len(history)} automation history item(s).", "action": "automation_history", "history": history}
                dashboard = engine.dashboard()
            return {"handled": True, "response": f"You have {len(dashboard['active'])} active and {len(dashboard['paused'])} paused automations.", "action": "automation_dashboard", "dashboard": dashboard}
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
        if "college updates" in lower or "check college" in lower or "check results" in lower or "show attendance" in lower or "show marks" in lower or "show timetable" in lower or "check fees" in lower or "show fees" in lower or "show assignments" in lower or "check kcet" in lower or "read announcements" in lower:
            from backend.services.evolution import evolution_service

            with self.db_factory() as db:
                if "show attendance" in lower:
                    dashboard = evolution_service.college_dashboard(db)
                    response = f"Overall attendance is {dashboard['summary'].split('Internal Marks:')[0].replace('Attendance:', '').strip()}"
                    return {"handled": True, "response": response, "action": "college_attendance", "dashboard": dashboard}
                if "show marks" in lower:
                    dashboard = evolution_service.college_dashboard(db)
                    return {"handled": True, "response": f"You have {len(dashboard['marks'])} internal marks record(s).", "action": "college_marks", "dashboard": dashboard}
                if "check results" in lower:
                    dashboard = evolution_service.college_dashboard(db)
                    return {"handled": True, "response": f"You have {len(dashboard['results'])} result record(s).", "action": "college_results", "dashboard": dashboard}
                if "show timetable" in lower:
                    dashboard = evolution_service.college_dashboard(db)
                    return {"handled": True, "response": f"You have {len(dashboard['timetables'])} timetable item(s).", "action": "college_timetable", "dashboard": dashboard}
                if "check fees" in lower or "show fees" in lower:
                    dashboard = evolution_service.college_dashboard(db)
                    pending = sum(1 for item in dashboard["fees"] if item["status"] == "pending")
                    return {"handled": True, "response": f"You have {pending} pending fee item(s).", "action": "college_fees", "dashboard": dashboard}
                if "show assignments" in lower:
                    dashboard = evolution_service.college_dashboard(db)
                    pending = sum(1 for item in dashboard["assignments"] if item["status"] != "completed")
                    return {"handled": True, "response": f"You have {pending} pending assignment(s).", "action": "college_assignments", "dashboard": dashboard}
                if "check kcet" in lower:
                    dashboard = evolution_service.college_dashboard(db)
                    return {"handled": True, "response": f"You have {len(dashboard['kcet'])} KCET update(s).", "action": "college_kcet", "dashboard": dashboard}
                if "read announcements" in lower:
                    dashboard = evolution_service.college_dashboard(db)
                    latest = dashboard["announcements"][0]["title"] if dashboard["announcements"] else "No announcements are cached."
                    return {"handled": True, "response": latest, "action": "college_announcements", "dashboard": dashboard}
                result = evolution_service.check_college_updates(db, "college")
            response = "College profile is required in Website Vault." if result.get("requires_profile") else result["dashboard"]["summary"]
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
            settings = self.get_settings(db)
            db.add(VoiceHistory(event_type=event_type, personality=settings.response_style, input_text=transcript, response_text=response, context_json=json.dumps({"mode": mode, **detail}, default=str), status=status))
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

    def _extract_number(self, text: str, default: int) -> int:
        match = re.search(r"(\d+(?:\.\d+)?)", text)
        return int(float(match.group(1))) if match else default

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

    def _should_speak(self, settings: VoiceAssistantSettings, response: str) -> bool:
        return bool(settings.voice_enabled and settings.response_style != "silent" and response.strip())

    def _response_context(self, result: dict) -> str:
        action = str(result.get("action", ""))
        response = str(result.get("response", "")).lower()
        if "battery" in action or "battery" in response:
            return "battery_status" if "status" in action else "battery_low"
        if "automation" in action:
            return "automation"
        if "reminder" in action:
            return "reminder"
        if "website" in action:
            return "website"
        if result.get("error"):
            return "error"
        if action in {"task_completed", "goal_completed", "automation_completed"}:
            return "completion"
        return "notification"

    def _notification_context(self, text: str) -> str:
        lower = text.lower()
        if "battery" in lower:
            return "battery_low"
        if "automation" in lower:
            return "automation"
        if "website" in lower:
            return "website"
        return "notification"

    def _active_profile(self, settings: VoiceAssistantSettings) -> dict:
        style = "minimal" if settings.response_style == "concise" else settings.response_style
        if style == "custom":
            custom = None
            with self.db_factory() as db:
                if settings.custom_personality_id:
                    custom = db.get(CustomPersonality, settings.custom_personality_id)
                if not custom:
                    custom = db.query(CustomPersonality).filter(CustomPersonality.enabled.is_(True)).order_by(CustomPersonality.updated_at.desc()).first()
                if custom:
                    return {
                        "wake": json.loads(custom.wake_responses_json or "[]"),
                        "completion": json.loads(custom.completion_responses_json or "[]"),
                        "reminder": json.loads(custom.reminder_responses_json or "[]"),
                        "error": json.loads(custom.error_responses_json or "[]"),
                        "notifications": json.loads(custom.notification_responses_json or "{}"),
                    }
            return {
                "wake": settings.custom_wake_responses or ["I'm listening."],
                "completion": settings.custom_completion_responses or ["Done."],
                "reminder": settings.custom_reminder_responses or ["You have a reminder."],
                "error": settings.custom_error_responses or ["I could not complete that."],
                "notifications": settings.custom_notification_responses or {},
            }
        return self.built_in_profiles.get(style, self.built_in_profiles["professional"])

    def _first_response(self, responses: list[str], default: str) -> str:
        clean = [item for item in responses if item is not None]
        if not clean:
            return default
        index = int(datetime.utcnow().timestamp()) % len(clean)
        return clean[index]

    def _battery_personality_response(self, default: str, style: str) -> str:
        if style == "minimal":
            return default.replace("Battery is currently", "Battery").replace(" and charging.", ", charging.").replace(" and running on battery power.", ", unplugged.")
        if style == "jarvis":
            return default.replace("Battery is currently", "Battery reserves are at").replace(" and running on battery power.", " and external power is disconnected.")
        if style == "friendly":
            return default.replace("Battery is currently", "Your battery is at")
        if style == "funny":
            return default.replace("Battery is currently", "Your battery snack meter is at")
        return default

    def _analytics(self, db: Session, personality: str, wake: int = 0, commands: int = 0, spoken: int = 0, errors: int = 0, muted: int = 0) -> None:
        today = date.today().isoformat()
        row = db.query(VoiceAnalytics).filter(VoiceAnalytics.analytics_date == today, VoiceAnalytics.personality == personality).first()
        if row is None:
            row = VoiceAnalytics(analytics_date=today, personality=personality)
            db.add(row)
        row.wake_count = (row.wake_count or 0) + wake
        row.command_count = (row.command_count or 0) + commands
        row.spoken_response_count = (row.spoken_response_count or 0) + spoken
        row.error_count = (row.error_count or 0) + errors
        row.muted_count = (row.muted_count or 0) + muted

    def _voice_statistics(self, analytics: list[dict]) -> dict:
        return {
            "wake_count": sum(item["wake_count"] for item in analytics),
            "command_count": sum(item["command_count"] for item in analytics),
            "spoken_response_count": sum(item["spoken_response_count"] for item in analytics),
            "error_count": sum(item["error_count"] for item in analytics),
            "muted_count": sum(item["muted_count"] for item in analytics),
        }

    def _profile_dict(self, row: VoiceProfile) -> dict:
        return {"id": row.id, "profile_key": row.profile_key, "name": row.name, "style": row.style, "description": row.description, "wake_responses": json.loads(row.wake_responses_json or "[]"), "completion_responses": json.loads(row.completion_responses_json or "[]"), "reminder_responses": json.loads(row.reminder_responses_json or "[]"), "error_responses": json.loads(row.error_responses_json or "[]"), "notification_responses": json.loads(row.notification_responses_json or "{}"), "tts_settings": json.loads(row.tts_settings_json or "{}"), "built_in": row.built_in, "enabled": row.enabled, "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat()}

    def _custom_personality_dict(self, row: CustomPersonality) -> dict:
        return {"id": row.id, "name": row.name, "greeting_style": row.greeting_style, "wake_responses": json.loads(row.wake_responses_json or "[]"), "completion_responses": json.loads(row.completion_responses_json or "[]"), "reminder_responses": json.loads(row.reminder_responses_json or "[]"), "error_responses": json.loads(row.error_responses_json or "[]"), "notification_responses": json.loads(row.notification_responses_json or "{}"), "enabled": row.enabled, "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat()}

    def _voice_history_dict(self, row: VoiceHistory) -> dict:
        return {"id": row.id, "event_type": row.event_type, "personality": row.personality, "input_text": row.input_text, "response_text": row.response_text, "context": json.loads(row.context_json or "{}"), "status": row.status, "created_at": row.created_at.isoformat()}

    def _wake_history_dict(self, row: WakeWordHistory) -> dict:
        return {"id": row.id, "phrase": row.phrase, "source": row.source, "confidence": row.confidence, "personality": row.personality, "response_text": row.response_text, "status": row.status, "created_at": row.created_at.isoformat()}

    def _voice_analytics_dict(self, row: VoiceAnalytics) -> dict:
        return {"id": row.id, "analytics_date": row.analytics_date, "personality": row.personality, "wake_count": row.wake_count or 0, "command_count": row.command_count or 0, "spoken_response_count": row.spoken_response_count or 0, "error_count": row.error_count or 0, "muted_count": row.muted_count or 0, "metadata": json.loads(row.metadata_json or "{}"), "created_at": row.created_at.isoformat()}

    def _validate(self, settings: VoiceAssistantSettings) -> None:
        if not settings.wake_phrases:
            raise ValueError("At least one wake phrase is required")
        if settings.response_style not in self.personality_modes:
            raise ValueError(f"response_style must be one of {sorted(self.personality_modes)}")
        if settings.response_style not in {"custom", "silent"} and settings.activation_response not in self.wake_responses:
            raise ValueError("activation_response must be a supported wake response unless response_style is custom")
        if not 0 <= settings.voice_volume <= 100:
            raise ValueError("voice_volume must be between 0 and 100")
        if not -10 <= settings.voice_speed <= 10:
            raise ValueError("voice_speed must be between -10 and 10")
        if not 0.1 <= settings.sensitivity <= 1.0:
            raise ValueError("sensitivity must be between 0.1 and 1.0")


voice_assistant_service = VoiceAssistantService()
