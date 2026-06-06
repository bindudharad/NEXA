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


class GpuMonitorSettingsRequest(BaseModel):
    enabled: bool | None = None
    threshold_celsius: int | None = Field(default=None, ge=1, le=120)
    sound_enabled: bool | None = None
    notification_enabled: bool | None = None
    repeat_interval_seconds: int | None = Field(default=None, ge=30)


class GpuSimulationRequest(BaseModel):
    temperature_celsius: float = Field(ge=0, le=130)
    usage_percent: float | None = Field(default=None, ge=0, le=100)
    memory_usage_percent: float | None = Field(default=None, ge=0, le=100)


class AutomationToggleRequest(BaseModel):
    enabled: bool
