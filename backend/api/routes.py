import json

import asyncio

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from backend.agents.browser import BrowserAgent
from backend.agents.coding import CodingAgent
from backend.agents.file_agent import FileAgent
from backend.agents.memory import MemoryAgent
from backend.agents.notifications import NotificationAgent
from backend.agents.scheduler import SchedulerAgent
from backend.agents.system import SystemAgent
from backend.api.dependencies import require_api_key
from backend.api.schemas import AutomationRequest, BatteryAlertSettingsRequest, BatterySimulationRequest, BrowserDownloadRequest, BrowserFormRequest, CommandRequest, EventRequest, FileOperationRequest, MemoryRequest, NotificationRequest
from backend.automation import AutomationEngine
from backend.core.task_manager import TaskManager
from backend.database.models import Notification, Task
from backend.database.session import get_db
from backend.services.battery_alert import battery_alert_service

router = APIRouter(dependencies=[Depends(require_api_key)])
scheduler = SchedulerAgent()


def serialize_task(task: Task) -> dict:
    return {
        "id": task.id,
        "command": task.command,
        "intent": task.intent,
        "agent": task.agent,
        "status": task.status,
        "requires_confirmation": task.requires_confirmation,
        "plan": json.loads(task.plan_json),
        "result": json.loads(task.result_json),
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
    }


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "nexa"}


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)) -> dict:
    system = SystemAgent().status()
    tasks = db.query(Task).order_by(Task.created_at.desc()).limit(10).all()
    notifications = db.query(Notification).order_by(Notification.created_at.desc()).limit(10).all()
    return {
        "system": system,
        "battery_alert": battery_alert_service.get_status(),
        "tasks": [serialize_task(task) for task in tasks],
        "automations": AutomationEngine(db).list(),
        "notifications": [{"id": item.id, "title": item.title, "message": item.message, "read": item.read} for item in notifications],
        "scheduled_jobs": scheduler.jobs(),
    }


@router.post("/commands")
def run_command(request: CommandRequest, db: Session = Depends(get_db)) -> dict:
    task = TaskManager(db, scheduler).create_from_command(request.command, request.auto_confirm)
    return serialize_task(task)


@router.post("/tasks/{task_id}/confirm")
def confirm_task(task_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        task = TaskManager(db, scheduler).confirm(task_id)
        return serialize_task(task)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/tasks")
def list_tasks(db: Session = Depends(get_db)) -> list[dict]:
    return [serialize_task(task) for task in db.query(Task).order_by(Task.created_at.desc()).limit(100).all()]


@router.get("/system/status")
def system_status() -> dict:
    return SystemAgent().status()


@router.get("/battery-alert/settings")
def battery_alert_settings(db: Session = Depends(get_db)) -> dict:
    return battery_alert_service.get_settings(db).__dict__


@router.put("/battery-alert/settings")
def update_battery_alert_settings(request: BatteryAlertSettingsRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return battery_alert_service.update_settings(request.model_dump(exclude_unset=True), db)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/battery-alert/status")
def battery_alert_status() -> dict:
    return battery_alert_service.get_status()


@router.post("/battery-alert/test/simulate")
def simulate_battery_alert(request: BatterySimulationRequest) -> dict:
    try:
        return battery_alert_service.simulate(request.battery_percent, request.is_charging)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/battery-alert/test/clear")
def clear_battery_alert_simulation() -> dict:
    return battery_alert_service.clear_simulation()


@router.get("/coding/report")
def coding_report(db: Session = Depends(get_db)) -> dict:
    return CodingAgent(db).daily_report()


@router.get("/coding/weekly-report")
def weekly_coding_report(db: Session = Depends(get_db)) -> dict:
    return CodingAgent(db).weekly_report()


@router.post("/coding/snapshot")
def coding_snapshot(db: Session = Depends(get_db)) -> dict:
    return CodingAgent(db).snapshot()


@router.get("/memory")
def list_memory(db: Session = Depends(get_db)) -> list[dict]:
    return MemoryAgent(db).list()


@router.post("/memory")
def add_memory(request: MemoryRequest, db: Session = Depends(get_db)) -> dict:
    return MemoryAgent(db).set(request.key, request.value, request.scope)


@router.get("/memory/conversation-history")
def conversation_history(db: Session = Depends(get_db)) -> list[dict]:
    return MemoryAgent(db).conversation_history()


@router.post("/settings")
def set_setting(request: MemoryRequest, db: Session = Depends(get_db)) -> dict:
    return MemoryAgent(db).set_setting(request.key, request.value)


@router.get("/automations")
def list_automations(db: Session = Depends(get_db)) -> list[dict]:
    return AutomationEngine(db).list()


@router.post("/automations")
def create_automation(request: AutomationRequest, db: Session = Depends(get_db)) -> dict:
    return AutomationEngine(db).create(request.name, request.condition, request.action)


@router.post("/automations/evaluate")
def evaluate_automations(db: Session = Depends(get_db)) -> list[dict]:
    return AutomationEngine(db).evaluate()


@router.post("/events")
def ingest_event(request: EventRequest, db: Session = Depends(get_db)) -> list[dict]:
    return AutomationEngine(db).ingest_event(request.event_type, request.payload)


@router.post("/notifications")
def send_notification(request: NotificationRequest, db: Session = Depends(get_db)) -> dict:
    return NotificationAgent(db).notify(request.title, request.message)


@router.post("/files/create")
def create_file(request: FileOperationRequest) -> dict:
    return FileAgent().create_file(request.path, request.content)


@router.post("/files/delete")
def delete_file(request: FileOperationRequest, x_confirm_danger: str | None = Header(default=None)) -> dict:
    if x_confirm_danger != "true":
        raise HTTPException(status_code=409, detail="Dangerous file deletion requires X-Confirm-Danger: true")
    return FileAgent().delete_file(request.path)


@router.post("/files/move")
def move_file(request: FileOperationRequest) -> dict:
    if not request.destination:
        raise HTTPException(status_code=422, detail="destination is required")
    return FileAgent().move_file(request.path, request.destination)


@router.post("/files/rename")
def rename_file(request: FileOperationRequest) -> dict:
    if not request.new_name:
        raise HTTPException(status_code=422, detail="new_name is required")
    return FileAgent().rename_file(request.path, request.new_name)


@router.post("/files/search")
def search_files(request: FileOperationRequest) -> dict:
    if not request.query:
        raise HTTPException(status_code=422, detail="query is required")
    return FileAgent().search_files(request.query, request.path)


@router.post("/browser/search")
def browser_search(request: MemoryRequest) -> dict:
    return asyncio.run(BrowserAgent().search_google(request.value))


@router.post("/browser/fill-form")
def browser_fill_form(request: BrowserFormRequest) -> dict:
    return asyncio.run(BrowserAgent().fill_form(request.url, request.fields, request.submit_selector))


@router.post("/browser/download")
def browser_download(request: BrowserDownloadRequest) -> dict:
    return asyncio.run(BrowserAgent().download_file(request.url, request.click_selector, request.destination))
