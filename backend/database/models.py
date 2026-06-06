from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
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
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(160), unique=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
