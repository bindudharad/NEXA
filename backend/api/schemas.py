from pydantic import BaseModel, Field


class CommandRequest(BaseModel):
    command: str = Field(min_length=1)
    auto_confirm: bool = False


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
