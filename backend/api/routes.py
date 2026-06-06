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
from backend.ai.task_approval import TaskApprovalService
from backend.api.dependencies import require_api_key
from backend.api.schemas import ApprovalEditRequest, ApprovalRejectRequest, AutomationRequest, AutomationToggleRequest, BatteryAlertSettingsRequest, BatterySimulationRequest, BrowserDownloadRequest, BrowserFormRequest, CommandRequest, EventRequest, FileOperationRequest, GpuMonitorSettingsRequest, GpuSimulationRequest, KcetResultRequest, MemoryRequest, NotificationRequest, WebsiteActionRequest, WebsiteAnalyzeRequest, WebsiteCredentialRequest, WebsiteImportRequest, WebsiteMonitoringRequest, WebsiteOpenRequest, WebsiteProfileRequest
from backend.automation import AutomationEngine
from backend.core.task_manager import TaskManager
from backend.database.models import Automation, Notification, Task, TaskStatus
from backend.database.session import get_db
from backend.services.battery_alert import battery_alert_service
from backend.services.gpu_monitor import gpu_monitor_service
from backend.services.website_profiles import WebsiteProfileService

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
    gpu_status = gpu_monitor_service.get_status()
    system["gpu_percent"] = gpu_status.get("usage_percent")
    system["gpu_temperature_celsius"] = gpu_status.get("temperature_celsius")
    system["gpu_memory_usage_percent"] = gpu_status.get("memory_usage_percent")
    tasks = db.query(Task).order_by(Task.created_at.desc()).limit(10).all()
    notifications = db.query(Notification).order_by(Notification.created_at.desc()).limit(10).all()
    return {
        "system": system,
        "battery_alert": battery_alert_service.get_status(),
        "gpu_monitor": gpu_status,
        "tasks": [serialize_task(task) for task in tasks],
        "automations": AutomationEngine(db).list(),
        "notifications": [{"id": item.id, "title": item.title, "message": item.message, "read": item.read} for item in notifications],
        "scheduled_jobs": scheduler.jobs(),
    }


@router.post("/commands")
def run_command(request: CommandRequest, db: Session = Depends(get_db)) -> dict:
    approval = TaskApprovalService(db, scheduler).request_approval(request.command)
    return TaskApprovalService(db, scheduler).serialize(approval)


@router.get("/task-approvals")
def list_task_approvals(db: Session = Depends(get_db)) -> list[dict]:
    service = TaskApprovalService(db, scheduler)
    return [service.serialize(approval) for approval in service.list()]


@router.post("/task-approvals/{approval_id}/approve")
def approve_task_approval(approval_id: int, db: Session = Depends(get_db)) -> dict:
    service = TaskApprovalService(db, scheduler)
    try:
        approval, task = service.approve(approval_id)
        return service.serialize(approval, task)
    except ValueError as exc:
        raise HTTPException(status_code=409 if "clarification" in str(exc).lower() else 404, detail=str(exc)) from exc


@router.put("/task-approvals/{approval_id}/edit")
def edit_task_approval(approval_id: int, request: ApprovalEditRequest, db: Session = Depends(get_db)) -> dict:
    service = TaskApprovalService(db, scheduler)
    updates = request.model_dump(exclude_none=True)
    try:
        approval = service.edit(approval_id, updates)
        return service.serialize(approval)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/task-approvals/{approval_id}/reject")
def reject_task_approval(approval_id: int, request: ApprovalRejectRequest | None = None, db: Session = Depends(get_db)) -> dict:
    service = TaskApprovalService(db, scheduler)
    try:
        approval = service.reject(approval_id, request.reason if request else "")
        return service.serialize(approval)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: int, db: Session = Depends(get_db)) -> dict:
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status in {TaskStatus.completed.value, TaskStatus.failed.value, TaskStatus.cancelled.value}:
        return serialize_task(task)
    task.status = TaskStatus.cancelled.value
    db.commit()
    db.refresh(task)
    return serialize_task(task)


@router.post("/tasks/{task_id}/pause")
def pause_task(task_id: int, db: Session = Depends(get_db)) -> dict:
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status in {TaskStatus.created.value, TaskStatus.running.value, TaskStatus.pending_confirmation.value}:
        task.status = "paused"
        db.commit()
        db.refresh(task)
    return serialize_task(task)


@router.post("/tasks/{task_id}/resume")
def resume_task(task_id: int, db: Session = Depends(get_db)) -> dict:
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status == "paused":
        task.status = TaskStatus.created.value
        db.commit()
        db.refresh(task)
    return serialize_task(task)


@router.post("/tasks/{task_id}/retry")
def retry_task(task_id: int, db: Session = Depends(get_db)) -> dict:
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    TaskManager(db, scheduler).execute(task.id)
    db.refresh(task)
    return serialize_task(task)


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


@router.get("/gpu-monitor/settings")
def gpu_monitor_settings(db: Session = Depends(get_db)) -> dict:
    return gpu_monitor_service.get_settings(db).__dict__


@router.put("/gpu-monitor/settings")
def update_gpu_monitor_settings(request: GpuMonitorSettingsRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return gpu_monitor_service.update_settings(request.model_dump(exclude_unset=True), db)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/gpu-monitor/status")
def gpu_monitor_status() -> dict:
    return gpu_monitor_service.get_status()


@router.post("/gpu-monitor/test/simulate")
def simulate_gpu_monitor(request: GpuSimulationRequest) -> dict:
    return gpu_monitor_service.simulate(request.temperature_celsius, request.usage_percent, request.memory_usage_percent)


@router.post("/gpu-monitor/test/clear")
def clear_gpu_monitor_simulation() -> dict:
    return gpu_monitor_service.clear_simulation()


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


@router.put("/automations/{automation_id}/toggle")
def toggle_automation(automation_id: int, request: AutomationToggleRequest, db: Session = Depends(get_db)) -> dict:
    row = db.get(Automation, automation_id)
    if not row:
        raise HTTPException(status_code=404, detail="Automation not found")
    row.enabled = request.enabled
    db.commit()
    db.refresh(row)
    return AutomationEngine(db).serialize(row)


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
def browser_search(request: MemoryRequest, x_confirm_danger: str | None = Header(default=None)) -> dict:
    if x_confirm_danger != "true":
        raise HTTPException(status_code=409, detail="Browser automation requires task approval")
    return asyncio.run(BrowserAgent().search_google(request.value))


@router.post("/browser/fill-form")
def browser_fill_form(request: BrowserFormRequest, x_confirm_danger: str | None = Header(default=None)) -> dict:
    if x_confirm_danger != "true":
        raise HTTPException(status_code=409, detail="Browser automation requires task approval")
    return asyncio.run(BrowserAgent().fill_form(request.url, request.fields, request.submit_selector))


@router.post("/browser/download")
def browser_download(request: BrowserDownloadRequest, x_confirm_danger: str | None = Header(default=None)) -> dict:
    if x_confirm_danger != "true":
        raise HTTPException(status_code=409, detail="Browser automation requires task approval")
    return asyncio.run(BrowserAgent().download_file(request.url, request.click_selector, request.destination))


@router.get("/website-profiles")
def list_website_profiles(db: Session = Depends(get_db)) -> list[dict]:
    return WebsiteProfileService(db).list_profiles()


@router.post("/website-profiles/analyze")
def analyze_website(request: WebsiteAnalyzeRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return WebsiteProfileService(db).analyze(request.name, request.url, request.html, request.headless)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/website-profiles")
def create_website_profile(request: WebsiteProfileRequest, db: Session = Depends(get_db)) -> dict:
    return WebsiteProfileService(db).create_profile(
        request.name,
        request.url,
        request.field_mapping,
        request.navigation_rules,
        request.login_process,
        request.retry_policy,
        request.credentials,
        request.success_check,
    )


@router.delete("/website-profiles/{profile_id}")
def delete_website_profile(profile_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return WebsiteProfileService(db).delete_profile(profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/website-profiles/{profile_id}/export")
def export_website_profile(profile_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return WebsiteProfileService(db).export_profile(profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/website-profiles/{profile_id}/history")
def website_profile_history(profile_id: int, db: Session = Depends(get_db)) -> list[dict]:
    try:
        return WebsiteProfileService(db).history(profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/website-profiles/import")
def import_website_profile(request: WebsiteImportRequest, db: Session = Depends(get_db)) -> dict:
    return WebsiteProfileService(db).import_profile(request.payload)


@router.put("/website-profiles/{profile_id}/credentials")
def save_website_credentials(profile_id: int, request: WebsiteCredentialRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return WebsiteProfileService(db).save_credentials(profile_id, request.credentials, request.label)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/website-profiles/{profile_id}/auto-login")
def website_auto_login(profile_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return WebsiteProfileService(db).auto_login(profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/website-profiles/{profile_id}/actions")
def create_website_action(profile_id: int, request: WebsiteActionRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return WebsiteProfileService(db).create_action(profile_id, request.name, request.action)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/website-profiles/{profile_id}/monitoring")
def update_website_monitoring(profile_id: int, request: WebsiteMonitoringRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return WebsiteProfileService(db).set_monitoring(profile_id, request.enabled, request.interval_seconds)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/website-profiles/monitor/check")
def check_website_monitoring(db: Session = Depends(get_db)) -> list[dict]:
    return WebsiteProfileService(db).check_monitored()


@router.post("/websites/open")
def open_website_profile(request: WebsiteOpenRequest, db: Session = Depends(get_db)) -> dict:
    return WebsiteProfileService(db).open_or_request_profile(request.name)


@router.post("/websites/kcet-result")
def kcet_result(request: KcetResultRequest, db: Session = Depends(get_db)) -> dict:
    return WebsiteProfileService(db).kcet_result(request.application_number, request.date_of_birth, request.save_profile, request.url)
