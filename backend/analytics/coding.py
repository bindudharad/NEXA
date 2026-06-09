from datetime import datetime, timedelta
import json
from pathlib import Path
import subprocess

import psutil
from sqlalchemy.orm import Session

from backend.database.models import ActivityLog, CodingSession


class CodingAnalytics:
    code_process_names = {
        "code.exe": "VS Code",
        "cursor.exe": "Cursor",
        "windsurf.exe": "Windsurf",
        "devenv.exe": "Visual Studio",
        "rider64.exe": "JetBrains Rider",
        "idea64.exe": "IntelliJ IDEA",
        "pycharm64.exe": "PyCharm",
        "webstorm64.exe": "WebStorm",
        "phpstorm64.exe": "PhpStorm",
        "sublime_text.exe": "Sublime Text",
        "notepad++.exe": "Notepad++",
        "vim.exe": "Vim",
        "nvim.exe": "Neovim",
        "emacs.exe": "Emacs",
        "wt.exe": "Windows Terminal",
        "windowsterminal.exe": "Windows Terminal",
        "powershell.exe": "PowerShell",
        "cmd.exe": "Command Prompt",
    }
    distraction_process_names = {
        "youtube",
        "instagram",
        "facebook",
        "netflix",
        "spotify",
        "vlc",
        "steam",
        "discord",
        "tiktok",
        "reels",
        "primevideo",
        "hotstar",
    }
    coding_interactions = {
        "typing",
        "keyboard",
        "mouse",
        "click",
        "file_switch",
        "file_edit",
        "terminal_command",
        "git_command",
        "debugger",
        "refactor",
        "search",
        "project_navigation",
        "build",
        "test",
    }
    idle_timeout_seconds = 30
    active_threshold = 55

    def __init__(self, db: Session) -> None:
        self.db = db

    def snapshot(self) -> dict:
        active_apps = []
        distracting_apps = []
        for proc in psutil.process_iter(["name"]):
            name = (proc.info.get("name") or "").lower()
            if name in self.code_process_names:
                active_apps.append(self.code_process_names[name])
            if any(term in name for term in self.distraction_process_names):
                distracting_apps.append(name)
        row = ActivityLog(
            activity_type="coding_snapshot",
            app_name=", ".join(sorted(set(active_apps))),
            detail_json=json.dumps({"active_apps": sorted(set(active_apps)), "distracting_apps": sorted(set(distracting_apps))}),
        )
        self.db.add(row)
        self.db.commit()
        return {"active_apps": sorted(set(active_apps)), "distracting_apps": sorted(set(distracting_apps)), "active_coding_detected": bool(active_apps) and not distracting_apps}

    def record_activity(self, payload: dict) -> dict:
        now = datetime.utcnow()
        app_name = str(payload.get("app_name") or "").strip()
        process_name = str(payload.get("process_name") or "").lower().strip()
        window_title = str(payload.get("window_title") or "").lower()
        project = str(payload.get("project") or "").strip()
        interaction = str(payload.get("interaction_type") or "").lower().strip()
        duration_seconds = max(0, min(int(payload.get("duration_seconds") or 0), 3600))
        idle_seconds = max(0, int(payload.get("idle_seconds") or 0))
        keystrokes = max(0, int(payload.get("keystrokes") or 0))
        mouse_events = max(0, int(payload.get("mouse_events") or 0))
        file_changes = max(0, int(payload.get("file_changes") or 0))
        terminal_commands = max(0, int(payload.get("terminal_commands") or 0))
        git_commands = max(0, int(payload.get("git_commands") or 0))
        custom_editor = bool(payload.get("custom_editor"))

        app_label = self.code_process_names.get(process_name, app_name or process_name or "Unknown")
        non_coding_reason = self._non_coding_reason(app_name, process_name, window_title)
        activity_score = self._activity_score(interaction, keystrokes, mouse_events, file_changes, terminal_commands, git_commands, idle_seconds, custom_editor, process_name)
        is_editor = process_name in self.code_process_names or custom_editor or any(term in app_name.lower() for term in ["code", "cursor", "jetbrains", "visual studio", "sublime", "notepad++", "windsurf"])
        active = is_editor and non_coding_reason == "" and idle_seconds < self.idle_timeout_seconds and activity_score >= self.active_threshold and duration_seconds > 0
        counted_seconds = duration_seconds if active else 0
        deep_seconds = counted_seconds if activity_score >= 80 and file_changes + terminal_commands + git_commands > 0 else 0
        distraction_seconds = duration_seconds if non_coding_reason else 0
        idle_counted_seconds = duration_seconds if idle_seconds >= self.idle_timeout_seconds else 0

        detail = {
            "app_name": app_name,
            "process_name": process_name,
            "window_title": window_title[:200],
            "interaction_type": interaction,
            "duration_seconds": duration_seconds,
            "counted_seconds": counted_seconds,
            "deep_seconds": deep_seconds,
            "idle_seconds": idle_seconds,
            "idle_counted_seconds": idle_counted_seconds,
            "distraction_seconds": distraction_seconds,
            "activity_score": activity_score,
            "active": active,
            "reason": "active_coding" if active else non_coding_reason or "activity_below_threshold",
            "language": payload.get("language") or self._language_from_payload(payload),
            "files_modified": file_changes,
            "terminal_commands": terminal_commands,
            "git_commands": git_commands,
            "branch": payload.get("branch", ""),
            "builds": max(0, int(payload.get("builds") or 0)),
            "tests": max(0, int(payload.get("tests") or 0)),
            "errors_fixed": max(0, int(payload.get("errors_fixed") or 0)),
        }
        self.db.add(ActivityLog(activity_type="coding_activity", app_name=app_label, project=project, detail_json=json.dumps(detail, default=str), created_at=now))
        session = None
        if active:
            session = CodingSession(
                app_name=app_label,
                project=project,
                duration_seconds=counted_seconds,
                files_modified=file_changes,
                commits=git_commands,
                started_at=now - timedelta(seconds=counted_seconds),
                ended_at=now,
            )
            self.db.add(session)
        self.db.commit()
        return {
            "counted": active,
            "activity_score": activity_score,
            "counted_seconds": counted_seconds,
            "deep_seconds": deep_seconds,
            "idle_seconds": idle_counted_seconds,
            "distraction_seconds": distraction_seconds,
            "reason": detail["reason"],
            "session_id": session.id if session else None,
            "project": project,
            "app_name": app_label,
        }

    def daily_report(self) -> dict:
        since = datetime.utcnow() - timedelta(days=1)
        return self._report_since(since)

    def weekly_report(self) -> dict:
        since = datetime.utcnow() - timedelta(days=7)
        return self._report_since(since)

    def _report_since(self, since: datetime) -> dict:
        sessions = self.db.query(CodingSession).filter(CodingSession.started_at >= since).all()
        activity_logs = self.db.query(ActivityLog).filter(ActivityLog.activity_type == "coding_activity", ActivityLog.created_at >= since).all()
        totals: dict[str, int] = {}
        project_totals: dict[str, int] = {}
        languages: dict[str, int] = {}
        files = 0
        commits = 0
        for session in sessions:
            totals[session.app_name] = totals.get(session.app_name, 0) + session.duration_seconds
            if session.project:
                project_totals[session.project] = project_totals.get(session.project, 0) + session.duration_seconds
            files += session.files_modified
            commits += session.commits
        idle_seconds = 0
        distraction_seconds = 0
        deep_seconds = 0
        activity_scores = []
        terminal_commands = 0
        builds = 0
        tests = 0
        errors_fixed = 0
        for log in activity_logs:
            detail = self._loads(log.detail_json)
            idle_seconds += int(detail.get("idle_counted_seconds") or 0)
            distraction_seconds += int(detail.get("distraction_seconds") or 0)
            deep_seconds += int(detail.get("deep_seconds") or 0)
            terminal_commands += int(detail.get("terminal_commands") or 0)
            builds += int(detail.get("builds") or 0)
            tests += int(detail.get("tests") or 0)
            errors_fixed += int(detail.get("errors_fixed") or 0)
            if detail.get("active"):
                activity_scores.append(float(detail.get("activity_score") or 0))
                language = str(detail.get("language") or "").strip()
                if language:
                    languages[language] = languages.get(language, 0) + int(detail.get("counted_seconds") or 0)
        git_commits = self._count_git_commits(Path.cwd(), since)
        real_coding_seconds = sum(totals.values())
        session_count = len(sessions)
        productivity_score = self._productivity_score(real_coding_seconds, deep_seconds, idle_seconds, distraction_seconds, activity_scores)
        insights = self._insights(real_coding_seconds, deep_seconds, idle_seconds, distraction_seconds, productivity_score, project_totals)
        return {
            "apps": {key: self._format_seconds(value) for key, value in totals.items()},
            "real_coding_seconds": real_coding_seconds,
            "coding_time": self._format_seconds(real_coding_seconds),
            "total_time": self._format_seconds(real_coding_seconds),
            "deep_coding_seconds": deep_seconds,
            "deep_coding_time": self._format_seconds(deep_seconds),
            "focus_coding_seconds": max(0, real_coding_seconds - idle_seconds - distraction_seconds),
            "focus_coding_time": self._format_seconds(max(0, real_coding_seconds - idle_seconds - distraction_seconds)),
            "idle_seconds": idle_seconds,
            "idle_time": self._format_seconds(idle_seconds),
            "distraction_seconds": distraction_seconds,
            "distraction_time": self._format_seconds(distraction_seconds),
            "learning_seconds": 0,
            "learning_time": "0h 0m",
            "activity_score": round(sum(activity_scores) / max(len(activity_scores), 1), 1) if activity_scores else 0,
            "productivity_score": productivity_score,
            "average_session": self._format_seconds(real_coding_seconds // max(session_count, 1)),
            "longest_session": self._format_seconds(max([session.duration_seconds for session in sessions], default=0)),
            "files_modified": files,
            "commits": commits + git_commits,
            "terminal_commands": terminal_commands,
            "builds": builds,
            "tests": tests,
            "errors_fixed": errors_fixed,
            "projects": self._detect_projects(),
            "project_time": {key: self._format_seconds(value) for key, value in sorted(project_totals.items(), key=lambda item: item[1], reverse=True)},
            "languages": {key: self._format_seconds(value) for key, value in sorted(languages.items(), key=lambda item: item[1], reverse=True)},
            "insights": insights,
            "validation": {
                "idle_timeout_seconds": self.idle_timeout_seconds,
                "active_threshold": self.active_threshold,
                "counts_only_active_work": True,
                "excludes_distractions": True,
            },
        }

    def _detect_projects(self) -> list[str]:
        roots = [Path.home() / "Projects", Path.cwd()]
        projects = []
        for root in roots:
            if root.exists():
                projects.extend([p.name for p in root.iterdir() if p.is_dir() and (p / ".git").exists()])
        return sorted(set(projects))[:20]

    def _count_git_commits(self, root: Path, since: datetime) -> int:
        try:
            result = subprocess.run(
                ["git", "-C", str(root), "log", "--since", since.isoformat(), "--oneline"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return len([line for line in result.stdout.splitlines() if line.strip()])
        except Exception:
            return 0

    def _format_seconds(self, seconds: int) -> str:
        hours, remainder = divmod(seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        return f"{hours}h {minutes}m"

    def _activity_score(self, interaction: str, keystrokes: int, mouse_events: int, file_changes: int, terminal_commands: int, git_commands: int, idle_seconds: int, custom_editor: bool, process_name: str) -> int:
        score = 0
        if process_name in self.code_process_names or custom_editor:
            score += 20
        if interaction in self.coding_interactions:
            score += 20
        score += min(25, keystrokes * 2)
        score += min(12, mouse_events)
        score += min(18, file_changes * 6)
        score += min(15, terminal_commands * 5)
        score += min(10, git_commands * 5)
        if idle_seconds >= self.idle_timeout_seconds:
            score -= 45
        return max(0, min(100, score))

    def _non_coding_reason(self, app_name: str, process_name: str, window_title: str) -> str:
        haystack = " ".join([app_name.lower(), process_name.lower(), window_title.lower()])
        if any(term in haystack for term in self.distraction_process_names):
            return "distraction_app"
        if any(term in haystack for term in ["youtube", "reels", "movie", "music only", "video playback", "instagram", "facebook", "game"]):
            return "non_coding_activity"
        return ""

    def _language_from_payload(self, payload: dict) -> str:
        file_path = str(payload.get("file_path") or payload.get("active_file") or "")
        suffix = Path(file_path).suffix.lower()
        return {
            ".py": "Python",
            ".js": "JavaScript",
            ".jsx": "React",
            ".ts": "TypeScript",
            ".tsx": "React TypeScript",
            ".java": "Java",
            ".c": "C",
            ".cpp": "C++",
            ".cs": "C#",
            ".go": "Go",
            ".rs": "Rust",
            ".html": "HTML",
            ".css": "CSS",
        }.get(suffix, "")

    def _productivity_score(self, real_seconds: int, deep_seconds: int, idle_seconds: int, distraction_seconds: int, activity_scores: list[float]) -> int:
        if real_seconds <= 0:
            return 0
        activity = sum(activity_scores) / max(len(activity_scores), 1)
        deep_ratio = deep_seconds / max(real_seconds, 1)
        penalty = min(35, (idle_seconds + distraction_seconds) / max(real_seconds + idle_seconds + distraction_seconds, 1) * 60)
        score = 35 + activity * 0.35 + deep_ratio * 30 - penalty
        return round(max(0, min(100, score)))

    def _insights(self, real_seconds: int, deep_seconds: int, idle_seconds: int, distraction_seconds: int, productivity_score: int, project_totals: dict[str, int]) -> list[str]:
        insights = []
        if productivity_score >= 80:
            insights.append("Coding efficiency is strong. Keep protecting the same focus window.")
        elif productivity_score > 0:
            insights.append("Coding activity is present, but focus quality can improve.")
        if distraction_seconds:
            insights.append("Distractions were excluded from coding time.")
        if idle_seconds:
            insights.append("Idle time was detected and removed from coding totals.")
        if deep_seconds >= 3600:
            insights.append("Deep coding time crossed one hour in this period.")
        if project_totals:
            project = max(project_totals.items(), key=lambda item: item[1])[0]
            insights.append(f"Most coding time was spent on {project}.")
        if not insights and real_seconds == 0:
            insights.append("No active coding work recorded in this period.")
        return insights

    def _loads(self, value: str) -> dict:
        try:
            return json.loads(value or "{}")
        except Exception:
            return {}
