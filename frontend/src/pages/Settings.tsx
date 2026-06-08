import React from "react";
import { Panel } from "../components/Panel";
import { api, type AlertSettings, type BatteryAlertSettings, type BatteryAlertStatus, type GpuMonitorSettings, type GpuMonitorStatus, type PowerMonitorSettings, type PowerMonitorStatus, type SystemAlertSettings, type VoiceSettings, type VoiceStatus } from "../lib/api";

export function SettingsPage() {
  const [settings, setSettings] = React.useState<BatteryAlertSettings | null>(null);
  const [testStatus, setTestStatus] = React.useState<BatteryAlertStatus | null>(null);
  const [gpuSettings, setGpuSettings] = React.useState<GpuMonitorSettings | null>(null);
  const [gpuTestStatus, setGpuTestStatus] = React.useState<GpuMonitorStatus | null>(null);
  const [alertSettings, setAlertSettings] = React.useState<AlertSettings | null>(null);
  const [systemAlertSettings, setSystemAlertSettings] = React.useState<SystemAlertSettings | null>(null);
  const [powerSettings, setPowerSettings] = React.useState<PowerMonitorSettings | null>(null);
  const [powerTestStatus, setPowerTestStatus] = React.useState<PowerMonitorStatus | null>(null);
  const [voiceSettings, setVoiceSettings] = React.useState<VoiceSettings | null>(null);
  const [voiceStatus, setVoiceStatus] = React.useState<VoiceStatus | null>(null);
  const [wakePhrases, setWakePhrases] = React.useState("");
  const [customThreshold, setCustomThreshold] = React.useState("");
  const [customGpuThreshold, setCustomGpuThreshold] = React.useState("");
  const thresholds = [10, 15, 20, 25, 30];
  const gpuThresholds = [40, 50, 60, 70, 80];
  const intervals = [
    { label: "1 minute", value: 60 },
    { label: "2 minutes", value: 120 },
    { label: "5 minutes", value: 300 },
    { label: "10 minutes", value: 600 }
  ];

  React.useEffect(() => {
    api<BatteryAlertSettings>("/battery-alert/settings").then(setSettings);
    api<GpuMonitorSettings>("/gpu-monitor/settings").then(setGpuSettings);
    api<AlertSettings>("/alert-settings").then(setAlertSettings);
    api<SystemAlertSettings>("/system-alerts/settings").then(setSystemAlertSettings);
    api<PowerMonitorSettings>("/power-monitor/settings").then(setPowerSettings);
    api<VoiceSettings>("/voice/settings").then((next) => {
      setVoiceSettings(next);
      setWakePhrases(next.wake_phrases.join(", "));
    });
    api<VoiceStatus>("/voice/status").then(setVoiceStatus);
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

  async function updateGpu(patch: Partial<GpuMonitorSettings>) {
    const next = await api<GpuMonitorSettings>("/gpu-monitor/settings", { method: "PUT", body: JSON.stringify(patch) });
    setGpuSettings(next);
  }

  async function simulateGpu(temperature_celsius: number) {
    const next = await api<GpuMonitorStatus>("/gpu-monitor/test/simulate", { method: "POST", body: JSON.stringify({ temperature_celsius }) });
    setGpuTestStatus(next);
  }

  async function clearGpuSimulation() {
    const next = await api<GpuMonitorStatus>("/gpu-monitor/test/clear", { method: "POST" });
    setGpuTestStatus(next);
  }

  async function updateAlertSettings(patch: Partial<AlertSettings>) {
    const next = await api<AlertSettings>("/alert-settings", { method: "PUT", body: JSON.stringify(patch) });
    setAlertSettings(next);
  }

  async function updateSystemAlerts(patch: Partial<SystemAlertSettings>) {
    const next = await api<SystemAlertSettings>("/system-alerts/settings", { method: "PUT", body: JSON.stringify(patch) });
    setSystemAlertSettings(next);
  }
  async function updatePowerSettings(patch: Partial<PowerMonitorSettings>) {
    const next = await api<PowerMonitorSettings>("/power-monitor/settings", { method: "PUT", body: JSON.stringify(patch) });
    setPowerSettings(next);
  }

  async function simulatePower(battery_percent: number, is_charging: boolean) {
    const next = await api<PowerMonitorStatus>("/power-monitor/test/simulate", { method: "POST", body: JSON.stringify({ battery_percent, is_charging }) });
    setPowerTestStatus(next);
  }
  async function updateVoiceSettings(patch: Partial<VoiceSettings>) {
    const next = await api<VoiceSettings>("/voice/settings", { method: "PUT", body: JSON.stringify(patch) });
    setVoiceSettings(next);
    setWakePhrases(next.wake_phrases.join(", "));
    setVoiceStatus(await api<VoiceStatus>("/voice/status"));
  }

  async function testWake() {
    await api("/voice/wake", { method: "POST", body: JSON.stringify({ phrase: "Nexa", source: "settings_test" }) });
    setVoiceStatus(await api<VoiceStatus>("/voice/status"));
  }

  if (!settings || !gpuSettings || !alertSettings || !systemAlertSettings || !powerSettings || !voiceSettings) {
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
      <Panel title="Global Alert Settings">
        <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
          <div className="space-y-3">
            <Toggle label="Enable Sounds" checked={alertSettings.sound_enabled} onChange={(value) => updateAlertSettings({ sound_enabled: value })} />
            <Toggle label="Enable Voice Alerts" checked={alertSettings.voice_enabled} onChange={(value) => updateAlertSettings({ voice_enabled: value })} />
          </div>
          <div className="grid gap-3">
            <label className="grid gap-2 text-sm text-slate-300">
              Sound Volume
              <input className="w-full accent-amber-300" type="range" min="0" max="100" value={alertSettings.sound_volume} onChange={(event) => updateAlertSettings({ sound_volume: Number(event.target.value) })} />
            </label>
            <label className="grid gap-2 text-sm text-slate-300">
              Notification Duration
              <input className="nexa-input h-10 rounded-xl px-3" type="number" min="1" max="60" value={alertSettings.notification_duration_seconds} onChange={(event) => updateAlertSettings({ notification_duration_seconds: Number(event.target.value) })} />
            </label>
          </div>
        </div>
      </Panel>
      <Panel title="Voice Assistant Settings">
        <div className="grid gap-5 xl:grid-cols-[1fr_1fr]">
          <div className="space-y-3">
            <Toggle label="Enable Voice Assistant" checked={voiceSettings.enabled} onChange={(value) => updateVoiceSettings({ enabled: value })} />
            <Toggle label="Wake Word Detection" checked={voiceSettings.wake_word_enabled} onChange={(value) => updateVoiceSettings({ wake_word_enabled: value })} />
            <Toggle label="Voice Responses" checked={voiceSettings.voice_enabled} onChange={(value) => updateVoiceSettings({ voice_enabled: value })} />
            <Toggle label="Push to Talk" checked={voiceSettings.push_to_talk} onChange={(value) => updateVoiceSettings({ push_to_talk: value })} />
            <Toggle label="Offline Only" checked={voiceSettings.offline_only} onChange={(value) => updateVoiceSettings({ offline_only: value })} />
            <Toggle label="Disable Cloud AI" checked={!voiceSettings.cloud_ai_enabled} onChange={(value) => updateVoiceSettings({ cloud_ai_enabled: !value })} />
            <Toggle label="Activation Notification" checked={voiceSettings.activation_notification_enabled} onChange={(value) => updateVoiceSettings({ activation_notification_enabled: value })} />
          </div>
          <div className="grid gap-3">
            <label className="grid gap-2 text-sm text-slate-300">
              Wake Phrases
              <input className="nexa-input h-10 rounded-xl px-3" value={wakePhrases} onChange={(event) => setWakePhrases(event.target.value)} onBlur={() => updateVoiceSettings({ wake_phrases: wakePhrases.split(",").map((item) => item.trim()).filter(Boolean) })} />
            </label>
            <label className="grid gap-2 text-sm text-slate-300">
              Activation Response
              <select className="nexa-input h-10 rounded-xl px-3" value={voiceSettings.activation_response} onChange={(event) => updateVoiceSettings({ activation_response: event.target.value })}>
                {["Nexa activated.", "Yes?", "I'm listening.", "How can I help?", "Ready.", "What would you like me to do?"].map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
            <label className="grid gap-2 text-sm text-slate-300">
              Voice Personality
              <select className="nexa-input h-10 rounded-xl px-3" value={voiceSettings.response_style} onChange={(event) => updateVoiceSettings({ response_style: event.target.value })}>
                {["professional", "friendly", "jarvis", "minimal", "funny", "silent", "custom"].map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
            <label className="grid gap-2 text-sm text-slate-300">
              Privacy Mode
              <select className="nexa-input h-10 rounded-xl px-3" value={voiceSettings.privacy_mode} onChange={(event) => updateVoiceSettings({ privacy_mode: event.target.value })}>
                {["wake_word_only", "push_to_talk", "always_listening", "offline_only", "local_processing_only"].map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
            <label className="grid gap-2 text-sm text-slate-300">
              Sensitivity
              <input className="w-full accent-amber-300" type="range" min="0.1" max="1" step="0.05" value={voiceSettings.sensitivity} onChange={(event) => updateVoiceSettings({ sensitivity: Number(event.target.value) })} />
            </label>
            <div className="grid gap-2 sm:grid-cols-2">
              <NumberSetting label="Voice Volume" value={voiceSettings.voice_volume} onChange={(value) => updateVoiceSettings({ voice_volume: value })} />
              <NumberSetting label="Voice Speed" value={voiceSettings.voice_speed} onChange={(value) => updateVoiceSettings({ voice_speed: value })} />
            </div>
            <div className="nexa-card rounded-xl p-3 text-sm text-slate-300">
              Microphone: {voiceStatus?.microphone_status ?? "unknown"} / Mode: {voiceStatus?.mode ?? "offline"} / Listener: {voiceStatus?.listener_running ? "running" : "stopped"}
            </div>
            <button className="h-10 rounded-xl bg-accent text-sm text-obsidian" onClick={testWake}>Test Wake Response</button>
          </div>
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
      <Panel title="Power Monitor Settings">
        <div className="grid gap-5 xl:grid-cols-[1fr_1fr]">
          <div className="space-y-3">
            <Toggle label="Power Monitor Enabled" checked={powerSettings.enabled} onChange={(value) => updatePowerSettings({ enabled: value })} />
            <Toggle label="Charger Connected Alerts" checked={powerSettings.charger_connected_alerts} onChange={(value) => updatePowerSettings({ charger_connected_alerts: value })} />
            <Toggle label="Charger Disconnected Alerts" checked={powerSettings.charger_disconnected_alerts} onChange={(value) => updatePowerSettings({ charger_disconnected_alerts: value })} />
            <Toggle label="95% Battery Alert" checked={powerSettings.battery_95_alert_enabled} onChange={(value) => updatePowerSettings({ battery_95_alert_enabled: value })} />
            <Toggle label="100% Battery Alert" checked={powerSettings.battery_full_alert_enabled} onChange={(value) => updatePowerSettings({ battery_full_alert_enabled: value })} />
            <Toggle label="Power Fluctuation Detection" checked={powerSettings.fluctuation_detection_enabled} onChange={(value) => updatePowerSettings({ fluctuation_detection_enabled: value })} />
            <Toggle label="Power Voice Alerts" checked={powerSettings.voice_enabled} onChange={(value) => updatePowerSettings({ voice_enabled: value })} />
            <Toggle label="Power Sound Alerts" checked={powerSettings.sound_enabled} onChange={(value) => updatePowerSettings({ sound_enabled: value })} />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <NumberSetting label="Low Battery %" value={powerSettings.low_battery_threshold_percent} onChange={(value) => updatePowerSettings({ low_battery_threshold_percent: value })} />
            <NumberSetting label="Critical Battery %" value={powerSettings.critical_battery_threshold_percent} onChange={(value) => updatePowerSettings({ critical_battery_threshold_percent: value })} />
            <NumberSetting label="Health Charge Alert %" value={powerSettings.battery_95_threshold_percent} onChange={(value) => updatePowerSettings({ battery_95_threshold_percent: value })} />
            <NumberSetting label="Repeat Seconds" value={powerSettings.low_repeat_interval_seconds} onChange={(value) => updatePowerSettings({ low_repeat_interval_seconds: value })} />
            <NumberSetting label="Event Volume" value={powerSettings.event_sound_volume} onChange={(value) => updatePowerSettings({ event_sound_volume: value })} />
            <NumberSetting label="Warning Volume" value={powerSettings.warning_sound_volume} onChange={(value) => updatePowerSettings({ warning_sound_volume: value })} />
          </div>
        </div>
      </Panel>
      <Panel title="Power Monitor Testing">
        <div className="grid gap-3">
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-4">
            <button className="h-10 rounded-xl bg-emerald-400 text-sm text-obsidian" onClick={() => simulatePower(45, true)}>Connect Charger</button>
            <button className="h-10 rounded-xl bg-accent text-sm text-obsidian" onClick={() => simulatePower(44, false)}>Disconnect Charger</button>
            <button className="h-10 rounded-xl bg-accent text-sm text-obsidian" onClick={() => simulatePower(95, true)}>Simulate 95%</button>
            <button className="h-10 rounded-xl bg-red-400 text-sm text-obsidian" onClick={() => simulatePower(10, false)}>Critical 10%</button>
          </div>
          <div className="nexa-card rounded-xl p-3 text-sm text-slate-300">
            Status: {powerTestStatus ? `${powerTestStatus.battery_percent ?? "Unknown"}% / ${powerTestStatus.is_charging ? "Charging" : "On battery"} / ${powerTestStatus.last_event_type ?? "No event"}` : "No power simulation active"}
          </div>
        </div>
      </Panel>
      <Panel title="GPU Monitoring Settings">
        <div className="grid gap-5 xl:grid-cols-[1fr_1fr]">
          <div className="space-y-3">
            <Toggle label="GPU Monitoring Enabled" checked={gpuSettings.enabled} onChange={(value) => updateGpu({ enabled: value })} />
            <Toggle label="Enable Sound Alert" checked={gpuSettings.sound_enabled} onChange={(value) => updateGpu({ sound_enabled: value })} />
            <Toggle label="Enable Voice Alert" checked={gpuSettings.voice_enabled} onChange={(value) => updateGpu({ voice_enabled: value })} />
            <Toggle label="Enable Notification" checked={gpuSettings.notification_enabled} onChange={(value) => updateGpu({ notification_enabled: value })} />
          </div>
          <div className="space-y-4">
            <div>
              <div className="mb-2 text-sm font-medium text-amber-100">Temperature Threshold</div>
              <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
                {gpuThresholds.map((value) => (
                  <button key={value} className={`h-10 rounded-xl text-sm ${gpuSettings.threshold_celsius === value ? "bg-accent text-obsidian" : "nexa-card text-slate-200"}`} onClick={() => updateGpu({ threshold_celsius: value })}>{value}°C</button>
                ))}
              </div>
              <div className="mt-2 grid grid-cols-[1fr_90px] gap-2">
                <input className="nexa-input h-10 rounded-xl px-3" inputMode="numeric" value={customGpuThreshold} onChange={(event) => setCustomGpuThreshold(event.target.value)} placeholder="Custom value" />
                <button className="rounded-xl bg-accent text-sm text-obsidian" onClick={() => updateGpu({ threshold_celsius: Number(customGpuThreshold) })}>Apply</button>
              </div>
            </div>
            <div>
              <div className="mb-2 text-sm font-medium text-amber-100">Repeat Interval</div>
              <div className="grid grid-cols-2 gap-2">
                {[{ label: "1 minute", value: 60 }, { label: "5 minutes", value: 300 }, { label: "10 minutes", value: 600 }, { label: "15 minutes", value: 900 }].map((item) => (
                  <button key={item.value} className={`h-10 rounded-xl text-sm ${gpuSettings.repeat_interval_seconds === item.value ? "bg-accent text-obsidian" : "nexa-card text-slate-200"}`} onClick={() => updateGpu({ repeat_interval_seconds: item.value })}>{item.label}</button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </Panel>
      <Panel title="GPU Monitor Testing">
        <div className="grid gap-3">
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-4">
            <button className="h-10 rounded-xl bg-accent text-sm text-obsidian" onClick={() => simulateGpu(55)}>Simulate 55°C</button>
            <button className="h-10 rounded-xl bg-accent text-sm text-obsidian" onClick={() => simulateGpu(65)}>Simulate 65°C</button>
            <button className="h-10 rounded-xl bg-accent text-sm text-obsidian" onClick={() => simulateGpu(75)}>Simulate 75°C</button>
            <button className="nexa-card h-10 rounded-xl text-sm text-slate-200" onClick={clearGpuSimulation}>Clear Test</button>
          </div>
          <div className="nexa-card rounded-xl p-3 text-sm text-slate-300">
            Status: {gpuTestStatus ? `${gpuTestStatus.gpu_name ?? "Unknown"} / ${gpuTestStatus.temperature_celsius ?? "N/A"}°C / ${gpuTestStatus.alert_active ? "Alert active" : "Idle"}` : "No simulation active"}
          </div>
        </div>
      </Panel>
      <Panel title="System Resource Alert Settings">
        <div className="grid gap-5 xl:grid-cols-[1fr_1fr]">
          <div className="space-y-3">
            <Toggle label="System Resource Alerts" checked={systemAlertSettings.enabled} onChange={(value) => updateSystemAlerts({ enabled: value })} />
            <Toggle label="Enable Notifications" checked={systemAlertSettings.notification_enabled} onChange={(value) => updateSystemAlerts({ notification_enabled: value })} />
            <Toggle label="Enable Sounds" checked={systemAlertSettings.sound_enabled} onChange={(value) => updateSystemAlerts({ sound_enabled: value })} />
            <Toggle label="Enable Voice" checked={systemAlertSettings.voice_enabled} onChange={(value) => updateSystemAlerts({ voice_enabled: value })} />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <NumberSetting label="CPU Temp °C" value={systemAlertSettings.cpu_temperature_threshold_celsius} onChange={(value) => updateSystemAlerts({ cpu_temperature_threshold_celsius: value })} />
            <NumberSetting label="CPU Usage %" value={systemAlertSettings.cpu_usage_threshold_percent} onChange={(value) => updateSystemAlerts({ cpu_usage_threshold_percent: value })} />
            <NumberSetting label="Memory %" value={systemAlertSettings.memory_threshold_percent} onChange={(value) => updateSystemAlerts({ memory_threshold_percent: value })} />
            <NumberSetting label="Storage %" value={systemAlertSettings.storage_threshold_percent} onChange={(value) => updateSystemAlerts({ storage_threshold_percent: value })} />
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

function NumberSetting({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return (
    <label className="grid gap-2 text-sm text-slate-300">
      {label}
      <input className="nexa-input h-10 rounded-xl px-3" type="number" value={value} onChange={(event) => onChange(Number(event.target.value))} />
    </label>
  );
}
