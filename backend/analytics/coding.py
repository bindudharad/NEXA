from datetime import datetime, timedelta
from pathlib import Path
import subprocess

import psutil
from sqlalchemy.orm import Session

from backend.database.models import ActivityLog, CodingSession


class CodingAnalytics:
    code_process_names = {"code.exe": "VS Code", "cursor.exe": "Cursor", "chrome.exe": "Chrome"}

    def __init__(self, db: Session) -> None:
        self.db = db

    def snapshot(self) -> dict:
        active_apps = []
        for proc in psutil.process_iter(["name"]):
            name = (proc.info.get("name") or "").lower()
            if name in self.code_process_names:
                active_apps.append(self.code_process_names[name])
        row = ActivityLog(activity_type="coding_snapshot", app_name=", ".join(sorted(set(active_apps))))
        self.db.add(row)
        self.db.commit()
        return {"active_apps": sorted(set(active_apps))}

    def daily_report(self) -> dict:
        since = datetime.utcnow() - timedelta(days=1)
        return self._report_since(since)

    def weekly_report(self) -> dict:
        since = datetime.utcnow() - timedelta(days=7)
        return self._report_since(since)

    def _report_since(self, since: datetime) -> dict:
        sessions = self.db.query(CodingSession).filter(CodingSession.started_at >= since).all()
        totals: dict[str, int] = {}
        files = 0
        commits = 0
        for session in sessions:
            totals[session.app_name] = totals.get(session.app_name, 0) + session.duration_seconds
            files += session.files_modified
            commits += session.commits
        git_commits = self._count_git_commits(Path.cwd(), since)
        return {
            "apps": {key: self._format_seconds(value) for key, value in totals.items()},
            "files_modified": files,
            "commits": commits + git_commits,
            "projects": self._detect_projects(),
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
