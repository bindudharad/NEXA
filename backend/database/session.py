from sqlalchemy import create_engine
from sqlalchemy import inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database() -> None:
    from backend.database import models

    Base.metadata.create_all(bind=engine)
    _migrate_sqlite_notifications()


def _migrate_sqlite_notifications() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    inspector = inspect(engine)
    if "notifications" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("notifications")}
    columns = {
        "alert_type": "VARCHAR(80) DEFAULT 'general' NOT NULL",
        "module": "VARCHAR(120) DEFAULT 'notifications' NOT NULL",
        "severity": "VARCHAR(40) DEFAULT 'low' NOT NULL",
        "priority": "VARCHAR(40) DEFAULT 'low' NOT NULL",
        "category": "VARCHAR(40) DEFAULT 'info' NOT NULL",
        "icon": "VARCHAR(80) DEFAULT 'info' NOT NULL",
        "color": "VARCHAR(40) DEFAULT '#38bdf8' NOT NULL",
        "suggested_action": "TEXT DEFAULT '' NOT NULL",
        "action_buttons_json": "TEXT DEFAULT '[]' NOT NULL",
        "user_action": "VARCHAR(80) DEFAULT '' NOT NULL",
        "voice_used": "TEXT DEFAULT '' NOT NULL",
        "sound_used": "TEXT DEFAULT '' NOT NULL",
        "status": "VARCHAR(40) DEFAULT 'sent' NOT NULL",
        "metadata_json": "TEXT DEFAULT '{}' NOT NULL",
    }
    with engine.begin() as connection:
        for name, ddl in columns.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE notifications ADD COLUMN {name} {ddl}"))
        if "goals" in inspector.get_table_names():
            goal_existing = {column["name"] for column in inspector.get_columns("goals")}
            goal_columns = {
                "description": "TEXT DEFAULT '' NOT NULL",
                "category": "VARCHAR(80) DEFAULT 'custom' NOT NULL",
                "priority": "VARCHAR(40) DEFAULT 'medium' NOT NULL",
                "deadline": "VARCHAR(40) DEFAULT '' NOT NULL",
                "reminder_settings_json": "TEXT DEFAULT '{}' NOT NULL",
            }
            for name, ddl in goal_columns.items():
                if name not in goal_existing:
                    connection.execute(text(f"ALTER TABLE goals ADD COLUMN {name} {ddl}"))
        indexes = [
            "CREATE INDEX IF NOT EXISTS ix_notifications_created_at ON notifications (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_notifications_alert_type ON notifications (alert_type)",
            "CREATE INDEX IF NOT EXISTS ix_notifications_severity ON notifications (severity)",
            "CREATE INDEX IF NOT EXISTS ix_automation_triggers_type ON automation_triggers (trigger_type)",
            "CREATE INDEX IF NOT EXISTS ix_automation_triggers_event_type ON automation_triggers (event_type)",
            "CREATE INDEX IF NOT EXISTS ix_automation_conditions_automation_id ON automation_conditions (automation_id)",
            "CREATE INDEX IF NOT EXISTS ix_automation_actions_type ON automation_actions (action_type)",
            "CREATE INDEX IF NOT EXISTS ix_automation_history_created_at ON automation_history (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_automation_templates_category ON automation_templates (category)",
            "CREATE INDEX IF NOT EXISTS ix_automation_analytics_date ON automation_analytics (analytics_date)",
            "CREATE INDEX IF NOT EXISTS ix_power_events_created_at ON power_events (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_charge_history_started_at ON charge_history (started_at)",
            "CREATE INDEX IF NOT EXISTS ix_voice_interactions_created_at ON voice_interactions (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_voice_profiles_profile_key ON voice_profiles (profile_key)",
            "CREATE INDEX IF NOT EXISTS ix_custom_personalities_name ON custom_personalities (name)",
            "CREATE INDEX IF NOT EXISTS ix_voice_history_created_at ON voice_history (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_wake_word_history_created_at ON wake_word_history (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_voice_analytics_date ON voice_analytics (analytics_date)",
            "CREATE INDEX IF NOT EXISTS ix_daily_briefings_created_at ON daily_briefings (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_briefing_history_created_at ON briefing_history (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_briefing_recommendations_created_at ON briefing_recommendations (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_briefing_schedules_time ON briefing_schedules (schedule_time)",
            "CREATE INDEX IF NOT EXISTS ix_briefing_analytics_created_at ON briefing_analytics (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_focus_sessions_started_at ON focus_sessions (started_at)",
            "CREATE INDEX IF NOT EXISTS ix_focus_goals_created_at ON focus_goals (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_focus_history_created_at ON focus_history (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_focus_analytics_created_at ON focus_analytics (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_blocked_sites_domain ON blocked_sites (domain)",
            "CREATE INDEX IF NOT EXISTS ix_blocked_apps_name ON blocked_apps (app_name)",
            "CREATE INDEX IF NOT EXISTS ix_productivity_scores_created_at ON productivity_scores (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_study_subjects_name ON study_subjects (name)",
            "CREATE INDEX IF NOT EXISTS ix_study_chapters_subject_id ON study_chapters (subject_id)",
            "CREATE INDEX IF NOT EXISTS ix_study_sessions_created_at ON study_sessions (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_study_goals_created_at ON study_goals (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_exam_schedules_exam_date ON exam_schedules (exam_date)",
            "CREATE INDEX IF NOT EXISTS ix_revision_plans_scheduled_date ON revision_plans (scheduled_date)",
            "CREATE INDEX IF NOT EXISTS ix_study_analytics_date ON study_analytics (analytics_date)",
            "CREATE INDEX IF NOT EXISTS ix_study_achievements_title ON study_achievements (title)",
            "CREATE INDEX IF NOT EXISTS ix_timeline_events_created_at ON timeline_events (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_timeline_summaries_period ON timeline_summaries (period)",
            "CREATE INDEX IF NOT EXISTS ix_timeline_insights_created_at ON timeline_insights (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_activity_history_created_at ON activity_history (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_memory_search_created_at ON memory_search (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_memory_categories_name ON memory_categories (name)",
            "CREATE INDEX IF NOT EXISTS ix_achievements_history_created_at ON achievements_history (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_health_metrics_created_at ON health_metrics (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_health_metrics_type ON health_metrics (metric_type)",
            "CREATE INDEX IF NOT EXISTS ix_resource_usage_created_at ON resource_usage (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_api_health_created_at ON api_health (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_api_health_name ON api_health (api_name)",
            "CREATE INDEX IF NOT EXISTS ix_automation_health_created_at ON automation_health (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_error_logs_created_at ON error_logs (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_error_logs_module ON error_logs (module)",
            "CREATE INDEX IF NOT EXISTS ix_health_scores_created_at ON health_scores (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_optimization_events_created_at ON optimization_events (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_optimization_events_type ON optimization_events (event_type)",
            "CREATE INDEX IF NOT EXISTS ix_projects_path ON projects (path)",
            "CREATE INDEX IF NOT EXISTS ix_project_snapshots_created_at ON project_snapshots (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_recovery_points_created_at ON recovery_points (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_git_history_created_at ON git_history (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_project_health_created_at ON project_health (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_project_events_created_at ON project_events (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_crash_reports_created_at ON crash_reports (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_crash_reports_application ON crash_reports (application)",
            "CREATE INDEX IF NOT EXISTS ix_recovery_events_created_at ON recovery_events (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_recovery_sessions_started_at ON recovery_sessions (started_at)",
            "CREATE INDEX IF NOT EXISTS ix_incident_reports_created_at ON incident_reports (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_recovered_applications_created_at ON recovered_applications (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_recovery_history_created_at ON recovery_history (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_downloads_history_created_at ON downloads_history (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_download_rules_pattern ON download_rules (pattern)",
            "CREATE INDEX IF NOT EXISTS ix_download_analytics_date ON download_analytics (analytics_date)",
            "CREATE INDEX IF NOT EXISTS ix_duplicate_files_digest ON duplicate_files (digest)",
            "CREATE INDEX IF NOT EXISTS ix_storage_reports_created_at ON storage_reports (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_cleanup_suggestions_created_at ON cleanup_suggestions (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_cleanup_suggestions_type ON cleanup_suggestions (suggestion_type)",
            "CREATE INDEX IF NOT EXISTS ix_download_monitor_events_created_at ON download_monitor_events (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_screenshot_history_created_at ON screenshot_history (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_ocr_results_screenshot_id ON ocr_results (screenshot_id)",
            "CREATE INDEX IF NOT EXISTS ix_error_analysis_screenshot_id ON error_analysis (screenshot_id)",
            "CREATE INDEX IF NOT EXISTS ix_document_summaries_screenshot_id ON document_summaries (screenshot_id)",
            "CREATE INDEX IF NOT EXISTS ix_extracted_text_screenshot_id ON extracted_text (screenshot_id)",
            "CREATE INDEX IF NOT EXISTS ix_screenshot_actions_screenshot_id ON screenshot_actions (screenshot_id)",
            "CREATE INDEX IF NOT EXISTS ix_screenshot_actions_type ON screenshot_actions (action_type)",
            "CREATE INDEX IF NOT EXISTS ix_goals_created_at ON goals (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_goals_type ON goals (goal_type)",
            "CREATE INDEX IF NOT EXISTS ix_goals_status ON goals (status)",
            "CREATE INDEX IF NOT EXISTS ix_goal_progress_goal_id ON goal_progress (goal_id)",
            "CREATE INDEX IF NOT EXISTS ix_goal_progress_created_at ON goal_progress (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_goal_history_goal_id ON goal_history (goal_id)",
            "CREATE INDEX IF NOT EXISTS ix_goal_history_created_at ON goal_history (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_streaks_goal_id ON streaks (goal_id)",
            "CREATE INDEX IF NOT EXISTS ix_streaks_type ON streaks (streak_type)",
            "CREATE INDEX IF NOT EXISTS ix_goal_analytics_date ON goal_analytics (analytics_date)",
            "CREATE INDEX IF NOT EXISTS ix_goal_reminders_due_at ON goal_reminders (due_at)",
            "CREATE INDEX IF NOT EXISTS ix_achievements_created_at ON achievements (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_copilot_suggestions_created_at ON copilot_suggestions (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_context_snapshots_created_at ON context_snapshots (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_context_snapshots_activity_type ON context_snapshots (activity_type)",
            "CREATE INDEX IF NOT EXISTS ix_copilot_insights_created_at ON copilot_insights (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_copilot_insights_type ON copilot_insights (insight_type)",
            "CREATE INDEX IF NOT EXISTS ix_copilot_warnings_created_at ON copilot_warnings (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_copilot_warnings_status ON copilot_warnings (status)",
            "CREATE INDEX IF NOT EXISTS ix_copilot_actions_suggestion_id ON copilot_actions (suggestion_id)",
            "CREATE INDEX IF NOT EXISTS ix_copilot_actions_type ON copilot_actions (action_type)",
            "CREATE INDEX IF NOT EXISTS ix_copilot_history_created_at ON copilot_history (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_copilot_analytics_date ON copilot_analytics (analytics_date)",
            "CREATE INDEX IF NOT EXISTS ix_college_updates_created_at ON college_updates (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_college_profiles_name ON college_profiles (name)",
            "CREATE INDEX IF NOT EXISTS ix_mobile_devices_created_at ON mobile_devices (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_mobile_devices_fingerprint ON mobile_devices (device_fingerprint)",
            "CREATE INDEX IF NOT EXISTS ix_device_tokens_device_id ON device_tokens (device_id)",
            "CREATE INDEX IF NOT EXISTS ix_device_tokens_token_hash ON device_tokens (token_hash)",
            "CREATE INDEX IF NOT EXISTS ix_pairing_codes_code ON pairing_codes (code)",
            "CREATE INDEX IF NOT EXISTS ix_pairing_codes_expires ON pairing_codes (expires_at)",
            "CREATE INDEX IF NOT EXISTS ix_mobile_sessions_device_id ON mobile_sessions (device_id)",
            "CREATE INDEX IF NOT EXISTS ix_mobile_sessions_token_hash ON mobile_sessions (session_token_hash)",
            "CREATE INDEX IF NOT EXISTS ix_notification_queue_device_id ON notification_queue (device_id)",
            "CREATE INDEX IF NOT EXISTS ix_notification_queue_status ON notification_queue (status)",
            "CREATE INDEX IF NOT EXISTS ix_mobile_permissions_device_id ON mobile_permissions (device_id)",
            "CREATE INDEX IF NOT EXISTS ix_mobile_audit_logs_created_at ON mobile_audit_logs (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_sync_queue_device_id ON sync_queue (device_id)",
            "CREATE INDEX IF NOT EXISTS ix_sync_queue_status ON sync_queue (status)",
            "CREATE INDEX IF NOT EXISTS ix_attendance_records_recorded_at ON attendance_records (recorded_at)",
            "CREATE INDEX IF NOT EXISTS ix_internal_marks_recorded_at ON internal_marks (recorded_at)",
            "CREATE INDEX IF NOT EXISTS ix_results_recorded_at ON results (recorded_at)",
            "CREATE INDEX IF NOT EXISTS ix_assignments_due_at ON assignments (due_at)",
            "CREATE INDEX IF NOT EXISTS ix_fees_due_at ON fees (due_at)",
            "CREATE INDEX IF NOT EXISTS ix_timetables_starts_at ON timetables (starts_at)",
            "CREATE INDEX IF NOT EXISTS ix_announcements_created_at ON announcements (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_kcet_records_created_at ON kcet_records (created_at)",
        ]
        for statement in indexes:
            connection.execute(text(statement))
