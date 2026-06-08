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
        indexes = [
            "CREATE INDEX IF NOT EXISTS ix_notifications_created_at ON notifications (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_notifications_alert_type ON notifications (alert_type)",
            "CREATE INDEX IF NOT EXISTS ix_notifications_severity ON notifications (severity)",
            "CREATE INDEX IF NOT EXISTS ix_power_events_created_at ON power_events (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_charge_history_started_at ON charge_history (started_at)",
            "CREATE INDEX IF NOT EXISTS ix_voice_interactions_created_at ON voice_interactions (created_at)",
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
            "CREATE INDEX IF NOT EXISTS ix_projects_path ON projects (path)",
            "CREATE INDEX IF NOT EXISTS ix_project_snapshots_created_at ON project_snapshots (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_recovery_points_created_at ON recovery_points (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_git_history_created_at ON git_history (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_project_health_created_at ON project_health (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_project_events_created_at ON project_events (created_at)",
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
            "CREATE INDEX IF NOT EXISTS ix_achievements_created_at ON achievements (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_copilot_suggestions_created_at ON copilot_suggestions (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_college_updates_created_at ON college_updates (created_at)",
        ]
        for statement in indexes:
            connection.execute(text(statement))
