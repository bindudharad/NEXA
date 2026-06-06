import React from "react";
import { Panel } from "../components/Panel";
import { api, type BatteryAlertSettings, type BatteryAlertStatus } from "../lib/api";

export function SettingsPage() {
  const [settings, setSettings] = React.useState<BatteryAlertSettings | null>(null);
  const [testStatus, setTestStatus] = React.useState<BatteryAlertStatus | null>(null);
  const [customThreshold, setCustomThreshold] = React.useState("");
  const thresholds = [10, 15, 20, 25, 30];
  const intervals = [
    { label: "1 minute", value: 60 },
    { label: "2 minutes", value: 120 },
    { label: "5 minutes", value: 300 },
    { label: "10 minutes", value: 600 }
  ];

  React.useEffect(() => {
    api<BatteryAlertSettings>("/battery-alert/settings").then(setSettings);
  }, []);

  async function update(patch: Partial<BatteryAlertSettings>) {
    const next = await api<BatteryAlertSettings>("/battery-alert/settings", { method: "PUT", body: JSON.stringify(patch) });
    setSettings(next);
  }

  async function simulate(battery_percent: number | null, is_charging: boolean | null) {
    const next = await api<BatteryAlertStatus>("/battery-alert/test/simulate", { method: "POST", body: JSON.stringify({ battery_percent, is_charging }) });
    setTestStatus(next);
  }

  async function clearSimulation() {
    const next = await api<BatteryAlertStatus>("/battery-alert/test/clear", { method: "POST" });
    setTestStatus(next);
  }

  if (!settings) {
    return <Panel title="Nexa Settings"><div className="text-sm text-slate-400">Loading settings...</div></Panel>;
  }

  return (
    <div className="space-y-5">
      <Panel title="Nexa Settings">
        <div className="grid max-w-xl gap-3 text-sm">
          <label className="nexa-card flex items-center justify-between gap-4 rounded-xl p-3">
            Dangerous actions require confirmation
            <input type="checkbox" checked readOnly />
          </label>
          <label className="nexa-card flex items-center justify-between gap-4 rounded-xl p-3">
            Local Ollama support
            <input type="checkbox" checked readOnly />
          </label>
        </div>
      </Panel>
      <Panel title="Battery Alert Settings">
        <div className="grid gap-5 xl:grid-cols-[1fr_1fr]">
          <div className="space-y-3">
            <Toggle label="Enable Alert" checked={settings.enabled} onChange={(value) => update({ enabled: value })} />
            <Toggle label="Enable Voice Alert" checked={settings.voice_enabled} onChange={(value) => update({ voice_enabled: value })} />
            <Toggle label="Enable Sound Alert" checked={settings.sound_enabled} onChange={(value) => update({ sound_enabled: value })} />
            <Toggle label="Enable Notification" checked={settings.notification_enabled} onChange={(value) => update({ notification_enabled: value })} />
          </div>
          <div className="space-y-4">
            <div>
              <div className="mb-2 text-sm font-medium text-amber-100">Battery Threshold</div>
              <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
                {thresholds.map((value) => (
                  <button key={value} className={`h-10 rounded-xl text-sm ${settings.threshold_percent === value ? "bg-accent text-obsidian" : "nexa-card text-slate-200"}`} onClick={() => update({ threshold_percent: value })}>{value}%</button>
                ))}
              </div>
              <div className="mt-2 grid grid-cols-[1fr_90px] gap-2">
                <input className="nexa-input h-10 rounded-xl px-3" inputMode="numeric" value={customThreshold} onChange={(event) => setCustomThreshold(event.target.value)} placeholder="Custom value" />
                <button className="rounded-xl bg-accent text-sm text-obsidian" onClick={() => update({ threshold_percent: Number(customThreshold) })}>Apply</button>
              </div>
            </div>
            <div>
              <div className="mb-2 text-sm font-medium text-amber-100">Repeat Interval</div>
              <div className="grid grid-cols-2 gap-2">
                {intervals.map((item) => (
                  <button key={item.value} className={`h-10 rounded-xl text-sm ${settings.repeat_interval_seconds === item.value ? "bg-accent text-obsidian" : "nexa-card text-slate-200"}`} onClick={() => update({ repeat_interval_seconds: item.value })}>{item.label}</button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </Panel>
      <Panel title="Battery Alert Testing">
        <div className="grid gap-3">
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-4">
            <button className="h-10 rounded-xl bg-accent text-sm text-obsidian" onClick={() => simulate(20, false)}>Simulate 20%</button>
            <button className="h-10 rounded-xl bg-accent text-sm text-obsidian" onClick={() => simulate(10, false)}>Simulate 10%</button>
            <button className="h-10 rounded-xl bg-emerald-400 text-sm text-obsidian" onClick={() => simulate(20, true)}>Simulate Charging</button>
            <button className="nexa-card h-10 rounded-xl text-sm text-slate-200" onClick={clearSimulation}>Clear Test</button>
          </div>
          <div className="nexa-card rounded-xl p-3 text-sm text-slate-300">
            Status: {testStatus ? `${testStatus.battery_percent ?? "Unknown"}% / ${testStatus.is_charging ? "Charging" : "Not charging"} / ${testStatus.alert_active ? "Alert active" : "Idle"}` : "No simulation active"}
          </div>
        </div>
      </Panel>
    </div>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return (
    <label className="nexa-card flex items-center justify-between gap-4 rounded-xl p-3 text-sm">
      {label}
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
    </label>
  );
}
