from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.session import Base


class TaskStatus(str, Enum):
    created = "created"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
    pending_confirmation = "pending_confirmation"


class ApprovalStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    edited = "edited"
    needs_clarification = "needs_clarification"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), default="Nexa User")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    command: Mapped[str] = mapped_column(Text)
    intent: Mapped[str] = mapped_column(String(80))
    agent: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40), default=TaskStatus.created.value)
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, default=False)
    plan_json: Mapped[str] = mapped_column(Text, default="{}")
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    executions: Mapped[list["TaskExecution"]] = relationship(back_populates="task")


class TaskExecution(Base):
    __tablename__ = "task_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    status: Mapped[str] = mapped_column(String(40))
    log: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    task: Mapped[Task] = relationship(back_populates="executions")


class TaskApproval(Base):
    __tablename__ = "task_approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    original_text: Mapped[str] = mapped_column(Text)
    corrected_text: Mapped[str] = mapped_column(Text)
    intent: Mapped[str] = mapped_column(String(120))
    task_type: Mapped[str] = mapped_column(String(80))
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(40), default=ApprovalStatus.pending.value)
    structured_task_json: Mapped[str] = mapped_column(Text, default="{}")
    plan_json: Mapped[str] = mapped_column(Text, default="{}")
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    high_risk: Mapped[bool] = mapped_column(Boolean, default=False)
    clarification_required: Mapped[bool] = mapped_column(Boolean, default=False)
    provider: Mapped[str] = mapped_column(String(80), default="local")
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ApprovalHistory(Base):
    __tablename__ = "approval_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    approval_id: Mapped[int] = mapped_column(ForeignKey("task_approvals.id"))
    action: Mapped[str] = mapped_column(String(80))
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AIInterpretation(Base):
    __tablename__ = "ai_interpretations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    approval_id: Mapped[int | None] = mapped_column(ForeignKey("task_approvals.id"), nullable=True)
    provider: Mapped[str] = mapped_column(String(80))
    original_text: Mapped[str] = mapped_column(Text)
    response_json: Mapped[str] = mapped_column(Text, default="{}")
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CorrectionHistory(Base):
    __tablename__ = "correction_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    original_text: Mapped[str] = mapped_column(Text)
    corrected_text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(80), default="approval")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WebsiteProfile(Base):
    __tablename__ = "website_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    url: Mapped[str] = mapped_column(Text)
    field_mapping_json: Mapped[str] = mapped_column(Text, default="{}")
    navigation_rules_json: Mapped[str] = mapped_column(Text, default="{}")
    login_process_json: Mapped[str] = mapped_column(Text, default="{}")
    retry_policy_json: Mapped[str] = mapped_column(Text, default='{"max_retries": 5, "retry_interval_seconds": 5}')
    success_check_json: Mapped[str] = mapped_column(Text, default="{}")
    monitoring_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    monitoring_interval_seconds: Mapped[int] = mapped_column(Integer, default=300)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WebsiteCredential(Base):
    __tablename__ = "website_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("website_profiles.id"), index=True)
    label: Mapped[str] = mapped_column(String(120), default="default")
    encrypted_payload: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WebsiteAction(Base):
    __tablename__ = "website_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("website_profiles.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    action_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WebsiteSession(Base):
    __tablename__ = "website_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("website_profiles.id"), index=True)
    status: Mapped[str] = mapped_column(String(80))
    encrypted_cookies: Mapped[str] = mapped_column(Text, default="")
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WebsiteHistory(Base):
    __tablename__ = "website_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("website_profiles.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(100))
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WebsiteMonitoring(Base):
    __tablename__ = "website_monitoring"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("website_profiles.id"), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    interval_seconds: Mapped[int] = mapped_column(Integer, default=300)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_available_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WebsiteRetryRule(Base):
    __tablename__ = "website_retry_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("website_profiles.id"), index=True)
    max_retries: Mapped[int] = mapped_column(Integer, default=5)
    base_delay_seconds: Mapped[int] = mapped_column(Integer, default=5)
    backoff_multiplier: Mapped[int] = mapped_column(Integer, default=2)
    retry_conditions_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WebsiteLearning(Base):
    __tablename__ = "website_learning"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("website_profiles.id"), nullable=True, index=True)
    website_name: Mapped[str] = mapped_column(String(160), default="")
    learned_key: Mapped[str] = mapped_column(String(160))
    learned_value_json: Mapped[str] = mapped_column(Text, default="{}")
    confidence: Mapped[int] = mapped_column(Integer, default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(80))
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Automation(Base):
    __tablename__ = "automations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    condition_json: Mapped[str] = mapped_column(Text)
    action_json: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AutomationTrigger(Base):
    __tablename__ = "automation_triggers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    automation_id: Mapped[int] = mapped_column(ForeignKey("automations.id"), index=True)
    trigger_type: Mapped[str] = mapped_column(String(100), index=True)
    event_type: Mapped[str] = mapped_column(String(120), default="", index=True)
    metric: Mapped[str] = mapped_column(String(120), default="")
    operator: Mapped[str] = mapped_column(String(20), default="")
    value_json: Mapped[str] = mapped_column(Text, default="null")
    schedule_json: Mapped[str] = mapped_column(Text, default="{}")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AutomationCondition(Base):
    __tablename__ = "automation_conditions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    automation_id: Mapped[int] = mapped_column(ForeignKey("automations.id"), index=True)
    condition_type: Mapped[str] = mapped_column(String(80), default="rule")
    expression_json: Mapped[str] = mapped_column(Text, default="{}")
    join_operator: Mapped[str] = mapped_column(String(20), default="AND")
    priority: Mapped[int] = mapped_column(Integer, default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AutomationAction(Base):
    __tablename__ = "automation_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    automation_id: Mapped[int] = mapped_column(ForeignKey("automations.id"), index=True)
    action_type: Mapped[str] = mapped_column(String(100), index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    risk_level: Mapped[str] = mapped_column(String(40), default="low")
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(40), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AutomationHistory(Base):
    __tablename__ = "automation_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    automation_id: Mapped[int | None] = mapped_column(ForeignKey("automations.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    trigger_event_json: Mapped[str] = mapped_column(Text, default="{}")
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(40), default="recorded", index=True)
    error: Mapped[str] = mapped_column(Text, default="")
    approval_status: Mapped[str] = mapped_column(String(40), default="")
    runtime_ms: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AutomationTemplate(Base):
    __tablename__ = "automation_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(80), default="custom", index=True)
    trigger_json: Mapped[str] = mapped_column(Text, default="{}")
    conditions_json: Mapped[str] = mapped_column(Text, default="[]")
    actions_json: Mapped[str] = mapped_column(Text, default="[]")
    schedule_json: Mapped[str] = mapped_column(Text, default="{}")
    approval_rules_json: Mapped[str] = mapped_column(Text, default="{}")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AutomationAnalytics(Base):
    __tablename__ = "automation_analytics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    automation_id: Mapped[int | None] = mapped_column(ForeignKey("automations.id"), nullable=True, index=True)
    analytics_date: Mapped[str] = mapped_column(String(20), index=True)
    execution_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    approval_count: Mapped[int] = mapped_column(Integer, default=0)
    average_runtime_ms: Mapped[float] = mapped_column(Float, default=0)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Memory(Base):
    __tablename__ = "memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(160), index=True)
    value: Mapped[str] = mapped_column(Text)
    scope: Mapped[str] = mapped_column(String(80), default="global")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity_type: Mapped[str] = mapped_column(String(80))
    app_name: Mapped[str] = mapped_column(String(160), default="")
    project: Mapped[str] = mapped_column(String(260), default="")
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CodingSession(Base):
    __tablename__ = "coding_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    app_name: Mapped[str] = mapped_column(String(160))
    project: Mapped[str] = mapped_column(String(260), default="")
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    files_modified: Mapped[int] = mapped_column(Integer, default=0)
    commits: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    message: Mapped[str] = mapped_column(Text)
    alert_type: Mapped[str] = mapped_column(String(80), default="general")
    module: Mapped[str] = mapped_column(String(120), default="notifications")
    severity: Mapped[str] = mapped_column(String(40), default="low")
    priority: Mapped[str] = mapped_column(String(40), default="low")
    category: Mapped[str] = mapped_column(String(40), default="info")
    icon: Mapped[str] = mapped_column(String(80), default="info")
    color: Mapped[str] = mapped_column(String(40), default="#38bdf8")
    suggested_action: Mapped[str] = mapped_column(Text, default="")
    action_buttons_json: Mapped[str] = mapped_column(Text, default="[]")
    user_action: Mapped[str] = mapped_column(String(80), default="")
    voice_used: Mapped[str] = mapped_column(Text, default="")
    sound_used: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="sent")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class NotificationHistory(Base):
    __tablename__ = "notification_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    notification_id: Mapped[int | None] = mapped_column(ForeignKey("notifications.id"), nullable=True)
    alert_type: Mapped[str] = mapped_column(String(80), default="general")
    module: Mapped[str] = mapped_column(String(120), default="notifications")
    event: Mapped[str] = mapped_column(String(80))
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_type: Mapped[str] = mapped_column(String(80), index=True)
    module: Mapped[str] = mapped_column(String(120), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    threshold_json: Mapped[str] = mapped_column(Text, default="{}")
    actions_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AlertSetting(Base):
    __tablename__ = "alert_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(160), unique=True)
    value_json: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    notification_id: Mapped[int | None] = mapped_column(ForeignKey("notifications.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(80))
    module: Mapped[str] = mapped_column(String(120), default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AlertAction(Base):
    __tablename__ = "alert_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    notification_id: Mapped[int] = mapped_column(ForeignKey("notifications.id"), index=True)
    action: Mapped[str] = mapped_column(String(80))
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BatteryEvent(Base):
    __tablename__ = "battery_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    battery_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_charging: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    power_source: Mapped[str] = mapped_column(String(80), default="unknown")
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PowerEvent(Base):
    __tablename__ = "power_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(160))
    message: Mapped[str] = mapped_column(Text)
    battery_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    power_source: Mapped[str] = mapped_column(String(80), default="unknown")
    location: Mapped[str] = mapped_column(String(160), default="")
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ChargeHistory(Base):
    __tablename__ = "charge_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    start_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    charge_added_percent: Mapped[int] = mapped_column(Integer, default=0)
    power_source: Mapped[str] = mapped_column(String(80), default="AC Power")
    location: Mapped[str] = mapped_column(String(160), default="")
    status: Mapped[str] = mapped_column(String(40), default="active")
    detail_json: Mapped[str] = mapped_column(Text, default="{}")


class BatteryHealthHistory(Base):
    __tablename__ = "battery_health_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    battery_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    health_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    wear_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    charge_cycles: Mapped[int | None] = mapped_column(Integer, nullable=True)
    full_charge_capacity_mwh: Mapped[int | None] = mapped_column(Integer, nullable=True)
    design_capacity_mwh: Mapped[int | None] = mapped_column(Integer, nullable=True)
    battery_temperature_celsius: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_remaining_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BatterySetting(Base):
    __tablename__ = "battery_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(160), unique=True)
    value_json: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class VoiceSetting(Base):
    __tablename__ = "voice_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(160), unique=True)
    value_json: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class VoiceInteraction(Base):
    __tablename__ = "voice_interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    transcript: Mapped[str] = mapped_column(Text, default="")
    response_text: Mapped[str] = mapped_column(Text, default="")
    mode: Mapped[str] = mapped_column(String(80), default="offline")
    status: Mapped[str] = mapped_column(String(80), default="completed")
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class VoiceProfile(Base):
    __tablename__ = "voice_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    style: Mapped[str] = mapped_column(String(80), default="professional")
    description: Mapped[str] = mapped_column(Text, default="")
    wake_responses_json: Mapped[str] = mapped_column(Text, default="[]")
    completion_responses_json: Mapped[str] = mapped_column(Text, default="[]")
    reminder_responses_json: Mapped[str] = mapped_column(Text, default="[]")
    error_responses_json: Mapped[str] = mapped_column(Text, default="[]")
    notification_responses_json: Mapped[str] = mapped_column(Text, default="{}")
    tts_settings_json: Mapped[str] = mapped_column(Text, default="{}")
    built_in: Mapped[bool] = mapped_column(Boolean, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CustomPersonality(Base):
    __tablename__ = "custom_personalities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    greeting_style: Mapped[str] = mapped_column(Text, default="")
    wake_responses_json: Mapped[str] = mapped_column(Text, default="[]")
    completion_responses_json: Mapped[str] = mapped_column(Text, default="[]")
    reminder_responses_json: Mapped[str] = mapped_column(Text, default="[]")
    error_responses_json: Mapped[str] = mapped_column(Text, default="[]")
    notification_responses_json: Mapped[str] = mapped_column(Text, default="{}")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class VoiceHistory(Base):
    __tablename__ = "voice_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    personality: Mapped[str] = mapped_column(String(80), default="professional", index=True)
    input_text: Mapped[str] = mapped_column(Text, default="")
    response_text: Mapped[str] = mapped_column(Text, default="")
    context_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(40), default="completed", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WakeWordHistory(Base):
    __tablename__ = "wake_word_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phrase: Mapped[str] = mapped_column(String(160), index=True)
    source: Mapped[str] = mapped_column(String(120), default="api")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    personality: Mapped[str] = mapped_column(String(80), default="professional")
    response_text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="detected", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class VoiceAnalytics(Base):
    __tablename__ = "voice_analytics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analytics_date: Mapped[str] = mapped_column(String(20), index=True)
    personality: Mapped[str] = mapped_column(String(80), default="professional", index=True)
    wake_count: Mapped[int] = mapped_column(Integer, default=0)
    command_count: Mapped[int] = mapped_column(Integer, default=0)
    spoken_response_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    muted_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DailyBriefing(Base):
    __tablename__ = "daily_briefings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    briefing_date: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(160), default="Daily Briefing")
    summary: Mapped[str] = mapped_column(Text, default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    spoken: Mapped[bool] = mapped_column(Boolean, default=False)
    notification_id: Mapped[int | None] = mapped_column(ForeignKey("notifications.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BriefingHistory(Base):
    __tablename__ = "briefing_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    briefing_id: Mapped[int | None] = mapped_column(ForeignKey("daily_briefings.id"), nullable=True, index=True)
    briefing_date: Mapped[str] = mapped_column(String(40), index=True)
    delivery_method: Mapped[str] = mapped_column(String(80), default="manual")
    delivery_status: Mapped[str] = mapped_column(String(80), default="generated")
    content_json: Mapped[str] = mapped_column(Text, default="{}")
    statistics_json: Mapped[str] = mapped_column(Text, default="{}")
    recommendations_json: Mapped[str] = mapped_column(Text, default="[]")
    user_action: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BriefingRecommendation(Base):
    __tablename__ = "briefing_recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    briefing_id: Mapped[int | None] = mapped_column(ForeignKey("daily_briefings.id"), nullable=True, index=True)
    recommendation_type: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(40), default="medium")
    action_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(40), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BriefingSchedule(Base):
    __tablename__ = "briefing_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), default="Morning Briefing")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    schedule_time: Mapped[str] = mapped_column(String(20), default="08:00")
    days: Mapped[str] = mapped_column(String(40), default="all")
    on_startup: Mapped[bool] = mapped_column(Boolean, default=False)
    speak: Mapped[bool] = mapped_column(Boolean, default=False)
    notify: Mapped[bool] = mapped_column(Boolean, default=True)
    delivery_methods_json: Mapped[str] = mapped_column(Text, default='["dashboard","notification"]')
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_run_hint: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BriefingAnalytics(Base):
    __tablename__ = "briefing_analytics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    briefing_date: Mapped[str] = mapped_column(String(40), index=True)
    coding_seconds: Mapped[int] = mapped_column(Integer, default=0)
    study_seconds: Mapped[int] = mapped_column(Integer, default=0)
    tasks_total: Mapped[int] = mapped_column(Integer, default=0)
    tasks_completed: Mapped[int] = mapped_column(Integer, default=0)
    unread_notifications: Mapped[int] = mapped_column(Integer, default=0)
    pending_approvals: Mapped[int] = mapped_column(Integer, default=0)
    goal_average_percent: Mapped[float] = mapped_column(Float, default=0)
    productivity_score: Mapped[float] = mapped_column(Float, default=0)
    insight_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FocusSession(Base):
    __tablename__ = "focus_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(160), default="Focus Session")
    mode: Mapped[str] = mapped_column(String(80), default="pomodoro")
    status: Mapped[str] = mapped_column(String(40), default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    break_seconds: Mapped[int] = mapped_column(Integer, default=0)
    tasks_completed: Mapped[int] = mapped_column(Integer, default=0)
    distraction_count: Mapped[int] = mapped_column(Integer, default=0)
    productivity_score: Mapped[float] = mapped_column(Float, default=0)
    detail_json: Mapped[str] = mapped_column(Text, default="{}")


class FocusGoal(Base):
    __tablename__ = "focus_goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("focus_sessions.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    goal_type: Mapped[str] = mapped_column(String(80), default="custom")
    target_minutes: Mapped[int] = mapped_column(Integer, default=25)
    completed_minutes: Mapped[int] = mapped_column(Integer, default=0)
    completion_percent: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(40), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FocusHistory(Base):
    __tablename__ = "focus_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("focus_sessions.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FocusAnalytics(Base):
    __tablename__ = "focus_analytics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("focus_sessions.id"), index=True)
    focus_seconds: Mapped[int] = mapped_column(Integer, default=0)
    break_seconds: Mapped[int] = mapped_column(Integer, default=0)
    distraction_count: Mapped[int] = mapped_column(Integer, default=0)
    tasks_completed: Mapped[int] = mapped_column(Integer, default=0)
    goal_completion_percent: Mapped[float] = mapped_column(Float, default=0)
    productivity_score: Mapped[float] = mapped_column(Float, default=0)
    recommendations_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BlockedSite(Base):
    __tablename__ = "blocked_sites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    domain: Mapped[str] = mapped_column(String(240), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    category: Mapped[str] = mapped_column(String(80), default="distraction")
    reason: Mapped[str] = mapped_column(Text, default="Focus Mode Active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BlockedApp(Base):
    __tablename__ = "blocked_apps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    app_name: Mapped[str] = mapped_column(String(240), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    category: Mapped[str] = mapped_column(String(80), default="distraction")
    reason: Mapped[str] = mapped_column(Text, default="Focus Mode Active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProductivityScore(Base):
    __tablename__ = "productivity_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("focus_sessions.id"), nullable=True, index=True)
    score: Mapped[float] = mapped_column(Float, default=0)
    factors_json: Mapped[str] = mapped_column(Text, default="{}")
    recommendations_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StudyPlan(Base):
    __tablename__ = "study_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    exam_date: Mapped[str] = mapped_column(String(40), default="")
    syllabus_json: Mapped[str] = mapped_column(Text, default="[]")
    daily_plan_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(40), default="active")
    progress_percent: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StudyProgress(Base):
    __tablename__ = "study_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("study_plans.id"), index=True)
    topic: Mapped[str] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(40), default="pending")
    revision_count: Mapped[int] = mapped_column(Integer, default=0)
    progress_percent: Mapped[float] = mapped_column(Float, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StudySubject(Base):
    __tablename__ = "study_subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    priority: Mapped[str] = mapped_column(String(40), default="medium")
    difficulty: Mapped[str] = mapped_column(String(40), default="medium")
    exam_date: Mapped[str] = mapped_column(String(40), default="")
    target_score: Mapped[float] = mapped_column(Float, default=90)
    completion_percent: Mapped[float] = mapped_column(Float, default=0)
    readiness_score: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(40), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StudyChapter(Base):
    __tablename__ = "study_chapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("study_subjects.id"), index=True)
    unit: Mapped[str] = mapped_column(String(120), default="")
    title: Mapped[str] = mapped_column(String(240))
    topics_json: Mapped[str] = mapped_column(Text, default="[]")
    priority: Mapped[str] = mapped_column(String(40), default="medium")
    difficulty: Mapped[str] = mapped_column(String(40), default="medium")
    completion_percent: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(40), default="pending")
    last_studied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StudySession(Base):
    __tablename__ = "study_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("study_subjects.id"), nullable=True, index=True)
    chapter_id: Mapped[int | None] = mapped_column(ForeignKey("study_chapters.id"), nullable=True, index=True)
    subject_name: Mapped[str] = mapped_column(String(160), default="")
    chapter_title: Mapped[str] = mapped_column(String(240), default="")
    topic: Mapped[str] = mapped_column(String(240), default="")
    session_type: Mapped[str] = mapped_column(String(80), default="study")
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    revision_seconds: Mapped[int] = mapped_column(Integer, default=0)
    practice_seconds: Mapped[int] = mapped_column(Integer, default=0)
    focus_session_id: Mapped[int | None] = mapped_column(ForeignKey("focus_sessions.id"), nullable=True, index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StudyGoal(Base):
    __tablename__ = "study_goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("study_subjects.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(220))
    goal_type: Mapped[str] = mapped_column(String(80), default="study")
    target_value: Mapped[float] = mapped_column(Float, default=1)
    current_value: Mapped[float] = mapped_column(Float, default=0)
    unit: Mapped[str] = mapped_column(String(40), default="hours")
    deadline: Mapped[str] = mapped_column(String(40), default="")
    progress_percent: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(40), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ExamSchedule(Base):
    __tablename__ = "exam_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("study_subjects.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(220))
    exam_date: Mapped[str] = mapped_column(String(40), index=True)
    exam_type: Mapped[str] = mapped_column(String(80), default="exam")
    target_score: Mapped[float] = mapped_column(Float, default=90)
    readiness_score: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(40), default="upcoming")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RevisionPlan(Base):
    __tablename__ = "revision_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("study_subjects.id"), nullable=True, index=True)
    chapter_id: Mapped[int | None] = mapped_column(ForeignKey("study_chapters.id"), nullable=True, index=True)
    plan_type: Mapped[str] = mapped_column(String(80), default="first_revision")
    title: Mapped[str] = mapped_column(String(240))
    scheduled_date: Mapped[str] = mapped_column(String(40), index=True)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=45)
    status: Mapped[str] = mapped_column(String(40), default="scheduled")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StudyAnalytics(Base):
    __tablename__ = "study_analytics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analytics_date: Mapped[str] = mapped_column(String(40), index=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("study_subjects.id"), nullable=True, index=True)
    study_seconds: Mapped[int] = mapped_column(Integer, default=0)
    revision_seconds: Mapped[int] = mapped_column(Integer, default=0)
    practice_seconds: Mapped[int] = mapped_column(Integer, default=0)
    topics_completed: Mapped[int] = mapped_column(Integer, default=0)
    readiness_score: Mapped[float] = mapped_column(Float, default=0)
    recommendations_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StudyAchievement(Base):
    __tablename__ = "study_achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    category: Mapped[str] = mapped_column(String(80), default="study")
    description: Mapped[str] = mapped_column(Text, default="")
    unlocked: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(120), default="nexa")
    project: Mapped[str] = mapped_column(String(260), default="")
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TimelineSummary(Base):
    __tablename__ = "timeline_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period: Mapped[str] = mapped_column(String(40), index=True)
    start_date: Mapped[str] = mapped_column(String(40), index=True)
    end_date: Mapped[str] = mapped_column(String(40), index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    stats_json: Mapped[str] = mapped_column(Text, default="{}")
    highlights_json: Mapped[str] = mapped_column(Text, default="[]")
    recommendations_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TimelineInsight(Base):
    __tablename__ = "timeline_insights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    insight_type: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(220))
    message: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(40), default="low")
    recommendation: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ActivityHistory(Base):
    __tablename__ = "activity_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timeline_event_id: Mapped[int | None] = mapped_column(ForeignKey("timeline_events.id"), nullable=True, index=True)
    activity_type: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(220))
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    importance: Mapped[float] = mapped_column(Float, default=50)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MemorySearch(Base):
    __tablename__ = "memory_search"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    query: Mapped[str] = mapped_column(Text)
    normalized_query: Mapped[str] = mapped_column(Text, default="")
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    filters_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MemoryCategory(Base):
    __tablename__ = "memory_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    color: Mapped[str] = mapped_column(String(40), default="#facc15")
    icon: Mapped[str] = mapped_column(String(80), default="memory")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AchievementHistory(Base):
    __tablename__ = "achievements_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    achievement_type: Mapped[str] = mapped_column(String(80), default="achievement")
    title: Mapped[str] = mapped_column(String(220), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(120), default="nexa")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class HealthMetric(Base):
    __tablename__ = "health_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    metric_type: Mapped[str] = mapped_column(String(80), index=True)
    module: Mapped[str] = mapped_column(String(120), default="nexa")
    value: Mapped[float] = mapped_column(Float, default=0)
    unit: Mapped[str] = mapped_column(String(40), default="")
    status: Mapped[str] = mapped_column(String(40), default="ok")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ResourceUsage(Base):
    __tablename__ = "resource_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cpu_percent: Mapped[float] = mapped_column(Float, default=0)
    average_cpu_percent: Mapped[float] = mapped_column(Float, default=0)
    peak_cpu_percent: Mapped[float] = mapped_column(Float, default=0)
    ram_mb: Mapped[float] = mapped_column(Float, default=0)
    average_ram_mb: Mapped[float] = mapped_column(Float, default=0)
    peak_ram_mb: Mapped[float] = mapped_column(Float, default=0)
    gpu_percent: Mapped[float] = mapped_column(Float, default=0)
    battery_impact_score: Mapped[float] = mapped_column(Float, default=0)
    thermal_impact_score: Mapped[float] = mapped_column(Float, default=0)
    mode: Mapped[str] = mapped_column(String(80), default="normal")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class APIHealth(Base):
    __tablename__ = "api_health"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    api_name: Mapped[str] = mapped_column(String(120), index=True)
    latency_ms: Mapped[float] = mapped_column(Float, default=0)
    success_rate: Mapped[float] = mapped_column(Float, default=100)
    failure_rate: Mapped[float] = mapped_column(Float, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(40), default="healthy")
    error_message: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AutomationHealth(Base):
    __tablename__ = "automation_health"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    executions: Mapped[int] = mapped_column(Integer, default=0)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    pending_approvals: Mapped[int] = mapped_column(Integer, default=0)
    disabled_automations: Mapped[int] = mapped_column(Integer, default=0)
    average_runtime_ms: Mapped[float] = mapped_column(Float, default=0)
    success_rate: Mapped[float] = mapped_column(Float, default=100)
    status: Mapped[str] = mapped_column(String(40), default="healthy")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ErrorLog(Base):
    __tablename__ = "error_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module: Mapped[str] = mapped_column(String(120), index=True)
    severity: Mapped[str] = mapped_column(String(40), default="error")
    message: Mapped[str] = mapped_column(Text, default="")
    stack_trace: Mapped[str] = mapped_column(Text, default="")
    source_file: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class HealthScore(Base):
    __tablename__ = "health_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    overall_score: Mapped[float] = mapped_column(Float, default=100)
    performance_score: Mapped[float] = mapped_column(Float, default=100)
    reliability_score: Mapped[float] = mapped_column(Float, default=100)
    resource_score: Mapped[float] = mapped_column(Float, default=100)
    module_scores_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(40), default="excellent")
    recommendations_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class OptimizationEvent(Base):
    __tablename__ = "optimization_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    module: Mapped[str] = mapped_column(String(120), default="nexa")
    title: Mapped[str] = mapped_column(String(220))
    message: Mapped[str] = mapped_column(Text, default="")
    action_taken: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="recorded")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProjectBackup(Base):
    __tablename__ = "project_backups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_path: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(String(120))
    backup_path: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="created")
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(220), index=True)
    path: Mapped[str] = mapped_column(Text, index=True)
    project_type: Mapped[str] = mapped_column(String(80), default="code")
    git_branch: Mapped[str] = mapped_column(String(160), default="")
    commit_hash: Mapped[str] = mapped_column(String(80), default="")
    last_backup_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    health_score: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(40), default="active")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProjectSnapshot(Base):
    __tablename__ = "project_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    project_path: Mapped[str] = mapped_column(Text)
    project_name: Mapped[str] = mapped_column(String(220), default="")
    action: Mapped[str] = mapped_column(String(120), default="manual_snapshot")
    git_status_json: Mapped[str] = mapped_column(Text, default="{}")
    modified_files_json: Mapped[str] = mapped_column(Text, default="[]")
    commit_hash: Mapped[str] = mapped_column(String(80), default="")
    branch_name: Mapped[str] = mapped_column(String(160), default="")
    backup_path: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(40), default="created")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RecoveryPoint(Base):
    __tablename__ = "recovery_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("project_snapshots.id"), nullable=True, index=True)
    backup_id: Mapped[int | None] = mapped_column(ForeignKey("project_backups.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(220))
    restore_path: Mapped[str] = mapped_column(Text, default="")
    recovery_type: Mapped[str] = mapped_column(String(80), default="snapshot")
    status: Mapped[str] = mapped_column(String(40), default="available")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    restored_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class GitHistory(Base):
    __tablename__ = "git_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    project_path: Mapped[str] = mapped_column(Text)
    operation: Mapped[str] = mapped_column(String(80), index=True)
    branch_name: Mapped[str] = mapped_column(String(160), default="")
    commit_hash: Mapped[str] = mapped_column(String(80), default="")
    status_json: Mapped[str] = mapped_column(Text, default="{}")
    snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("project_snapshots.id"), nullable=True, index=True)
    risk_level: Mapped[str] = mapped_column(String(40), default="medium")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProjectHealth(Base):
    __tablename__ = "project_health"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    health_score: Mapped[float] = mapped_column(Float, default=0)
    uncommitted_files: Mapped[int] = mapped_column(Integer, default=0)
    backup_age_hours: Mapped[float] = mapped_column(Float, default=0)
    risk_level: Mapped[str] = mapped_column(String(40), default="low")
    recommendations_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProjectEvent(Base):
    __tablename__ = "project_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(220))
    message: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(40), default="low")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CrashReport(Base):
    __tablename__ = "crash_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    crash_type: Mapped[str] = mapped_column(String(100), index=True)
    source: Mapped[str] = mapped_column(String(120), default="emergency_recovery")
    application: Mapped[str] = mapped_column(String(160), default="")
    severity: Mapped[str] = mapped_column(String(40), default="high")
    message: Mapped[str] = mapped_column(Text, default="")
    stack_trace: Mapped[str] = mapped_column(Text, default="")
    diagnostics_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(40), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class RecoveryEvent(Base):
    __tablename__ = "recovery_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    source: Mapped[str] = mapped_column(String(120), default="emergency_recovery")
    title: Mapped[str] = mapped_column(String(220))
    message: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(40), default="medium")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RecoverySession(Base):
    __tablename__ = "recovery_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_type: Mapped[str] = mapped_column(String(100), default="workspace", index=True)
    status: Mapped[str] = mapped_column(String(40), default="captured", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    workspace_state_json: Mapped[str] = mapped_column(Text, default="{}")
    restore_plan_json: Mapped[str] = mapped_column(Text, default="[]")
    restored_items_json: Mapped[str] = mapped_column(Text, default="[]")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")


class IncidentReport(Base):
    __tablename__ = "incident_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_type: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(220))
    summary: Mapped[str] = mapped_column(Text, default="")
    applications_affected_json: Mapped[str] = mapped_column(Text, default="[]")
    recovery_actions_json: Mapped[str] = mapped_column(Text, default="[]")
    recovered_items_json: Mapped[str] = mapped_column(Text, default="[]")
    errors_json: Mapped[str] = mapped_column(Text, default="[]")
    recommendations_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(40), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class RecoveredApplication(Base):
    __tablename__ = "recovered_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("recovery_sessions.id"), nullable=True, index=True)
    app_name: Mapped[str] = mapped_column(String(160), index=True)
    process_name: Mapped[str] = mapped_column(String(160), default="")
    workspace_path: Mapped[str] = mapped_column(Text, default="")
    open_files_json: Mapped[str] = mapped_column(Text, default="[]")
    terminal_state_json: Mapped[str] = mapped_column(Text, default="{}")
    restore_command: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="available", index=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RecoveryHistory(Base):
    __tablename__ = "recovery_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(220))
    message: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="recorded", index=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DownloadHistory(Base):
    __tablename__ = "downloads_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_path: Mapped[str] = mapped_column(Text)
    file_name: Mapped[str] = mapped_column(String(260), index=True)
    category: Mapped[str] = mapped_column(String(80), default="Other")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_of: Mapped[str] = mapped_column(Text, default="")
    recommendation: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="indexed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DownloadRule(Base):
    __tablename__ = "download_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    match_type: Mapped[str] = mapped_column(String(40), default="extension")
    pattern: Mapped[str] = mapped_column(String(260), index=True)
    category: Mapped[str] = mapped_column(String(80), default="Others")
    destination: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DownloadAnalytics(Base):
    __tablename__ = "download_analytics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analytics_date: Mapped[str] = mapped_column(String(20), index=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    total_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    large_file_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DuplicateFile(Base):
    __tablename__ = "duplicate_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_path: Mapped[str] = mapped_column(Text)
    duplicate_of: Mapped[str] = mapped_column(Text, default="")
    duplicate_type: Mapped[str] = mapped_column(String(40), default="content")
    digest: Mapped[str] = mapped_column(String(128), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(40), default="open")
    recommendation: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StorageReport(Base):
    __tablename__ = "storage_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    root_path: Mapped[str] = mapped_column(Text)
    total_files: Mapped[int] = mapped_column(Integer, default=0)
    total_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    category_breakdown_json: Mapped[str] = mapped_column(Text, default="{}")
    large_files_json: Mapped[str] = mapped_column(Text, default="[]")
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    cleanup_recommendations_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CleanupSuggestion(Base):
    __tablename__ = "cleanup_suggestions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_path: Mapped[str] = mapped_column(Text)
    suggestion_type: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(220))
    message: Mapped[str] = mapped_column(Text, default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    severity: Mapped[str] = mapped_column(String(40), default="low")
    status: Mapped[str] = mapped_column(String(40), default="open")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DownloadMonitorEvent(Base):
    __tablename__ = "download_monitor_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    file_path: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(String(220))
    message: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ScreenshotHistory(Base):
    __tablename__ = "screenshot_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_path: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(120), default="shortcut")
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    analysis: Mapped[str] = mapped_column(Text, default="")
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class OCRResult(Base):
    __tablename__ = "ocr_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    screenshot_id: Mapped[int | None] = mapped_column(ForeignKey("screenshot_history.id"), nullable=True, index=True)
    engine: Mapped[str] = mapped_column(String(80), default="local")
    language: Mapped[str] = mapped_column(String(80), default="eng")
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0)
    entities_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(40), default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ErrorAnalysis(Base):
    __tablename__ = "error_analysis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    screenshot_id: Mapped[int | None] = mapped_column(ForeignKey("screenshot_history.id"), nullable=True, index=True)
    error_type: Mapped[str] = mapped_column(String(120), default="unknown")
    language: Mapped[str] = mapped_column(String(80), default="")
    framework: Mapped[str] = mapped_column(String(120), default="")
    probable_cause: Mapped[str] = mapped_column(Text, default="")
    suggested_fixes_json: Mapped[str] = mapped_column(Text, default="[]")
    severity: Mapped[str] = mapped_column(String(40), default="medium")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DocumentSummary(Base):
    __tablename__ = "document_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    screenshot_id: Mapped[int | None] = mapped_column(ForeignKey("screenshot_history.id"), nullable=True, index=True)
    document_type: Mapped[str] = mapped_column(String(120), default="general")
    summary: Mapped[str] = mapped_column(Text, default="")
    key_points_json: Mapped[str] = mapped_column(Text, default="[]")
    study_notes_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ExtractedText(Base):
    __tablename__ = "extracted_text"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    screenshot_id: Mapped[int | None] = mapped_column(ForeignKey("screenshot_history.id"), nullable=True, index=True)
    text_type: Mapped[str] = mapped_column(String(80), default="plain_text")
    value: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ScreenshotAction(Base):
    __tablename__ = "screenshot_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    screenshot_id: Mapped[int | None] = mapped_column(ForeignKey("screenshot_history.id"), nullable=True, index=True)
    action_type: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(40), default="completed")
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    goal_type: Mapped[str] = mapped_column(String(80), default="custom")
    category: Mapped[str] = mapped_column(String(80), default="custom")
    priority: Mapped[str] = mapped_column(String(40), default="medium")
    target_value: Mapped[float] = mapped_column(Float, default=1)
    current_value: Mapped[float] = mapped_column(Float, default=0)
    unit: Mapped[str] = mapped_column(String(40), default="count")
    period: Mapped[str] = mapped_column(String(40), default="daily")
    deadline: Mapped[str] = mapped_column(String(40), default="")
    reminder_settings_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(40), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GoalProgress(Base):
    __tablename__ = "goal_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id"), index=True)
    delta_value: Mapped[float] = mapped_column(Float, default=0)
    current_value: Mapped[float] = mapped_column(Float, default=0)
    progress_percent: Mapped[float] = mapped_column(Float, default=0)
    source: Mapped[str] = mapped_column(String(120), default="manual")
    note: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GoalHistory(Base):
    __tablename__ = "goal_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    goal_id: Mapped[int | None] = mapped_column(ForeignKey("goals.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(220))
    message: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="recorded")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Streak(Base):
    __tablename__ = "streaks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    goal_id: Mapped[int | None] = mapped_column(ForeignKey("goals.id"), nullable=True, index=True)
    streak_type: Mapped[str] = mapped_column(String(80), index=True)
    current_count: Mapped[int] = mapped_column(Integer, default=0)
    best_count: Mapped[int] = mapped_column(Integer, default=0)
    last_activity_date: Mapped[str] = mapped_column(String(20), default="")
    status: Mapped[str] = mapped_column(String(40), default="active")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GoalAnalytics(Base):
    __tablename__ = "goal_analytics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    goal_id: Mapped[int | None] = mapped_column(ForeignKey("goals.id"), nullable=True, index=True)
    analytics_date: Mapped[str] = mapped_column(String(20), index=True)
    progress_value: Mapped[float] = mapped_column(Float, default=0)
    progress_percent: Mapped[float] = mapped_column(Float, default=0)
    completion_rate: Mapped[float] = mapped_column(Float, default=0)
    estimated_completion_days: Mapped[float] = mapped_column(Float, default=0)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GoalReminder(Base):
    __tablename__ = "goal_reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    goal_id: Mapped[int | None] = mapped_column(ForeignKey("goals.id"), nullable=True, index=True)
    reminder_type: Mapped[str] = mapped_column(String(80), index=True)
    message: Mapped[str] = mapped_column(Text, default="")
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="pending")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Achievement(Base):
    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    badge: Mapped[str] = mapped_column(String(80), default="Badge")
    description: Mapped[str] = mapped_column(Text, default="")
    progress_percent: Mapped[float] = mapped_column(Float, default=0)
    unlocked: Mapped[bool] = mapped_column(Boolean, default=False)
    unlocked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CopilotSuggestion(Base):
    __tablename__ = "copilot_suggestions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    suggestion_type: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(40), default="low")
    module: Mapped[str] = mapped_column(String(120), default="copilot")
    action_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(40), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    acted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ContextSnapshot(Base):
    __tablename__ = "context_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    current_app: Mapped[str] = mapped_column(String(160), default="")
    current_window: Mapped[str] = mapped_column(String(240), default="")
    activity_type: Mapped[str] = mapped_column(String(80), default="idle")
    priority_context: Mapped[str] = mapped_column(String(80), default="normal")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    privacy_mode: Mapped[str] = mapped_column(String(80), default="local")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CopilotInsight(Base):
    __tablename__ = "copilot_insights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    insight_type: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(220))
    message: Mapped[str] = mapped_column(Text, default="")
    period: Mapped[str] = mapped_column(String(40), default="daily")
    severity: Mapped[str] = mapped_column(String(40), default="low")
    recommendation: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CopilotWarning(Base):
    __tablename__ = "copilot_warnings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    warning_type: Mapped[str] = mapped_column(String(80), index=True)
    module: Mapped[str] = mapped_column(String(120), default="copilot")
    title: Mapped[str] = mapped_column(String(220))
    message: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(40), default="medium")
    status: Mapped[str] = mapped_column(String(40), default="open")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class CopilotAction(Base):
    __tablename__ = "copilot_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    suggestion_id: Mapped[int | None] = mapped_column(ForeignKey("copilot_suggestions.id"), nullable=True, index=True)
    action_type: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(220))
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(40), default="available")
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class CopilotHistory(Base):
    __tablename__ = "copilot_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    suggestion_id: Mapped[int | None] = mapped_column(ForeignKey("copilot_suggestions.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(220))
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(40), default="recorded")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CopilotAnalytics(Base):
    __tablename__ = "copilot_analytics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analytics_date: Mapped[str] = mapped_column(String(40), index=True)
    suggestions_generated: Mapped[int] = mapped_column(Integer, default=0)
    suggestions_acted: Mapped[int] = mapped_column(Integer, default=0)
    warnings_open: Mapped[int] = mapped_column(Integer, default=0)
    critical_count: Mapped[int] = mapped_column(Integer, default=0)
    helpful_score: Mapped[float] = mapped_column(Float, default=0)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CollegeUpdate(Base):
    __tablename__ = "college_updates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(120), default="college")
    update_type: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="new")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CollegeProfile(Base):
    __tablename__ = "college_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    portal_type: Mapped[str] = mapped_column(String(80), default="custom")
    website_profile_id: Mapped[int | None] = mapped_column(ForeignKey("website_profiles.id"), nullable=True, index=True)
    target_attendance_percent: Mapped[float] = mapped_column(Float, default=75)
    student_identifier_encrypted: Mapped[str] = mapped_column(Text, default="")
    session_state_encrypted: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="active")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MobileDevice(Base):
    __tablename__ = "mobile_devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_name: Mapped[str] = mapped_column(String(160), default="Android Device")
    device_type: Mapped[str] = mapped_column(String(80), default="android")
    device_fingerprint: Mapped[str] = mapped_column(String(220), default="")
    status: Mapped[str] = mapped_column(String(40), default="active")
    permissions_json: Mapped[str] = mapped_column(Text, default="{}")
    security_status: Mapped[str] = mapped_column(String(40), default="trusted")
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DeviceToken(Base):
    __tablename__ = "device_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("mobile_devices.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(128), index=True)
    token_type: Mapped[str] = mapped_column(String(40), default="bearer")
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PairingCode(Base):
    __tablename__ = "pairing_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(16), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), index=True)
    qr_payload_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(40), default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("mobile_devices.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class MobileSession(Base):
    __tablename__ = "mobile_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("mobile_devices.id"), index=True)
    session_token_hash: Mapped[str] = mapped_column(String(128), index=True)
    ip_address: Mapped[str] = mapped_column(String(80), default="")
    user_agent: Mapped[str] = mapped_column(Text, default="")
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class NotificationQueue(Base):
    __tablename__ = "notification_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("mobile_devices.id"), nullable=True, index=True)
    notification_id: Mapped[int | None] = mapped_column(ForeignKey("notifications.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(100), default="notification")
    priority: Mapped[str] = mapped_column(String(40), default="normal")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(40), default="queued")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class MobilePermission(Base):
    __tablename__ = "mobile_permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("mobile_devices.id"), index=True)
    permission: Mapped[str] = mapped_column(String(120))
    allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    scope_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MobileAuditLog(Base):
    __tablename__ = "mobile_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("mobile_devices.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    action: Mapped[str] = mapped_column(String(160), default="")
    status: Mapped[str] = mapped_column(String(40), default="recorded")
    ip_address: Mapped[str] = mapped_column(String(80), default="")
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SyncQueue(Base):
    __tablename__ = "sync_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("mobile_devices.id"), nullable=True, index=True)
    item_type: Mapped[str] = mapped_column(String(100), index=True)
    operation: Mapped[str] = mapped_column(String(80), default="upsert")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(40), default="pending")
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    conflict_strategy: Mapped[str] = mapped_column(String(80), default="desktop_wins")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("college_profiles.id"), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(120), default="college")
    subject: Mapped[str] = mapped_column(String(160), default="Overall")
    attended_classes: Mapped[int] = mapped_column(Integer, default=0)
    total_classes: Mapped[int] = mapped_column(Integer, default=0)
    percentage: Mapped[float] = mapped_column(Float, default=0)
    target_percentage: Mapped[float] = mapped_column(Float, default=75)
    trend: Mapped[str] = mapped_column(String(40), default="stable")
    status: Mapped[str] = mapped_column(String(40), default="ok")
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class InternalMark(Base):
    __tablename__ = "internal_marks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("college_profiles.id"), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(120), default="college")
    subject: Mapped[str] = mapped_column(String(160))
    component: Mapped[str] = mapped_column(String(120), default="internal")
    marks_obtained: Mapped[float] = mapped_column(Float, default=0)
    max_marks: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(40), default="current")
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ResultRecord(Base):
    __tablename__ = "results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("college_profiles.id"), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(120), default="college")
    exam_name: Mapped[str] = mapped_column(String(200))
    result_type: Mapped[str] = mapped_column(String(80), default="exam")
    summary: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[str] = mapped_column(String(120), default="")
    rank: Mapped[str] = mapped_column(String(120), default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(40), default="available")
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AssignmentRecord(Base):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("college_profiles.id"), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(120), default="college")
    title: Mapped[str] = mapped_column(String(220))
    subject: Mapped[str] = mapped_column(String(160), default="")
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="pending")
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FeeRecord(Base):
    __tablename__ = "fees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("college_profiles.id"), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(120), default="college")
    fee_type: Mapped[str] = mapped_column(String(120), default="college_fee")
    amount: Mapped[float] = mapped_column(Float, default=0)
    currency: Mapped[str] = mapped_column(String(20), default="INR")
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    receipt_path: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="pending")
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TimetableRecord(Base):
    __tablename__ = "timetables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("college_profiles.id"), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(120), default="college")
    schedule_type: Mapped[str] = mapped_column(String(80), default="class")
    title: Mapped[str] = mapped_column(String(220))
    starts_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    location: Mapped[str] = mapped_column(String(220), default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AnnouncementRecord(Base):
    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("college_profiles.id"), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(120), default="college")
    announcement_type: Mapped[str] = mapped_column(String(80), default="general")
    title: Mapped[str] = mapped_column(String(220))
    message: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="new")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class KCETRecord(Base):
    __tablename__ = "kcet_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("college_profiles.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(80), default="result")
    title: Mapped[str] = mapped_column(String(220))
    rank: Mapped[str] = mapped_column(String(120), default="")
    score: Mapped[str] = mapped_column(String(120), default="")
    screenshot_path: Mapped[str] = mapped_column(Text, default="")
    pdf_path: Mapped[str] = mapped_column(Text, default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(40), default="available")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(160), unique=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
