import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class PlannedAction:
    intent: str
    agent: str
    action: str
    params: dict = field(default_factory=dict)
    requires_confirmation: bool = False


class PlannerAgent:
    """Rule-first planner with a clean seam for OpenAI/Ollama expansion."""

    dangerous_actions = {"delete_file", "delete_folder", "shutdown", "restart", "kill_process"}
    desktop_apps = {"chrome", "google chrome", "vs code", "vscode", "visual studio code", "cursor", "notepad", "calculator", "spotify"}

    def plan(self, command: str) -> PlannedAction:
        text = command.strip()
        lower = text.lower()

        if match := re.search(r"shutdown after (\d+) (minute|minutes|second|seconds|hour|hours)", lower):
            return PlannedAction(
                intent="schedule_delayed_system_action",
                agent="scheduler",
                action="schedule_delay",
                params={"command": "shutdown", "delay_seconds": self._duration_to_seconds(match)},
                requires_confirmation=True,
            )
        if match := re.search(r"(restart|shutdown).*(?:at )(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", lower):
            hour = int(match.group(2))
            minute = int(match.group(3) or 0)
            meridiem = match.group(4)
            if meridiem == "pm" and hour < 12:
                hour += 12
            if meridiem == "am" and hour == 12:
                hour = 0
            run_at = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
            if run_at <= datetime.now():
                run_at += timedelta(days=1)
            return PlannedAction(
                intent="schedule_system_action",
                agent="scheduler",
                action="schedule_at",
                params={"command": match.group(1), "run_at": run_at.isoformat()},
                requires_confirmation=True,
            )
        if lower.startswith("open "):
            target = text[5:].strip()
            if "." in target or target.lower() in {"github", "google", "stackoverflow", "stack overflow"}:
                return PlannedAction("open_website", "browser", "open_url", {"target": target})
            if target.lower() not in self.desktop_apps:
                return PlannedAction("open_website_profile", "website", "open_profile", {"name": target}, requires_confirmation=True)
            return PlannedAction("launch_application", "system", "launch_app", {"name": target})
        if match := re.search(r"(?:login to|show|check|open) (kcet|college|contineo|gmail|github|attendance|internal marks|exam results|marks card)(?: result| results)?", lower):
            return PlannedAction("website_profile_action", "website", "open_profile", {"name": match.group(1)}, requires_confirmation=True)
        if lower.startswith("search google for "):
            return PlannedAction("google_search", "browser", "search_google", {"query": text[18:].strip()})
        if match := re.search(r"create (?:a )?file (?:called |named )?(.+)", lower):
            return PlannedAction("create_file", "file", "create_file", {"path": match.group(1).strip()})
        if match := re.search(r"create (?:a )?folder (?:called |named )?(.+)", lower):
            return PlannedAction("create_folder", "file", "create_folder", {"path": match.group(1).strip()})
        if match := re.search(r"delete (?:file|folder) (.+)", lower):
            action = "delete_folder" if "delete folder" in lower else "delete_file"
            return PlannedAction("delete_path", "file", action, {"path": match.group(1).strip()}, requires_confirmation=True)
        if match := re.search(r"find files? (?:called |named |matching )?(.+)", lower):
            return PlannedAction("search_files", "file", "search_files", {"query": match.group(1).strip()})
        if "move all pdf" in lower:
            return PlannedAction("organize_files", "file", "move_by_extension", {"extension": ".pdf", "destination": "Documents"})
        if "duplicate file" in lower:
            return PlannedAction("find_duplicates", "file", "find_duplicates", {})
        if "coded today" in lower or "coding today" in lower:
            return PlannedAction("coding_report", "coding", "daily_report", {})
        if "coded this week" in lower or "coding week" in lower:
            return PlannedAction("weekly_coding_report", "coding", "weekly_report", {})
        if "backup" in lower and ("night" in lower or "daily" in lower or "every day" in lower):
            return PlannedAction("scheduled_backup", "scheduler", "schedule_daily", {"command": "backup", "hour": 23, "minute": 0})
        if lower.startswith("remind me"):
            return PlannedAction("create_reminder", "scheduler", "create_reminder", {"text": text})
        if "backup" in lower:
            return PlannedAction("backup", "file", "backup_folder", {"command": text})
        if "cpu" in lower or "ram" in lower or "battery" in lower:
            return PlannedAction("system_status", "system", "status", {})
        return PlannedAction("general_memory", "memory", "remember_command", {"command": text})

    def _duration_to_seconds(self, match: re.Match[str]) -> int:
        value = int(match.group(1))
        unit = match.group(2)
        if unit.startswith("hour"):
            return value * 3600
        if unit.startswith("minute"):
            return value * 60
        return value
