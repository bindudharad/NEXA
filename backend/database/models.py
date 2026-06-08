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
    goal_type: Mapped[str] = mapped_column(String(80), default="custom")
    target_value: Mapped[float] = mapped_column(Float, default=1)
    current_value: Mapped[float] = mapped_column(Float, default=0)
    unit: Mapped[str] = mapped_column(String(40), default="count")
    period: Mapped[str] = mapped_column(String(40), default="daily")
    status: Mapped[str] = mapped_column(String(40), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


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


class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(160), unique=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
