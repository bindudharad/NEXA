import json
import logging
import inspect
import asyncio
from datetime import datetime

from sqlalchemy.orm import Session

from backend.agents.browser import BrowserAgent
from backend.agents.coding import CodingAgent
from backend.agents.file_agent import FileAgent
from backend.agents.memory import MemoryAgent
from backend.agents.planner import PlannerAgent, PlannedAction
from backend.agents.scheduler import SchedulerAgent
from backend.agents.system import SystemAgent
from backend.agents.website import WebsiteAgent
from backend.database.models import Task, TaskExecution, TaskStatus

logger = logging.getLogger(__name__)
task_logger = logging.getLogger("nexa.tasks")


class TaskManager:
    def __init__(self, db: Session, scheduler: SchedulerAgent | None = None) -> None:
        self.db = db
        self.planner = PlannerAgent()
        self.scheduler = scheduler or SchedulerAgent()

    def create_from_command(self, command: str, auto_confirm: bool = False) -> Task:
        plan = self.planner.plan(command)
        task = Task(
            command=command,
            intent=plan.intent,
            agent=plan.agent,
            status=TaskStatus.created.value,
            requires_confirmation=plan.requires_confirmation,
            plan_json=json.dumps(plan.__dict__, default=str),
        )
        self.db.add(task)
        self.db.commit()
        if plan.requires_confirmation and not auto_confirm:
            task.status = TaskStatus.pending_confirmation.value
            self.db.commit()
            return task
        self.execute(task.id)
        self.db.refresh(task)
        return task

    def confirm(self, task_id: int) -> Task:
        task = self.db.get(Task, task_id)
        if not task:
            raise ValueError("Task not found")
        self.execute(task.id)
        self.db.refresh(task)
        return task

    def execute(self, task_id: int) -> dict:
        task = self.db.get(Task, task_id)
        if not task:
            raise ValueError("Task not found")
        plan = PlannedAction(**json.loads(task.plan_json))
        execution = TaskExecution(task_id=task.id, status=TaskStatus.running.value, log="Started")
        self.db.add(execution)
        task.status = TaskStatus.running.value
        task.updated_at = datetime.utcnow()
        self.db.commit()
        task_logger.info("Task %s started: %s", task.id, task.command)
        try:
            agent = self._agent(plan.agent)
            result = agent.execute(plan.action, plan.params)
            if inspect.isawaitable(result):
                result = asyncio.run(result)
            task.status = TaskStatus.completed.value
            task.result_json = json.dumps(result, default=str)
            execution.status = TaskStatus.completed.value
            execution.log = json.dumps(result, default=str)
        except Exception as exc:
            logger.exception("Task failed")
            task_logger.error("Task %s failed: %s", task.id, exc)
            task.status = TaskStatus.failed.value
            task.result_json = json.dumps({"error": str(exc)})
            execution.status = TaskStatus.failed.value
            execution.log = str(exc)
        finally:
            execution.finished_at = datetime.utcnow()
            task.updated_at = datetime.utcnow()
            self.db.commit()
            if task.status == TaskStatus.completed.value:
                task_logger.info("Task %s completed", task.id)
        return json.loads(task.result_json)

    def _agent(self, name: str):
        if name == "file":
            return FileAgent()
        if name == "browser":
            return BrowserAgent()
        if name == "system":
            return SystemAgent()
        if name == "coding":
            return CodingAgent(self.db)
        if name == "scheduler":
            return self.scheduler
        if name == "memory":
            return MemoryAgent(self.db)
        if name == "website":
            return WebsiteAgent(self.db)
        raise ValueError(f"Unknown agent: {name}")
