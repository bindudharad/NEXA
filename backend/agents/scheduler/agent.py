from datetime import datetime, timedelta
from uuid import uuid4

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.agents.notifications import NotificationAgent
from backend.agents.system import SystemAgent
from backend.agents.file_agent import FileAgent


class SchedulerAgent:
    def __init__(self) -> None:
        self.scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
        self.system = SystemAgent()
        if not self.scheduler.running:
            self.scheduler.start()

    def execute(self, action: str, params: dict) -> dict:
        return getattr(self, action)(**params)

    def schedule_delay(self, command: str, delay_seconds: int) -> dict:
        run_at = datetime.now() + timedelta(seconds=delay_seconds)
        return self.schedule_at(command, run_at.isoformat())

    def schedule_at(self, command: str, run_at: str) -> dict:
        job_id = f"{command}-{uuid4().hex[:8]}"
        self.scheduler.add_job(lambda: self._run_command(command), "date", run_date=datetime.fromisoformat(run_at), id=job_id)
        return {"job_id": job_id, "run_at": run_at, "command": command}

    def create_reminder(self, text: str, run_at: str | None = None) -> dict:
        when = datetime.fromisoformat(run_at) if run_at else datetime.now() + timedelta(minutes=5)
        job_id = f"reminder-{uuid4().hex[:8]}"
        self.scheduler.add_job(
            lambda: NotificationAgent().notify("Reminder", text),
            "date",
            run_date=when,
            id=job_id,
        )
        return {"job_id": job_id, "run_at": when.isoformat(), "text": text}

    def schedule_daily(self, command: str, hour: int, minute: int = 0) -> dict:
        return self._schedule_cron(command, CronTrigger(hour=hour, minute=minute), "daily")

    def schedule_weekly(self, command: str, day_of_week: str, hour: int, minute: int = 0) -> dict:
        return self._schedule_cron(command, CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute), "weekly")

    def schedule_monthly(self, command: str, day: int, hour: int, minute: int = 0) -> dict:
        return self._schedule_cron(command, CronTrigger(day=day, hour=hour, minute=minute), "monthly")

    def _schedule_cron(self, command: str, trigger: CronTrigger, cadence: str) -> dict:
        job_id = f"{cadence}-{command}-{uuid4().hex[:8]}"
        self.scheduler.add_job(lambda: self._run_command(command), trigger, id=job_id)
        return {"job_id": job_id, "command": command, "cadence": cadence}

    def _run_command(self, command: str) -> dict:
        if command in {"shutdown", "restart", "sleep", "lock"}:
            return self.system.execute(command, {})
        if command == "backup":
            return FileAgent().backup_folder("scheduled backup")
        return NotificationAgent().notify("Scheduled task", command)

    def jobs(self) -> list[dict]:
        return [{"id": job.id, "next_run_time": str(job.next_run_time), "name": job.name} for job in self.scheduler.get_jobs()]
