import json

import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
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
from backend.api.schemas import (
    AlertSettingsRequest,
    ApprovalEditRequest,
    ApprovalRejectRequest,
    AutomationBuilderRequest,
    AutomationRequest,
    AutomationToggleRequest,
    BatteryAlertSettingsRequest,
    BatterySimulationRequest,
    BrowserDownloadRequest,
    BrowserFormRequest,
    CollegeCheckRequest,
    CollegeProfileRequest,
    CommandRequest,
    CodingActivityRequest,
    CopilotActionRequest,
    CopilotSuggestionStatusRequest,
    CopilotSettingsRequest,
    CustomPersonalityRequest,
    CustomPersonalityUpdateRequest,
    DailyBriefingRequest,
    DailyBriefingSettingsRequest,
    DownloadsOrganizeRequest,
    DownloadRuleRequest,
    DownloadsScanRequest,
    DownloadsSearchRequest,
    EventRequest,
    FileOperationRequest,
    FocusControlRequest,
    FocusDistractionRequest,
    FocusEndRequest,
    FocusGoalProgressRequest,
    FocusGoalRequest,
    FocusStartRequest,
    GoalEditRequest,
    GoalIncrementRequest,
    GoalProgressRequest,
    GoalRequest,
    GpuMonitorSettingsRequest,
    GpuSimulationRequest,
    KcetResultRequest,
    MemoryRequest,
    MobileDeviceUpdateRequest,
    MobilePairingClaimRequest,
    MobilePairingStartRequest,
    MobileRefreshRequest,
    MobileRemoteCommandRequest,
    MobileSyncRequest,
    NotificationActionRequest,
    NotificationRequest,
    PowerMonitorSettingsRequest,
    PowerSimulationRequest,
    ProjectGuardianProtectRequest,
    ProjectGuardianSnapshotRequest,
    ProjectGuardianRestoreRequest,
    RecoveryCrashRequest,
    RecoverySessionRequest,
    RecoverySimulationRequest,
    ResourceManagerSettingsRequest,
    ScreenshotActionRequest,
    ScreenshotRecordRequest,
    ScreenshotSearchRequest,
    ScreenshotSettingsRequest,
    SelfHealthOptimizeRequest,
    StudyChapterProgressRequest,
    StudyChapterRequest,
    StudyGoalRequest,
    StudyGoalUpdateRequest,
    StudyPlanRequest,
    StudyProgressRequest,
    StudySessionRequest,
    StudySubjectRequest,
    SystemAlertSettingsRequest,
    TimelineEventRequest,
    TimelineSearchRequest,
    VoiceCommandRequest,
    VoiceSettingsRequest,
    VoiceWakeRequest,
    WebsiteActionRequest,
    WebsiteAnalyzeRequest,
    WebsiteCredentialRequest,
    WebsiteImportRequest,
    WebsiteMonitoringRequest,
    WebsiteOpenRequest,
    WebsiteProfileRequest,
)
from backend.automation import AutomationEngine
from backend.core.task_manager import TaskManager
from backend.database.models import Automation, AutomationAction, AutomationCondition, AutomationTrigger, Notification, Task, TaskStatus
from backend.database.session import get_db
from backend.services.battery_alert import battery_alert_service
from backend.services.gpu_monitor import gpu_monitor_service
from backend.services.alert_framework import AlertService
from backend.services.download_monitor import download_monitoring_service
from backend.services.power_monitor import power_monitor_service
from backend.services.resource_manager import resource_manager_service
from backend.services.system_alerts import system_alert_service
from backend.services.evolution import evolution_service
from backend.services.voice_assistant import voice_assistant_service
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
        "power_monitor": power_monitor_service.get_status(),
        "voice_assistant": voice_assistant_service.get_status(),
        "download_monitor": download_monitoring_service.get_status(),
        "resource_manager": resource_manager_service.get_status(),
        "daily_briefing": evolution_service.latest_briefing(db),
        "briefing_recommendations": evolution_service.briefing_recommendations(db, status="open", limit=5),
        "gpu_monitor": gpu_status,
        "tasks": [serialize_task(task) for task in tasks],
        "automations": AutomationEngine(db).list(),
        "notifications": [AlertService(db).serialize(item) for item in notifications],
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


@router.get("/power-monitor/settings")
def power_monitor_settings(db: Session = Depends(get_db)) -> dict:
    return power_monitor_service.get_settings(db).__dict__


@router.put("/power-monitor/settings")
def update_power_monitor_settings(request: PowerMonitorSettingsRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return power_monitor_service.update_settings(request.model_dump(exclude_unset=True), db)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/power-monitor/status")
def power_monitor_status() -> dict:
    return power_monitor_service.get_status()


@router.get("/power-monitor/history")
def power_monitor_history(q: str | None = Query(default=None), event_type: str | None = Query(default=None), limit: int = Query(default=100, ge=1, le=1000)) -> dict:
    return power_monitor_service.history(limit=limit, query=q, event_type=event_type)


@router.get("/power-monitor/export")
def power_monitor_export() -> dict:
    return power_monitor_service.export()


@router.get("/power-monitor/recommendations")
def power_monitor_recommendations() -> list[dict]:
    return power_monitor_service.recommendations()


@router.post("/power-monitor/test/simulate")
def simulate_power_monitor(request: PowerSimulationRequest) -> dict:
    try:
        return power_monitor_service.simulate(request.battery_percent, request.is_charging)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/power-monitor/test/clear")
def clear_power_monitor_simulation() -> dict:
    return power_monitor_service.clear_simulation()


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


@router.get("/system-alerts/settings")
def system_alert_settings(db: Session = Depends(get_db)) -> dict:
    return system_alert_service.get_settings(db).__dict__


@router.put("/system-alerts/settings")
def update_system_alert_settings(request: SystemAlertSettingsRequest, db: Session = Depends(get_db)) -> dict:
    return system_alert_service.update_settings(request.model_dump(exclude_unset=True), db)


@router.post("/system-alerts/evaluate")
def evaluate_system_alerts() -> list[dict]:
    return system_alert_service.evaluate_once()


@router.get("/resource-manager/status")
def resource_manager_status() -> dict:
    return resource_manager_service.get_status()


@router.get("/resource-manager/settings")
def resource_manager_settings(db: Session = Depends(get_db)) -> dict:
    return resource_manager_service.get_settings(db).__dict__


@router.put("/resource-manager/settings")
def update_resource_manager_settings(request: ResourceManagerSettingsRequest, db: Session = Depends(get_db)) -> dict:
    return resource_manager_service.update_settings(request.model_dump(exclude_unset=True), db)


@router.post("/resource-manager/evaluate")
def evaluate_resource_manager() -> dict:
    return resource_manager_service.evaluate_once()


@router.get("/coding/report")
def coding_report(db: Session = Depends(get_db)) -> dict:
    return CodingAgent(db).daily_report()


@router.get("/coding/weekly-report")
def weekly_coding_report(db: Session = Depends(get_db)) -> dict:
    return CodingAgent(db).weekly_report()


@router.post("/coding/snapshot")
def coding_snapshot(db: Session = Depends(get_db)) -> dict:
    return CodingAgent(db).snapshot()


@router.post("/coding/activity")
def record_coding_activity(request: CodingActivityRequest, db: Session = Depends(get_db)) -> dict:
    return CodingAgent(db).record_activity(request.model_dump())


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


@router.get("/automations/dashboard")
def automations_dashboard(db: Session = Depends(get_db)) -> dict:
    return AutomationEngine(db).dashboard()


@router.get("/automations/history")
def automation_history(limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db)) -> list[dict]:
    return AutomationEngine(db).history(limit)


@router.get("/automations/templates")
def automation_templates(db: Session = Depends(get_db)) -> list[dict]:
    return AutomationEngine(db).templates()


@router.get("/automations/analytics")
def automation_analytics(db: Session = Depends(get_db)) -> dict:
    return AutomationEngine(db).analytics()


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
    return NotificationAgent(db).notify(
        request.title,
        request.message,
        alert_type=request.alert_type,
        module=request.module,
        severity=request.severity,
        priority=request.priority,
        category=request.category,
        suggested_action=request.suggested_action,
        action_buttons=request.action_buttons,
    )


@router.get("/notifications")
def list_notifications(
    q: str | None = Query(default=None),
    alert_type: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    unread_only: bool = False,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[dict]:
    return AlertService().list(limit=limit, query=q, alert_type=alert_type, severity=severity, unread_only=unread_only)


@router.get("/notifications/stats")
def notification_stats() -> dict:
    return AlertService().stats()


@router.get("/notifications/export")
def export_notifications() -> dict:
    return AlertService().export()


@router.put("/notifications/{notification_id}/read")
def mark_notification_read(notification_id: int, read: bool = True) -> dict:
    try:
        return AlertService().mark_read(notification_id, read)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/notifications/{notification_id}/actions")
def record_notification_action(notification_id: int, request: NotificationActionRequest) -> dict:
    try:
        return AlertService().record_action(notification_id, request.action, request.payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/notifications/{notification_id}")
def delete_notification(notification_id: int) -> dict:
    try:
        return AlertService().delete(notification_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/alert-settings")
def alert_settings(db: Session = Depends(get_db)) -> dict:
    return AlertService(db).get_settings(db)


@router.put("/alert-settings")
def update_alert_settings(request: AlertSettingsRequest, db: Session = Depends(get_db)) -> dict:
    return AlertService(db).update_settings(request.model_dump(exclude_unset=True), db)


@router.get("/voice/settings")
def voice_settings(db: Session = Depends(get_db)) -> dict:
    return voice_assistant_service.get_settings(db).__dict__


@router.put("/voice/settings")
def update_voice_settings(request: VoiceSettingsRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return voice_assistant_service.update_settings(request.model_dump(exclude_unset=True), db)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/voice/status")
def voice_status() -> dict:
    return voice_assistant_service.get_status()


@router.get("/voice/dashboard")
def voice_dashboard() -> dict:
    return voice_assistant_service.dashboard()


@router.get("/voice/profiles")
def voice_profiles() -> list[dict]:
    return voice_assistant_service.profiles()


@router.post("/voice/custom-personalities")
def create_custom_personality(request: CustomPersonalityRequest) -> dict:
    return voice_assistant_service.create_custom_personality(request.model_dump())


@router.put("/voice/custom-personalities/{personality_id}")
def update_custom_personality(personality_id: int, request: CustomPersonalityUpdateRequest) -> dict:
    try:
        return voice_assistant_service.update_custom_personality(personality_id, request.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/voice/custom-personalities/{personality_id}")
def delete_custom_personality(personality_id: int) -> dict:
    try:
        return voice_assistant_service.delete_custom_personality(personality_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/voice/wake")
def voice_wake(request: VoiceWakeRequest) -> dict:
    return voice_assistant_service.wake(request.phrase, request.source)


@router.post("/voice/command")
def voice_command(request: VoiceCommandRequest) -> dict:
    try:
        return voice_assistant_service.process_command(request.command, request.source)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/voice/pause")
def pause_voice() -> dict:
    return voice_assistant_service.pause()


@router.post("/voice/resume")
def resume_voice() -> dict:
    return voice_assistant_service.resume()


@router.get("/voice/interactions")
def voice_interactions(limit: int = Query(default=100, ge=1, le=1000)) -> list[dict]:
    return voice_assistant_service.interactions(limit)


@router.get("/evolution/overview")
def evolution_overview(db: Session = Depends(get_db)) -> dict:
    return evolution_service.overview(db)


@router.post("/evolution/copilot/evaluate")
def evaluate_copilot(db: Session = Depends(get_db)) -> list[dict]:
    return evolution_service.generate_copilot_suggestions(db)


@router.get("/evolution/copilot/dashboard")
def copilot_dashboard(db: Session = Depends(get_db)) -> dict:
    return evolution_service.copilot_dashboard(db)


@router.post("/evolution/copilot/context")
def copilot_context(db: Session = Depends(get_db)) -> dict:
    return evolution_service.create_context_snapshot(db)


@router.get("/evolution/copilot/suggestions")
def copilot_suggestions(limit: int = Query(default=50, ge=1, le=500), db: Session = Depends(get_db)) -> list[dict]:
    return evolution_service.list_copilot_suggestions(db, limit)


@router.put("/evolution/copilot/suggestions/{suggestion_id}")
def update_copilot_suggestion(suggestion_id: int, request: CopilotSuggestionStatusRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.update_suggestion_status(db, suggestion_id, request.status)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/evolution/copilot/suggestions/{suggestion_id}/actions")
def execute_copilot_action(suggestion_id: int, request: CopilotActionRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.execute_copilot_action(db, suggestion_id, request.action_type)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/evolution/copilot/settings")
def copilot_settings(db: Session = Depends(get_db)) -> dict:
    return evolution_service.get_copilot_settings(db)


@router.put("/evolution/copilot/settings")
def update_copilot_settings(request: CopilotSettingsRequest, db: Session = Depends(get_db)) -> dict:
    return evolution_service.update_copilot_settings(db, request.model_dump(exclude_unset=True))


@router.get("/evolution/copilot/insights")
def copilot_insights(db: Session = Depends(get_db)) -> list[dict]:
    return evolution_service.copilot_dashboard(db)["insights"]


@router.get("/evolution/copilot/warnings")
def copilot_warnings(db: Session = Depends(get_db)) -> list[dict]:
    return evolution_service.copilot_dashboard(db)["warnings"]


@router.get("/evolution/copilot/history")
def copilot_history(db: Session = Depends(get_db)) -> list[dict]:
    return evolution_service.copilot_dashboard(db)["history"]


@router.get("/evolution/copilot/analytics")
def copilot_analytics(db: Session = Depends(get_db)) -> list[dict]:
    return evolution_service.copilot_dashboard(db)["analytics"]


@router.post("/evolution/daily-briefing")
def generate_daily_briefing(request: DailyBriefingRequest, db: Session = Depends(get_db)) -> dict:
    return evolution_service.generate_daily_briefing(db, speak=request.speak, notify=request.notify)


@router.get("/evolution/daily-briefing/latest")
def latest_daily_briefing(db: Session = Depends(get_db)) -> dict | None:
    return evolution_service.latest_briefing(db)


@router.get("/evolution/daily-briefing/history")
def daily_briefing_history(limit: int = Query(default=30, ge=1, le=365), db: Session = Depends(get_db)) -> list[dict]:
    return evolution_service.briefing_history(db, limit)


@router.get("/evolution/daily-briefing/recommendations")
def daily_briefing_recommendations(status: str | None = Query(default=None), limit: int = Query(default=50, ge=1, le=500), db: Session = Depends(get_db)) -> list[dict]:
    return evolution_service.briefing_recommendations(db, status, limit)


@router.get("/evolution/daily-briefing/analytics")
def daily_briefing_analytics(limit: int = Query(default=30, ge=1, le=365), db: Session = Depends(get_db)) -> list[dict]:
    return evolution_service.briefing_analytics(db, limit)


@router.get("/evolution/daily-briefing/settings")
def daily_briefing_settings(db: Session = Depends(get_db)) -> dict:
    return evolution_service.get_briefing_settings(db)


@router.put("/evolution/daily-briefing/settings")
def update_daily_briefing_settings(request: DailyBriefingSettingsRequest, db: Session = Depends(get_db)) -> dict:
    return evolution_service.update_briefing_settings(db, request.model_dump(exclude_unset=True))


@router.post("/evolution/focus/start")
def start_focus(request: FocusStartRequest, db: Session = Depends(get_db)) -> dict:
    return evolution_service.start_focus(
        db,
        request.title,
        request.duration_minutes,
        request.break_minutes,
        request.mode,
        request.session_type,
        request.subject,
        request.chapter,
        request.topic,
        request.current_goal,
        request.pomodoro_preset,
        request.blocked_websites,
        request.blocked_apps,
        request.mute_notifications,
        request.allow_critical_notifications,
        request.long_break_minutes,
        request.cycles_before_long_break,
    )


@router.post("/evolution/focus/end")
def end_focus(request: FocusEndRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.end_focus(db, request.session_id, request.tasks_completed, request.distraction_count, request.goal_completion_percent)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/evolution/focus/sessions")
def focus_sessions(limit: int = Query(default=50, ge=1, le=500), db: Session = Depends(get_db)) -> list[dict]:
    return evolution_service.list_focus_sessions(db, limit)


@router.get("/evolution/focus/status")
def focus_status(db: Session = Depends(get_db)) -> dict:
    return evolution_service.focus_status(db)


@router.get("/evolution/focus/dashboard")
def focus_dashboard(db: Session = Depends(get_db)) -> dict:
    return evolution_service.focus_dashboard(db)


@router.post("/evolution/focus/pause")
def pause_focus(request: FocusControlRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.pause_focus(db, request.session_id, request.reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/evolution/focus/resume")
def resume_focus(request: FocusControlRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.resume_focus(db, request.session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/evolution/focus/extend")
def extend_focus(request: FocusControlRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.extend_focus(db, request.minutes, request.session_id, request.reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/evolution/focus/break")
def start_focus_break(request: FocusControlRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.start_focus_break(db, request.minutes, request.session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/evolution/focus/distraction-check")
def focus_distraction_check(request: FocusDistractionRequest, db: Session = Depends(get_db)) -> dict:
    return evolution_service.check_focus_distraction(db, request.url, request.app_name)


@router.post("/evolution/focus/goals")
def create_focus_goal(request: FocusGoalRequest, db: Session = Depends(get_db)) -> dict:
    return evolution_service.create_focus_goal(db, request.title, request.goal_type, request.target_minutes, request.session_id)


@router.put("/evolution/focus/goals/{goal_id}")
def update_focus_goal(goal_id: int, request: FocusGoalProgressRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.update_focus_goal(db, goal_id, request.completed_minutes, request.status)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/evolution/study/plans")
def create_study_plan(request: StudyPlanRequest, db: Session = Depends(get_db)) -> dict:
    return evolution_service.create_study_plan(
        db,
        request.title,
        request.exam_date,
        request.topics,
        request.subject_name,
        request.priority,
        request.difficulty,
        request.target_score,
        request.availability_minutes_per_day,
    )


@router.get("/evolution/study/plans")
def list_study_plans(db: Session = Depends(get_db)) -> list[dict]:
    return evolution_service.list_study_plans(db)


@router.get("/evolution/study/dashboard")
def study_dashboard(db: Session = Depends(get_db)) -> dict:
    return evolution_service.study_dashboard(db)


@router.get("/evolution/study/recommendations")
def study_recommendations(db: Session = Depends(get_db)) -> list[dict]:
    return evolution_service.study_recommendations(db)


@router.post("/evolution/study/subjects")
def create_study_subject(request: StudySubjectRequest, db: Session = Depends(get_db)) -> dict:
    return evolution_service.create_study_subject(db, request.name, request.priority, request.difficulty, request.exam_date, request.target_score)


@router.post("/evolution/study/chapters")
def create_study_chapter(request: StudyChapterRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.add_study_chapter(db, request.subject_id, request.title, request.unit, request.topics, request.priority, request.difficulty)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/evolution/study/chapters/{chapter_id}/progress")
def update_study_chapter_progress(chapter_id: int, request: StudyChapterProgressRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.update_study_chapter_progress(db, chapter_id, request.completion_percent, request.status, request.notes)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/evolution/study/plans/{plan_id}/progress")
def update_study_progress(plan_id: int, request: StudyProgressRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.update_study_progress(db, plan_id, request.topic, request.progress_percent, request.status, request.notes)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/evolution/study/plans/{plan_id}/reminder")
def schedule_study_reminder(plan_id: int, topic: str | None = None, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.schedule_study_reminder(db, plan_id, topic)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/evolution/study/sessions")
def record_study_session(request: StudySessionRequest, db: Session = Depends(get_db)) -> dict:
    return evolution_service.record_study_session(
        db,
        request.subject_id,
        request.subject_name,
        request.chapter_id,
        request.chapter_title,
        request.topic,
        request.duration_minutes,
        request.session_type,
        request.notes,
    )


@router.post("/evolution/study/goals")
def create_study_goal(request: StudyGoalRequest, db: Session = Depends(get_db)) -> dict:
    return evolution_service.create_study_goal(db, request.title, request.target_value, request.unit, request.subject_id, request.deadline)


@router.put("/evolution/study/goals/{goal_id}")
def update_study_goal(goal_id: int, request: StudyGoalUpdateRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.update_study_goal(db, goal_id, request.current_value)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/evolution/timeline")
def add_timeline_event(request: TimelineEventRequest, db: Session = Depends(get_db)) -> dict:
    return evolution_service.add_timeline_event(db, request.event_type, request.title, request.description, request.source, request.duration_seconds, request.metadata)


@router.get("/evolution/timeline")
def search_timeline(
    q: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[dict]:
    return evolution_service.search_timeline(db, q, event_type, limit, start_date, end_date)


@router.get("/evolution/timeline/dashboard")
def timeline_dashboard(
    view: str = Query(default="today"),
    event_type: str | None = Query(default=None),
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    return evolution_service.timeline_dashboard(db, view, event_type, q)


@router.get("/evolution/timeline/summary")
def timeline_summary(period: str = Query(default="day"), reference_date: str | None = Query(default=None), db: Session = Depends(get_db)) -> dict:
    return evolution_service.timeline_summary(db, period, reference_date)


@router.post("/evolution/timeline/search")
def natural_timeline_search(request: TimelineSearchRequest, db: Session = Depends(get_db)) -> dict:
    return evolution_service.natural_memory_search(db, request.query, request.limit)


@router.post("/evolution/project-guardian/snapshot")
def project_guardian_snapshot(request: ProjectGuardianSnapshotRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.project_guardian_snapshot(db, request.project_path, request.action)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/evolution/project-guardian/dashboard")
def project_guardian_dashboard(project_path: str | None = Query(default=None), db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.project_guardian_dashboard(db, project_path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/evolution/project-guardian/git-status")
def project_guardian_git_status(project_path: str = Query(min_length=1)) -> dict:
    try:
        return evolution_service.git_status(project_path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/evolution/project-guardian/protect")
def project_guardian_protect(request: ProjectGuardianProtectRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.protect_project_operation(db, request.project_path, request.operation, request.reason)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/evolution/project-guardian/projects/{project_id}/health")
def project_guardian_health(project_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.evaluate_project_health(db, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/evolution/project-guardian/restore")
def project_guardian_restore(request: ProjectGuardianRestoreRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.restore_project_backup(db, request.backup_id, request.restore_path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/evolution/recovery/dashboard")
def emergency_recovery_dashboard(db: Session = Depends(get_db)) -> dict:
    return evolution_service.recovery_dashboard(db)


@router.post("/evolution/recovery/crash-reports")
def record_recovery_crash_report(request: RecoveryCrashRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.record_crash_report(db, request.crash_type, request.source, request.application, request.message, request.severity, request.stack_trace, request.diagnostics, request.project_path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/evolution/recovery/sessions")
def capture_recovery_session(request: RecoverySessionRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.capture_recovery_session(db, request.session_type, request.applications, request.project_path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/evolution/recovery/sessions/{session_id}/restore")
def restore_recovery_session(session_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.restore_recovery_session(db, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/evolution/recovery/simulate")
def simulate_recovery_event(request: RecoverySimulationRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.simulate_recovery_event(db, request.event_type, request.application, request.project_path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/evolution/downloads/scan")
def scan_downloads(request: DownloadsScanRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.scan_downloads(db, request.folder, request.large_file_mb)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/evolution/downloads/organize")
def organize_downloads(request: DownloadsOrganizeRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.organize_downloads(db, request.folder, request.dry_run)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/evolution/downloads/dashboard")
def download_manager_dashboard(folder: str | None = None, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.download_dashboard(db, folder)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/evolution/downloads/monitor/status")
def download_monitor_status() -> dict:
    return download_monitoring_service.get_status()


@router.post("/evolution/downloads/search")
def search_downloads(request: DownloadsSearchRequest, db: Session = Depends(get_db)) -> dict:
    return evolution_service.search_downloads(db, request.query, request.limit)


@router.get("/evolution/downloads/analytics")
def download_analytics(days: int = Query(default=30, ge=1, le=365), db: Session = Depends(get_db)) -> dict:
    return evolution_service.download_analytics(db, days)


@router.get("/evolution/downloads/duplicates")
def duplicate_downloads(limit: int = Query(default=100, ge=1, le=1000), db: Session = Depends(get_db)) -> list[dict]:
    return evolution_service.list_duplicate_files(db, limit)


@router.get("/evolution/downloads/large-files")
def large_downloads(limit: int = Query(default=100, ge=1, le=1000), db: Session = Depends(get_db)) -> list[dict]:
    downloads = evolution_service.list_downloads(db, limit=1000)
    return [item for item in downloads if item["size_bytes"] >= 100 * 1024 * 1024][:limit]


@router.get("/evolution/downloads/rules")
def list_download_rules(db: Session = Depends(get_db)) -> list[dict]:
    return evolution_service.list_download_rules(db)


@router.post("/evolution/downloads/rules")
def create_download_rule(request: DownloadRuleRequest, db: Session = Depends(get_db)) -> dict:
    return evolution_service.create_download_rule(db, request.name, request.pattern, request.category, request.destination, request.match_type, request.enabled, request.priority)


@router.get("/evolution/downloads/cleanup-suggestions")
def download_cleanup_suggestions(limit: int = Query(default=100, ge=1, le=1000), db: Session = Depends(get_db)) -> list[dict]:
    return evolution_service.cleanup_suggestions(db, limit)


@router.get("/evolution/downloads")
def list_downloads(limit: int = Query(default=100, ge=1, le=1000), db: Session = Depends(get_db)) -> list[dict]:
    return evolution_service.list_downloads(db, limit)


@router.post("/evolution/screenshots")
def record_screenshot(request: ScreenshotRecordRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.record_screenshot(db, request.file_path, request.source, request.extracted_text, request.analysis, request.capture_mode, request.language)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/evolution/screenshots/dashboard")
def screenshot_dashboard(db: Session = Depends(get_db)) -> dict:
    return evolution_service.screenshot_dashboard(db)


@router.post("/evolution/screenshots/search")
def search_screenshots(request: ScreenshotSearchRequest, db: Session = Depends(get_db)) -> dict:
    return evolution_service.search_screenshots(db, request.query, request.limit)


@router.post("/evolution/screenshots/{screenshot_id}/actions")
def screenshot_action(screenshot_id: int, request: ScreenshotActionRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.record_screenshot_action(db, screenshot_id, request.action_type, request.payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/evolution/screenshots/settings")
def screenshot_settings(db: Session = Depends(get_db)) -> dict:
    return evolution_service.get_screenshot_settings(db)


@router.put("/evolution/screenshots/settings")
def update_screenshot_settings(request: ScreenshotSettingsRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.update_screenshot_settings(db, request.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/evolution/screenshots")
def list_screenshots(limit: int = Query(default=50, ge=1, le=500), db: Session = Depends(get_db)) -> list[dict]:
    return evolution_service.list_screenshots(db, limit)


@router.post("/evolution/automation-builder")
def build_automation(request: AutomationBuilderRequest, db: Session = Depends(get_db)) -> dict:
    return evolution_service.build_automation(db, request.prompt)


@router.post("/evolution/goals")
def create_goal(request: GoalRequest, db: Session = Depends(get_db)) -> dict:
    return evolution_service.create_goal(db, request.title, request.target_value, request.unit, request.goal_type, request.period, request.description, request.deadline, request.priority, request.category, request.reminder_settings)


@router.get("/evolution/goals")
def list_goals(db: Session = Depends(get_db)) -> list[dict]:
    return evolution_service.list_goals(db)


@router.get("/evolution/goals/stats")
def goal_stats(db: Session = Depends(get_db)) -> dict:
    return evolution_service.goal_stats(db)


@router.get("/evolution/goals/dashboard")
def goal_dashboard(db: Session = Depends(get_db)) -> dict:
    return evolution_service.goal_dashboard(db)


@router.get("/evolution/goals/history")
def goal_history(limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db)) -> list[dict]:
    return evolution_service.goal_history(db, limit)


@router.get("/evolution/goals/analytics")
def goal_analytics(db: Session = Depends(get_db)) -> dict:
    return evolution_service.goal_analytics(db)


@router.post("/evolution/goals/auto-track")
def goal_auto_track(db: Session = Depends(get_db)) -> dict:
    return evolution_service.refresh_goal_auto_tracking(db)


@router.put("/evolution/goals/{goal_id}")
def update_goal(goal_id: int, request: GoalProgressRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.update_goal(db, goal_id, request.current_value, request.source, request.note)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/evolution/goals/{goal_id}")
def edit_goal(goal_id: int, request: GoalEditRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.edit_goal(db, goal_id, request.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/evolution/goals/{goal_id}/increment")
def increment_goal(goal_id: int, request: GoalIncrementRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.increment_goal_progress(db, goal_id, request.delta_value, request.source, request.note)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/evolution/goals/{goal_id}")
def delete_goal(goal_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.delete_goal(db, goal_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/evolution/achievements")
def list_achievements(db: Session = Depends(get_db)) -> list[dict]:
    return evolution_service.list_achievements(db)


@router.post("/evolution/achievements/evaluate")
def evaluate_achievements(db: Session = Depends(get_db)) -> list[dict]:
    return evolution_service.evaluate_achievements(db)


@router.post("/evolution/college/check")
def check_college_updates(request: CollegeCheckRequest, db: Session = Depends(get_db)) -> dict:
    return evolution_service.check_college_updates(db, request.source)


@router.get("/evolution/college/dashboard")
def college_dashboard(db: Session = Depends(get_db)) -> dict:
    return evolution_service.college_dashboard(db)


@router.post("/evolution/college/profiles")
def create_college_profile(request: CollegeProfileRequest, db: Session = Depends(get_db)) -> dict:
    return evolution_service.create_college_profile(db, request.name, request.portal_type, request.website_profile_id, request.target_attendance_percent)


@router.get("/evolution/college/updates")
def list_college_updates(limit: int = Query(default=50, ge=1, le=500), db: Session = Depends(get_db)) -> list[dict]:
    return evolution_service.list_college_updates(db, limit)


@router.get("/evolution/college/{section}")
def college_section(section: str, db: Session = Depends(get_db)) -> list[dict]:
    dashboard = evolution_service.college_dashboard(db)
    aliases = {
        "attendance": "attendance",
        "marks": "marks",
        "results": "results",
        "assignments": "assignments",
        "fees": "fees",
        "timetable": "timetables",
        "announcements": "announcements",
        "kcet": "kcet",
    }
    key = aliases.get(section)
    if not key:
        raise HTTPException(status_code=404, detail="College section not found")
    return dashboard.get(key, [])


@router.get("/evolution/self-health")
def self_health(db: Session = Depends(get_db)) -> dict:
    return evolution_service.self_health(db)


@router.post("/evolution/self-health/optimize")
def optimize_self_health(request: SelfHealthOptimizeRequest, db: Session = Depends(get_db)) -> dict:
    return evolution_service.optimize_self_health(db, request.action)


@router.get("/mobile/summary")
def mobile_summary(db: Session = Depends(get_db)) -> dict:
    return evolution_service.mobile_summary(db)


@router.get("/mobile/docs")
def mobile_docs() -> dict:
    return evolution_service.mobile_api_docs()


def _mobile_device(request: Request, db: Session):
    try:
        return evolution_service.mobile_authenticate(
            db,
            request.headers.get("authorization", ""),
            request.client.host if request.client else "",
            request.headers.get("user-agent", ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/mobile/pairing/start")
def mobile_pairing_start(request: MobilePairingStartRequest, db: Session = Depends(get_db)) -> dict:
    return evolution_service.mobile_pairing_start(db, request.device_name, request.permissions)


@router.post("/mobile/pairing/claim")
def mobile_pairing_claim(request: Request, body: MobilePairingClaimRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.mobile_pairing_claim(
            db,
            body.pairing_code,
            body.pairing_token,
            body.device_name,
            body.device_type,
            body.device_fingerprint,
            request.client.host if request.client else "",
            request.headers.get("user-agent", ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/mobile/auth/refresh")
def mobile_auth_refresh(request: Request, body: MobileRefreshRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.mobile_refresh(db, body.refresh_token, request.client.host if request.client else "")
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/mobile/dashboard")
def mobile_dashboard(db: Session = Depends(get_db)) -> dict:
    return evolution_service.mobile_gateway_dashboard(db)


@router.get("/mobile/devices")
def mobile_devices(db: Session = Depends(get_db)) -> list[dict]:
    return evolution_service.mobile_devices(db)


@router.patch("/mobile/devices/{device_id}")
def mobile_update_device(device_id: int, request: MobileDeviceUpdateRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.mobile_update_device(db, device_id, request.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/mobile/devices/{device_id}")
def mobile_revoke_device(device_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return evolution_service.mobile_revoke_device(db, device_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/mobile/battery/status")
def mobile_battery_status(request: Request, db: Session = Depends(get_db)) -> dict:
    _mobile_device(request, db)
    return power_monitor_service.get_status()


@router.get("/mobile/battery/events")
def mobile_battery_events(request: Request, db: Session = Depends(get_db)) -> list[dict]:
    _mobile_device(request, db)
    return power_monitor_service.history(limit=100)["events"]


@router.get("/mobile/battery/history")
def mobile_battery_history(request: Request, db: Session = Depends(get_db)) -> dict:
    _mobile_device(request, db)
    return power_monitor_service.history(limit=100)


@router.get("/mobile/tasks")
def mobile_tasks(request: Request, db: Session = Depends(get_db)) -> list[dict]:
    _mobile_device(request, db)
    return [serialize_task(task) for task in db.query(Task).order_by(Task.created_at.desc()).limit(100).all()]


@router.post("/mobile/tasks")
def mobile_create_task(request: Request, body: CommandRequest, db: Session = Depends(get_db)) -> dict:
    device = _mobile_device(request, db)
    task = Task(command=body.command, intent="mobile_task", agent="mobile_companion", status=TaskStatus.created.value, plan_json=json.dumps({"device_id": device.id}), result_json="{}")
    db.add(task)
    db.commit()
    db.refresh(task)
    return serialize_task(task)


@router.patch("/mobile/tasks/{task_id}")
def mobile_update_task(task_id: int, request: Request, body: NotificationActionRequest, db: Session = Depends(get_db)) -> dict:
    _mobile_device(request, db)
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if body.action == "complete":
        task.status = TaskStatus.completed.value
    elif body.action == "cancel":
        task.status = TaskStatus.cancelled.value
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return serialize_task(task)


@router.delete("/mobile/tasks/{task_id}")
def mobile_delete_task(task_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    _mobile_device(request, db)
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = TaskStatus.cancelled.value
    db.commit()
    return {"status": "cancelled", "task_id": task_id}


@router.get("/mobile/notifications")
def mobile_notifications(request: Request, db: Session = Depends(get_db)) -> list[dict]:
    _mobile_device(request, db)
    rows = db.query(Notification).order_by(Notification.created_at.desc()).limit(100).all()
    return [{"id": row.id, "title": row.title, "message": row.message, "alert_type": row.alert_type, "module": row.module, "severity": row.severity, "read": row.read, "created_at": row.created_at.isoformat()} for row in rows]


@router.patch("/mobile/notifications/{notification_id}")
def mobile_mark_notification(notification_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    _mobile_device(request, db)
    row = db.get(Notification, notification_id)
    if not row:
        raise HTTPException(status_code=404, detail="Notification not found")
    row.read = True
    db.commit()
    return {"status": "read", "notification_id": notification_id}


@router.delete("/mobile/notifications/{notification_id}")
def mobile_delete_notification(notification_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    _mobile_device(request, db)
    row = db.get(Notification, notification_id)
    if not row:
        raise HTTPException(status_code=404, detail="Notification not found")
    db.delete(row)
    db.commit()
    return {"status": "deleted", "notification_id": notification_id}


@router.get("/mobile/notifications/alert-history")
def mobile_alert_history(request: Request, db: Session = Depends(get_db)) -> list[dict]:
    _mobile_device(request, db)
    return AlertService(db).list(limit=200)


@router.get("/mobile/notifications/settings")
def mobile_notification_settings(request: Request, db: Session = Depends(get_db)) -> dict:
    _mobile_device(request, db)
    return AlertService(db).get_settings(db)


@router.get("/mobile/notification-queue")
def mobile_notification_queue(request: Request, status: str | None = Query(default=None), db: Session = Depends(get_db)) -> list[dict]:
    device = _mobile_device(request, db)
    return evolution_service.mobile_notification_queue(db, device, status)


@router.get("/mobile/automations")
def mobile_automations(request: Request, db: Session = Depends(get_db)) -> list[dict]:
    _mobile_device(request, db)
    return AutomationEngine(db).list()


@router.post("/mobile/automations")
def mobile_create_automation(request: Request, body: AutomationBuilderRequest, db: Session = Depends(get_db)) -> dict:
    _mobile_device(request, db)
    return evolution_service.build_automation(db, body.prompt)


@router.patch("/mobile/automations/{automation_id}")
def mobile_toggle_automation(automation_id: int, request: Request, body: AutomationToggleRequest, db: Session = Depends(get_db)) -> dict:
    _mobile_device(request, db)
    row = db.get(Automation, automation_id)
    if not row:
        raise HTTPException(status_code=404, detail="Automation not found")
    row.enabled = body.enabled
    db.commit()
    db.refresh(row)
    return AutomationEngine(db).serialize(row)


@router.get("/mobile/automations/history")
def mobile_automation_history(request: Request, db: Session = Depends(get_db)) -> list[dict]:
    _mobile_device(request, db)
    return AutomationEngine(db).history(100)


@router.delete("/mobile/automations/{automation_id}")
def mobile_delete_automation(automation_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    _mobile_device(request, db)
    row = db.get(Automation, automation_id)
    if not row:
        raise HTTPException(status_code=404, detail="Automation not found")
    db.query(AutomationTrigger).filter(AutomationTrigger.automation_id == automation_id).delete()
    db.query(AutomationCondition).filter(AutomationCondition.automation_id == automation_id).delete()
    db.query(AutomationAction).filter(AutomationAction.automation_id == automation_id).delete()
    db.delete(row)
    db.commit()
    return {"status": "deleted", "automation_id": automation_id}


@router.get("/mobile/goals")
def mobile_goals(request: Request, db: Session = Depends(get_db)) -> list[dict]:
    _mobile_device(request, db)
    return evolution_service.list_goals(db)


@router.post("/mobile/goals")
def mobile_create_goal(request: Request, body: GoalRequest, db: Session = Depends(get_db)) -> dict:
    _mobile_device(request, db)
    return evolution_service.create_goal(db, body.title, body.target_value, body.unit, body.goal_type, body.period, body.description, body.deadline, body.priority, body.category, body.reminder_settings)


@router.patch("/mobile/goals/{goal_id}")
def mobile_edit_goal(goal_id: int, request: Request, body: GoalEditRequest, db: Session = Depends(get_db)) -> dict:
    _mobile_device(request, db)
    try:
        return evolution_service.edit_goal(db, goal_id, body.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/mobile/goals/{goal_id}")
def mobile_delete_goal(goal_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    _mobile_device(request, db)
    try:
        return evolution_service.delete_goal(db, goal_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/mobile/goals/progress")
def mobile_goal_progress(request: Request, db: Session = Depends(get_db)) -> dict:
    _mobile_device(request, db)
    return evolution_service.goal_stats(db)


@router.get("/mobile/goals/achievements")
def mobile_goal_achievements(request: Request, db: Session = Depends(get_db)) -> list[dict]:
    _mobile_device(request, db)
    return evolution_service.list_achievements(db)


@router.get("/mobile/goals/streaks")
def mobile_goal_streaks(request: Request, db: Session = Depends(get_db)) -> list[dict]:
    _mobile_device(request, db)
    return evolution_service.goal_stats(db).get("streaks", [])


@router.get("/mobile/study/dashboard")
def mobile_study_dashboard(request: Request, db: Session = Depends(get_db)) -> dict:
    _mobile_device(request, db)
    return evolution_service.study_dashboard(db)


@router.get("/mobile/study/subjects")
def mobile_study_subjects(request: Request, db: Session = Depends(get_db)) -> list[dict]:
    _mobile_device(request, db)
    return evolution_service.study_dashboard(db)["subjects"]


@router.get("/mobile/study/plans")
def mobile_study_plans(request: Request, db: Session = Depends(get_db)) -> list[dict]:
    _mobile_device(request, db)
    return evolution_service.list_study_plans(db)


@router.get("/mobile/study/progress")
def mobile_study_progress(request: Request, db: Session = Depends(get_db)) -> dict:
    _mobile_device(request, db)
    dashboard = evolution_service.study_dashboard(db)
    return {"subjects": dashboard["subjects"], "analytics": dashboard["analytics"], "recommendations": dashboard["recommendations"]}


@router.get("/mobile/study/exam-countdown")
def mobile_study_exam_countdown(request: Request, db: Session = Depends(get_db)) -> list[dict]:
    _mobile_device(request, db)
    return evolution_service.study_dashboard(db)["exam_countdowns"]


@router.get("/mobile/study/revision-plans")
def mobile_study_revision_plans(request: Request, db: Session = Depends(get_db)) -> list[dict]:
    _mobile_device(request, db)
    return evolution_service.study_dashboard(db)["revision_plans"]


@router.get("/mobile/study/analytics")
def mobile_study_analytics(request: Request, db: Session = Depends(get_db)) -> list[dict]:
    _mobile_device(request, db)
    return evolution_service.study_dashboard(db)["analytics"]


@router.get("/mobile/college/dashboard")
def mobile_college_dashboard(request: Request, db: Session = Depends(get_db)) -> dict:
    _mobile_device(request, db)
    return evolution_service.college_dashboard(db)


@router.get("/mobile/college/updates")
def mobile_college_updates(request: Request, db: Session = Depends(get_db)) -> list[dict]:
    _mobile_device(request, db)
    return evolution_service.list_college_updates(db, 100)


@router.get("/mobile/college/{section}")
def mobile_college_section(section: str, request: Request, db: Session = Depends(get_db)) -> list[dict]:
    _mobile_device(request, db)
    dashboard = evolution_service.college_dashboard(db)
    aliases = {"attendance": "attendance", "marks": "marks", "results": "results", "assignments": "assignments", "fees": "fees", "timetable": "timetables", "announcements": "announcements", "kcet": "kcet"}
    key = aliases.get(section)
    if not key:
        raise HTTPException(status_code=404, detail="College mobile section not found")
    return dashboard.get(key, [])


@router.get("/mobile/timeline")
def mobile_timeline(request: Request, db: Session = Depends(get_db)) -> list[dict]:
    _mobile_device(request, db)
    return evolution_service.search_timeline(db, limit=100)


@router.post("/mobile/timeline/search")
def mobile_timeline_search(request: Request, body: TimelineSearchRequest, db: Session = Depends(get_db)) -> list[dict]:
    _mobile_device(request, db)
    return evolution_service.natural_memory_search(db, body.query, body.limit)["results"]


@router.get("/mobile/timeline/daily-summary")
def mobile_timeline_daily_summary(request: Request, db: Session = Depends(get_db)) -> dict:
    _mobile_device(request, db)
    return evolution_service.timeline_summary(db, "day")


@router.get("/mobile/timeline/weekly-summary")
def mobile_timeline_weekly_summary(request: Request, db: Session = Depends(get_db)) -> dict:
    _mobile_device(request, db)
    return evolution_service.timeline_summary(db, "week")


@router.get("/mobile/timeline/monthly-summary")
def mobile_timeline_monthly_summary(request: Request, db: Session = Depends(get_db)) -> dict:
    _mobile_device(request, db)
    return evolution_service.timeline_summary(db, "month")


@router.get("/mobile/health/status")
def mobile_health_status(request: Request, db: Session = Depends(get_db)) -> dict:
    _mobile_device(request, db)
    return evolution_service.self_health(db)


@router.get("/mobile/health/errors")
def mobile_health_errors(request: Request, db: Session = Depends(get_db)) -> dict:
    _mobile_device(request, db)
    return evolution_service.self_health(db)["error_monitor"]


@router.get("/mobile/health/logs")
def mobile_health_logs(request: Request, db: Session = Depends(get_db)) -> dict:
    _mobile_device(request, db)
    return evolution_service.self_health(db)["log_monitor"]


@router.get("/mobile/health/automation")
def mobile_health_automation(request: Request, db: Session = Depends(get_db)) -> dict:
    _mobile_device(request, db)
    return evolution_service.self_health(db)["automation_health"]


@router.get("/mobile/health/api")
def mobile_health_api(request: Request, db: Session = Depends(get_db)) -> dict:
    _mobile_device(request, db)
    return evolution_service.self_health(db)["api_health"]


@router.post("/mobile/commands")
def mobile_remote_command(request: Request, body: MobileRemoteCommandRequest, db: Session = Depends(get_db)) -> dict:
    device = _mobile_device(request, db)
    try:
        return evolution_service.mobile_remote_command(db, device, body.command, body.payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/mobile/sync")
def mobile_sync_queue(request: Request, status: str | None = Query(default=None), db: Session = Depends(get_db)) -> list[dict]:
    device = _mobile_device(request, db)
    return evolution_service.mobile_sync_queue(db, device, status)


@router.post("/mobile/sync")
def mobile_sync_enqueue(request: Request, body: MobileSyncRequest, db: Session = Depends(get_db)) -> dict:
    device = _mobile_device(request, db)
    return evolution_service.mobile_sync_enqueue(db, device, body.item_type, body.operation, body.payload, body.conflict_strategy)


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
