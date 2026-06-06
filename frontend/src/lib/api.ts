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

export type GpuMonitorSettings = {
  enabled: boolean;
  threshold_celsius: number;
  sound_enabled: boolean;
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
