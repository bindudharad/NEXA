const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8010/api";

export type Task = {
  id: number;
  command: string;
  intent: string;
  agent: string;
  status: string;
  requires_confirmation: boolean;
  result: Record<string, unknown>;
  created_at: string;
};

export type TaskApproval = {
  id: number;
  original_text: string;
  corrected_text: string;
  intent: string;
  task_type: string;
  confidence: number;
  status: string;
  structured_task: Record<string, unknown>;
  plan: Record<string, unknown>;
  requires_approval: boolean;
  high_risk: boolean;
  clarification_required: boolean;
  provider: string;
  task_id: number | null;
  task?: Task | null;
  created_at: string;
  updated_at: string;
};

export type BatteryAlertSettings = {
  enabled: boolean;
  threshold_percent: number;
  voice_enabled: boolean;
  sound_enabled: boolean;
  notification_enabled: boolean;
  repeat_interval_seconds: number;
};

export type BatteryAlertStatus = {
  battery_percent: number | null;
  is_charging: boolean | null;
  alert_active: boolean;
  last_alert_time: string | null;
  last_stop_time: string | null;
  testing_mode: boolean;
};

export type PowerMonitorStatus = {
  battery_percent: number | null;
  is_charging: boolean | null;
  charger_connected: boolean | null;
  power_source: string;
  adapter_status: string;
  battery_health_percent: number | null;
  battery_wear_percent: number | null;
  charge_cycles: number | null;
  full_charge_capacity_mwh: number | null;
  design_capacity_mwh: number | null;
  estimated_remaining_seconds: number | null;
  battery_temperature_celsius: number | null;
  charging_speed_percent_per_hour: number | null;
  average_daily_usage_percent: number | null;
  average_charging_time_seconds: number | null;
  battery_age_days: number | null;
  active_charge_session_id: number | null;
  last_event_type: string | null;
  last_event_time: string | null;
  last_full_charge_time: string | null;
  testing_mode: boolean;
};

export type PowerMonitorSettings = {
  enabled: boolean;
  charger_connected_alerts: boolean;
  charger_disconnected_alerts: boolean;
  battery_95_alert_enabled: boolean;
  battery_full_alert_enabled: boolean;
  low_battery_alert_enabled: boolean;
  critical_battery_alert_enabled: boolean;
  fluctuation_detection_enabled: boolean;
  voice_enabled: boolean;
  sound_enabled: boolean;
  notification_enabled: boolean;
  low_battery_threshold_percent: number;
  critical_battery_threshold_percent: number;
  battery_95_threshold_percent: number;
  fluctuation_window_seconds: number;
  fluctuation_transition_count: number;
  low_repeat_interval_seconds: number;
  full_repeat_interval_seconds: number;
  event_sound_volume: number;
  warning_sound_volume: number;
};

export type PowerEvent = {
  id: number;
  event_type: string;
  title: string;
  message: string;
  battery_percent: number | null;
  power_source: string;
  location: string;
  detail: Record<string, unknown>;
  created_at: string;
};

export type ChargeSession = {
  id: number;
  started_at: string;
  ended_at: string | null;
  start_percent: number | null;
  end_percent: number | null;
  duration_seconds: number;
  charge_added_percent: number;
  power_source: string;
  location: string;
  status: string;
  detail: Record<string, unknown>;
};

export type PowerHistory = {
  events: PowerEvent[];
  charge_sessions: ChargeSession[];
  latest_health: Record<string, unknown> | null;
};

export type GpuMonitorSettings = {
  enabled: boolean;
  threshold_celsius: number;
  sound_enabled: boolean;
  voice_enabled: boolean;
  notification_enabled: boolean;
  repeat_interval_seconds: number;
};

export type GpuMonitorStatus = {
  gpu_name: string | null;
  temperature_celsius: number | null;
  usage_percent: number | null;
  memory_usage_percent: number | null;
  memory_used_mb: number | null;
  memory_total_mb: number | null;
  health_status: string;
  alert_active: boolean;
  last_alert_time: string | null;
  last_stop_time: string | null;
  testing_mode: boolean;
  source: string | null;
};

export type NotificationAlert = {
  id: number;
  alert_type: string;
  module: string;
  title: string;
  message: string;
  timestamp: string;
  suggested_action: string;
  action_buttons: string[];
  severity: string;
  priority: string;
  category: string;
  icon: string;
  color: string;
  user_action: string;
  voice_used: string;
  sound_used: string;
  status: string;
  read: boolean;
  metadata: Record<string, unknown>;
};

export type AlertSettings = {
  sound_enabled: boolean;
  voice_enabled: boolean;
  sound_volume: number;
  notification_position: string;
  notification_duration_seconds: number;
};

export type VoiceSettings = {
  enabled: boolean;
  wake_word_enabled: boolean;
  wake_phrases: string[];
  activation_response: string;
  response_style: string;
  privacy_mode: string;
  cloud_ai_enabled: boolean;
  offline_only: boolean;
  push_to_talk: boolean;
  microphone_device: string;
  sensitivity: number;
  noise_filtering: boolean;
  voice_enabled: boolean;
  voice_volume: number;
  voice_speed: number;
  voice_gender: string;
  voice_language: string;
  activation_notification_enabled: boolean;
  listen_timeout_seconds: number;
};

export type VoiceStatus = {
  service_running: boolean;
  listener_running: boolean;
  microphone_status: string;
  mode: string;
  online: boolean;
  muted: boolean;
  last_wake_time: string | null;
  last_command: string | null;
  last_response: string | null;
  last_error: string | null;
  startup_ready_seconds: number | null;
};

export type SystemAlertSettings = {
  enabled: boolean;
  cpu_temperature_threshold_celsius: number;
  cpu_usage_threshold_percent: number;
  memory_threshold_percent: number;
  storage_threshold_percent: number;
  notification_enabled: boolean;
  sound_enabled: boolean;
  voice_enabled: boolean;
  repeat_interval_seconds: number;
};

export type ResourceManagerStatus = {
  mode: string;
  power_saving: boolean;
  thermal_protection: boolean;
  heavy_load: boolean;
  user_idle: boolean;
  battery_percent: number | null;
  is_charging: boolean | null;
  cpu_percent: number;
  ram_mb: number;
  process_cpu_percent: number;
  process_ram_mb: number;
  process_threads: number;
  network_bytes_sent: number;
  network_bytes_recv: number;
  disk_read_bytes: number;
  disk_write_bytes: number;
  health_score: number;
  last_evaluated_at: string | null;
};

export type WebsiteProfile = {
  id: number;
  name: string;
  url: string;
  field_mapping: Record<string, string>;
  navigation_rules: Record<string, unknown>;
  login_process: Record<string, unknown>;
  retry_policy: Record<string, unknown>;
  success_check: Record<string, unknown>;
  monitoring_enabled: boolean;
  monitoring_interval_seconds: number;
  created_at: string;
  updated_at: string;
};

export type WebsiteAnalysis = {
  name: string;
  url: string;
  login_forms: Array<Record<string, unknown>>;
  fields: Array<Record<string, unknown>>;
  field_mapping: Record<string, string>;
  buttons: Array<Record<string, unknown>>;
  dropdowns: Array<Record<string, unknown>>;
  captcha_present: boolean;
  navigation: Record<string, unknown>;
  retry_policy: Record<string, unknown>;
  success_check: Record<string, unknown>;
};

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

export function runCommand(command: string, autoConfirm = false) {
  return api<TaskApproval>("/commands", { method: "POST", body: JSON.stringify({ command, auto_confirm: autoConfirm }) });
}

export function confirmTask(taskId: number) {
  return api<Task>(`/tasks/${taskId}/confirm`, { method: "POST" });
}

export function approveTaskApproval(approvalId: number) {
  return api<TaskApproval>(`/task-approvals/${approvalId}/approve`, { method: "POST" });
}

export function editTaskApproval(approvalId: number, payload: { task_title?: string; date?: string; time?: string; trigger?: string; priority?: string }) {
  return api<TaskApproval>(`/task-approvals/${approvalId}/edit`, { method: "PUT", body: JSON.stringify(payload) });
}

export function rejectTaskApproval(approvalId: number, reason = "") {
  return api<TaskApproval>(`/task-approvals/${approvalId}/reject`, { method: "POST", body: JSON.stringify({ reason }) });
}
