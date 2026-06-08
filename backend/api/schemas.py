from pydantic import BaseModel, Field


class CommandRequest(BaseModel):
    command: str = Field(min_length=1)
    auto_confirm: bool = False


class ApprovalEditRequest(BaseModel):
    task_title: str | None = None
    date: str | None = None
    time: str | None = None
    trigger: str | None = None
    conditions: dict | None = None
    priority: str | None = None


class ApprovalRejectRequest(BaseModel):
    reason: str = ""


class MemoryRequest(BaseModel):
    key: str
    value: str
    scope: str = "global"


class AutomationRequest(BaseModel):
    name: str
    condition: dict
    action: dict


class NotificationRequest(BaseModel):
    title: str
    message: str
    alert_type: str = "general"
    module: str = "notifications"
    severity: str = "low"
    priority: str = "low"
    category: str = "info"
    suggested_action: str = "Review the notification details."
    action_buttons: list[str] = ["Dismiss"]


class NotificationActionRequest(BaseModel):
    action: str
    payload: dict = {}


class AlertSettingsRequest(BaseModel):
    sound_enabled: bool | None = None
    voice_enabled: bool | None = None
    sound_volume: int | None = Field(default=None, ge=0, le=100)
    notification_position: str | None = None
    notification_duration_seconds: int | None = Field(default=None, ge=1, le=60)


class VoiceSettingsRequest(BaseModel):
    enabled: bool | None = None
    wake_word_enabled: bool | None = None
    wake_phrases: list[str] | str | None = None
    activation_response: str | None = None
    response_style: str | None = None
    privacy_mode: str | None = None
    cloud_ai_enabled: bool | None = None
    offline_only: bool | None = None
    push_to_talk: bool | None = None
    microphone_device: str | None = None
    sensitivity: float | None = Field(default=None, ge=0.1, le=1.0)
    noise_filtering: bool | None = None
    voice_enabled: bool | None = None
    voice_volume: int | None = Field(default=None, ge=0, le=100)
    voice_speed: int | None = Field(default=None, ge=-10, le=10)
    voice_gender: str | None = None
    voice_language: str | None = None
    activation_notification_enabled: bool | None = None
    listen_timeout_seconds: int | None = Field(default=None, ge=1, le=60)


class VoiceWakeRequest(BaseModel):
    phrase: str = "Nexa"
    source: str = "api"
    confidence: float | None = None


class VoiceCommandRequest(BaseModel):
    command: str = Field(min_length=1)
    source: str = "voice"


class EventRequest(BaseModel):
    event_type: str
    payload: dict = {}


class FileOperationRequest(BaseModel):
    path: str
    destination: str | None = None
    content: str = ""
    new_name: str | None = None
    query: str | None = None


class BrowserFormRequest(BaseModel):
    url: str
    fields: dict[str, str]
    submit_selector: str | None = None


class BrowserDownloadRequest(BaseModel):
    url: str
    click_selector: str
    destination: str | None = None


class WebsiteAnalyzeRequest(BaseModel):
    name: str
    url: str
    html: str | None = None
    headless: bool = True


class WebsiteProfileRequest(BaseModel):
    name: str
    url: str
    field_mapping: dict = {}
    navigation_rules: dict = {}
    login_process: dict = {}
    retry_policy: dict = {}
    success_check: dict = {}
    credentials: dict | None = None


class WebsiteCredentialRequest(BaseModel):
    credentials: dict
    label: str = "default"


class WebsiteActionRequest(BaseModel):
    name: str
    action: dict


class WebsiteMonitoringRequest(BaseModel):
    enabled: bool
    interval_seconds: int = Field(default=300, ge=60)


class WebsiteOpenRequest(BaseModel):
    name: str


class WebsiteImportRequest(BaseModel):
    payload: dict


class KcetResultRequest(BaseModel):
    application_number: str | None = None
    date_of_birth: str | None = None
    save_profile: bool = False
    url: str | None = None


class BatteryAlertSettingsRequest(BaseModel):
    enabled: bool | None = None
    threshold_percent: int | None = Field(default=None, ge=1, le=100)
    voice_enabled: bool | None = None
    sound_enabled: bool | None = None
    notification_enabled: bool | None = None
    repeat_interval_seconds: int | None = Field(default=None, ge=30)


class BatterySimulationRequest(BaseModel):
    battery_percent: int | None = Field(default=None, ge=0, le=100)
    is_charging: bool | None = None


class PowerMonitorSettingsRequest(BaseModel):
    enabled: bool | None = None
    charger_connected_alerts: bool | None = None
    charger_disconnected_alerts: bool | None = None
    battery_95_alert_enabled: bool | None = None
    battery_full_alert_enabled: bool | None = None
    low_battery_alert_enabled: bool | None = None
    critical_battery_alert_enabled: bool | None = None
    fluctuation_detection_enabled: bool | None = None
    voice_enabled: bool | None = None
    sound_enabled: bool | None = None
    notification_enabled: bool | None = None
    low_battery_threshold_percent: int | None = Field(default=None, ge=1, le=100)
    critical_battery_threshold_percent: int | None = Field(default=None, ge=1, le=100)
    battery_95_threshold_percent: int | None = Field(default=None, ge=50, le=100)
    fluctuation_window_seconds: int | None = Field(default=None, ge=5, le=300)
    fluctuation_transition_count: int | None = Field(default=None, ge=2, le=20)
    low_repeat_interval_seconds: int | None = Field(default=None, ge=30)
    full_repeat_interval_seconds: int | None = Field(default=None, ge=300)
    event_sound_volume: int | None = Field(default=None, ge=0, le=100)
    warning_sound_volume: int | None = Field(default=None, ge=0, le=100)


class PowerSimulationRequest(BaseModel):
    battery_percent: int | None = Field(default=None, ge=0, le=100)
    is_charging: bool | None = None


class GpuMonitorSettingsRequest(BaseModel):
    enabled: bool | None = None
    threshold_celsius: int | None = Field(default=None, ge=1, le=120)
    sound_enabled: bool | None = None
    voice_enabled: bool | None = None
    notification_enabled: bool | None = None
    repeat_interval_seconds: int | None = Field(default=None, ge=30)


class GpuSimulationRequest(BaseModel):
    temperature_celsius: float = Field(ge=0, le=130)
    usage_percent: float | None = Field(default=None, ge=0, le=100)
    memory_usage_percent: float | None = Field(default=None, ge=0, le=100)


class SystemAlertSettingsRequest(BaseModel):
    enabled: bool | None = None
    cpu_temperature_threshold_celsius: int | None = Field(default=None, ge=1, le=120)
    cpu_usage_threshold_percent: int | None = Field(default=None, ge=1, le=100)
    memory_threshold_percent: int | None = Field(default=None, ge=1, le=100)
    storage_threshold_percent: int | None = Field(default=None, ge=1, le=100)
    notification_enabled: bool | None = None
    sound_enabled: bool | None = None
    voice_enabled: bool | None = None
    repeat_interval_seconds: int | None = Field(default=None, ge=30)


class ResourceManagerSettingsRequest(BaseModel):
    enabled: bool | None = None
    power_saving_battery_threshold_percent: int | None = Field(default=None, ge=1, le=100)
    thermal_cpu_threshold_celsius: int | None = Field(default=None, ge=1, le=120)
    thermal_gpu_threshold_celsius: int | None = Field(default=None, ge=1, le=120)
    heavy_cpu_threshold_percent: int | None = Field(default=None, ge=1, le=100)
    idle_seconds_for_light_mode: int | None = Field(default=None, ge=30)
    alert_poll_interval_seconds: int | None = Field(default=None, ge=15)
    dashboard_refresh_interval_seconds: int | None = Field(default=None, ge=15)
    website_monitor_interval_seconds: int | None = Field(default=None, ge=300)
    gpu_monitor_interval_seconds: int | None = Field(default=None, ge=60)
    system_monitor_interval_seconds: int | None = Field(default=None, ge=60)
    minimum_interval_seconds: int | None = Field(default=None, ge=5)


class AutomationToggleRequest(BaseModel):
    enabled: bool


class CopilotSuggestionStatusRequest(BaseModel):
    status: str = "dismissed"


class DailyBriefingRequest(BaseModel):
    speak: bool = False
    notify: bool = True


class DailyBriefingSettingsRequest(BaseModel):
    enabled: bool | None = None
    time: str | None = None
    days: str | None = None
    on_startup: bool | None = None
    speak: bool | None = None
    notify: bool | None = None
    weather_location: str | None = None
    delivery_methods: list[str] | str | None = None


class FocusStartRequest(BaseModel):
    title: str = "Focus Session"
    duration_minutes: int = Field(default=25, ge=1, le=240)
    break_minutes: int = Field(default=5, ge=0, le=60)
    mode: str = "pomodoro"
    session_type: str = "focus"
    subject: str = ""
    chapter: str = ""
    topic: str = ""
    current_goal: str = ""
    pomodoro_preset: str = "25/5"
    blocked_websites: list[str] = []
    blocked_apps: list[str] = []
    mute_notifications: bool = True
    allow_critical_notifications: bool = True
    long_break_minutes: int = Field(default=15, ge=0, le=60)
    cycles_before_long_break: int = Field(default=4, ge=1, le=12)


class FocusEndRequest(BaseModel):
    session_id: int | None = None
    tasks_completed: int = Field(default=0, ge=0)
    distraction_count: int = Field(default=0, ge=0)
    goal_completion_percent: float = Field(default=0, ge=0, le=100)


class FocusControlRequest(BaseModel):
    session_id: int | None = None
    minutes: int = Field(default=5, ge=1, le=240)
    reason: str = ""


class FocusDistractionRequest(BaseModel):
    url: str | None = None
    app_name: str | None = None


class FocusGoalRequest(BaseModel):
    title: str = Field(min_length=1)
    goal_type: str = "custom"
    target_minutes: int = Field(default=25, ge=1, le=10000)
    session_id: int | None = None


class FocusGoalProgressRequest(BaseModel):
    completed_minutes: int = Field(ge=0)
    status: str | None = None


class StudyPlanRequest(BaseModel):
    title: str = Field(min_length=1)
    exam_date: str = ""
    topics: list[str] = []
    subject_name: str = ""
    priority: str = "medium"
    difficulty: str = "medium"
    target_score: float = Field(default=90, ge=0, le=100)
    availability_minutes_per_day: int = Field(default=120, ge=15, le=1440)


class StudyProgressRequest(BaseModel):
    topic: str = Field(min_length=1)
    progress_percent: float = Field(ge=0, le=100)
    status: str = "in_progress"
    notes: str = ""


class StudySubjectRequest(BaseModel):
    name: str = Field(min_length=1)
    priority: str = "medium"
    difficulty: str = "medium"
    exam_date: str = ""
    target_score: float = Field(default=90, ge=0, le=100)


class StudyChapterRequest(BaseModel):
    subject_id: int
    title: str = Field(min_length=1)
    unit: str = ""
    topics: list[str] = []
    priority: str = "medium"
    difficulty: str = "medium"


class StudyChapterProgressRequest(BaseModel):
    completion_percent: float = Field(ge=0, le=100)
    status: str = "in_progress"
    notes: str = ""


class StudySessionRequest(BaseModel):
    subject_id: int | None = None
    subject_name: str = ""
    chapter_id: int | None = None
    chapter_title: str = ""
    topic: str = ""
    duration_minutes: int = Field(default=25, ge=1, le=1440)
    session_type: str = "study"
    notes: str = ""


class StudyGoalRequest(BaseModel):
    title: str = Field(min_length=1)
    target_value: float = Field(gt=0)
    unit: str = "hours"
    subject_id: int | None = None
    deadline: str = ""


class StudyGoalUpdateRequest(BaseModel):
    current_value: float = Field(ge=0)


class TimelineEventRequest(BaseModel):
    event_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = ""
    source: str = "nexa"
    duration_seconds: int = Field(default=0, ge=0)
    metadata: dict = {}


class TimelineSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=100, ge=1, le=1000)


class ProjectGuardianSnapshotRequest(BaseModel):
    project_path: str = Field(min_length=1)
    action: str = "manual_snapshot"


class ProjectGuardianProtectRequest(BaseModel):
    project_path: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    reason: str = ""


class ProjectGuardianRestoreRequest(BaseModel):
    backup_id: int
    restore_path: str = Field(min_length=1)


class DownloadsScanRequest(BaseModel):
    folder: str | None = None
    large_file_mb: int = Field(default=500, ge=1)


class DownloadsOrganizeRequest(BaseModel):
    folder: str | None = None
    dry_run: bool = True


class DownloadsSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=100, ge=1, le=1000)


class DownloadRuleRequest(BaseModel):
    name: str = Field(min_length=1)
    pattern: str = Field(min_length=1)
    category: str = Field(min_length=1)
    destination: str = ""
    match_type: str = "extension"
    enabled: bool = True
    priority: int = Field(default=100, ge=1, le=1000)


class ScreenshotRecordRequest(BaseModel):
    file_path: str = Field(min_length=1)
    source: str = "shortcut"
    extracted_text: str = ""
    analysis: str = ""
    capture_mode: str = "full_screen"
    language: str = "eng"


class ScreenshotSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=50, ge=1, le=500)


class ScreenshotActionRequest(BaseModel):
    action_type: str = Field(min_length=1)
    payload: dict = {}


class ScreenshotSettingsRequest(BaseModel):
    cloud_ai_enabled: bool | None = None
    require_cloud_approval: bool | None = None
    local_ocr_enabled: bool | None = None
    voice_enabled: bool | None = None
    history_enabled: bool | None = None
    default_hotkey: str | None = None


class AutomationBuilderRequest(BaseModel):
    prompt: str = Field(min_length=1)


class GoalRequest(BaseModel):
    title: str = Field(min_length=1)
    target_value: float = Field(gt=0)
    unit: str = "count"
    goal_type: str = "custom"
    period: str = "daily"


class GoalProgressRequest(BaseModel):
    current_value: float = Field(ge=0)


class CollegeCheckRequest(BaseModel):
    source: str = "college"
