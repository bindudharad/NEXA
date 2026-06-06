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
  return api<Task>("/commands", { method: "POST", body: JSON.stringify({ command, auto_confirm: autoConfirm }) });
}

export function confirmTask(taskId: number) {
  return api<Task>(`/tasks/${taskId}/confirm`, { method: "POST" });
}
