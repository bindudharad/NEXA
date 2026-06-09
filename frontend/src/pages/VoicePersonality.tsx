import React from "react";
import { Mic2, Radio, RefreshCw, Save, Settings2, Sparkles, Volume2 } from "lucide-react";
import { Panel } from "../components/Panel";
import { api, type VoiceSettings, type VoiceStatus } from "../lib/api";

type AnyRecord = Record<string, any>;

const button = "inline-flex h-9 items-center justify-center gap-2 rounded-lg bg-amber-300 px-3 text-sm font-medium text-black hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-50";
const ghost = "inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-amber-200/15 px-3 text-sm text-amber-100 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50";
const input = "h-10 w-full rounded-lg border border-amber-200/10 bg-black/25 px-3 text-sm text-amber-50 outline-none placeholder:text-slate-500 focus:border-amber-300/50";

export function VoicePersonality() {
  const [dashboard, setDashboard] = React.useState<AnyRecord | null>(null);
  const [settings, setSettings] = React.useState<VoiceSettings | null>(null);
  const [status, setStatus] = React.useState<VoiceStatus | null>(null);
  const [error, setError] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [customName, setCustomName] = React.useState("Custom Assistant");
  const [customWake, setCustomWake] = React.useState("I'm listening.");
  const [customDone, setCustomDone] = React.useState("Done.");

  const refresh = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [nextDashboard, nextSettings, nextStatus] = await Promise.all([
        api<AnyRecord>("/voice/dashboard"),
        api<VoiceSettings>("/voice/settings"),
        api<VoiceStatus>("/voice/status")
      ]);
      setDashboard(nextDashboard);
      setSettings(nextSettings);
      setStatus(nextStatus);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load voice dashboard");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void refresh();
  }, [refresh]);

  async function updateSettings(patch: Partial<VoiceSettings>) {
    setLoading(true);
    setError("");
    try {
      await api<VoiceSettings>("/voice/settings", { method: "PUT", body: JSON.stringify(patch) });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update voice settings");
      setLoading(false);
    }
  }

  async function testWake() {
    setLoading(true);
    setError("");
    try {
      await api("/voice/wake", { method: "POST", body: JSON.stringify({ phrase: "Nexa", source: "voice_dashboard" }) });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Wake test failed");
      setLoading(false);
    }
  }

  async function createCustomPersonality() {
    setLoading(true);
    setError("");
    try {
      const created = await api<AnyRecord>("/voice/custom-personalities", {
        method: "POST",
        body: JSON.stringify({
          name: customName,
          greeting_style: "custom",
          wake_responses: splitCsv(customWake),
          completion_responses: splitCsv(customDone),
          reminder_responses: ["You have a reminder."],
          error_responses: ["I could not complete that."],
          notification_responses: {}
        })
      });
      await api<VoiceSettings>("/voice/settings", { method: "PUT", body: JSON.stringify({ response_style: "custom", custom_personality_id: created.id }) });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create custom personality");
      setLoading(false);
    }
  }

  const profiles = dashboard?.profiles ?? [];
  const custom = dashboard?.custom_personalities ?? [];
  const history = dashboard?.voice_history ?? [];
  const wakeHistory = dashboard?.wake_history ?? [];
  const stats = dashboard?.voice_statistics ?? {};

  return (
    <div className="space-y-5">
      <section className="flex flex-col gap-3 border-b border-amber-200/10 pb-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm text-amber-200/70"><Mic2 size={16} /> Voice Personality</div>
          <h1 className="mt-1 text-2xl font-semibold text-amber-50">Voice Dashboard</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-400">Configure Nexa's response style, wake behavior, local voice status, recent wake events, and custom assistant profiles.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className={ghost} onClick={refresh} disabled={loading}><RefreshCw size={16} /> Refresh</button>
          <button className={button} onClick={testWake} disabled={loading}><Radio size={16} /> Test Wake</button>
        </div>
      </section>

      {error && <div className="rounded-lg border border-red-400/25 bg-red-500/10 p-3 text-sm text-red-100">{error}</div>}

      <section className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <Panel title="Current Voice State">
          <div className="grid gap-3 sm:grid-cols-2">
            <Metric label="Personality" value={dashboard?.current_personality ?? settings?.response_style ?? "--"} />
            <Metric label="Microphone" value={status?.microphone_status ?? dashboard?.voice_status?.microphone_status ?? "--"} />
            <Metric label="Wake Word" value={dashboard?.wake_word_status?.enabled ? "Enabled" : "Disabled"} />
            <Metric label="Mode" value={status?.mode ?? dashboard?.voice_status?.mode ?? "--"} />
            <Metric label="Offline Ready" value={dashboard?.offline_ready ? "Yes" : "No"} />
            <Metric label="Listener" value={status?.listener_running ? "Running" : "Idle"} />
          </div>
        </Panel>

        <Panel title="Voice Controls">
          {settings ? (
            <div className="grid gap-3 md:grid-cols-2">
              <label className="grid gap-2 text-sm text-slate-300">
                Personality
                <select className={input} value={settings.response_style} onChange={(event) => updateSettings({ response_style: event.target.value })}>
                  {["professional", "friendly", "jarvis", "minimal", "funny", "silent", "custom"].map((item) => <option key={item} value={item}>{labelize(item)}</option>)}
                </select>
              </label>
              <label className="grid gap-2 text-sm text-slate-300">
                Wake Response
                <select className={input} value={settings.activation_response} onChange={(event) => updateSettings({ activation_response: event.target.value })}>
                  {["Yes, how may I assist you?", "Hey! How can I help?", "At your service.", "Yes?", "You summoned me?", ""].map((item) => <option key={item || "silent"} value={item}>{item || "Silent"}</option>)}
                </select>
              </label>
              <Toggle label="Voice Responses" checked={settings.voice_enabled} onChange={(value) => updateSettings({ voice_enabled: value })} />
              <Toggle label="Wake Word" checked={settings.wake_word_enabled} onChange={(value) => updateSettings({ wake_word_enabled: value })} />
              <Toggle label="Offline Only" checked={settings.offline_only} onChange={(value) => updateSettings({ offline_only: value })} />
              <Toggle label="Disable Cloud AI" checked={!settings.cloud_ai_enabled} onChange={(value) => updateSettings({ cloud_ai_enabled: !value })} />
            </div>
          ) : <Empty text="Voice settings are loading." />}
        </Panel>
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <Panel title="Built-In Profiles">
          <div className="space-y-2">
            {profiles.map((profile: AnyRecord) => (
              <button key={profile.profile_key} className={`w-full rounded-lg border p-3 text-left transition ${settings?.response_style === profile.profile_key ? "border-amber-300/50 bg-amber-300/10" : "border-white/10 bg-black/20 hover:bg-white/10"}`} onClick={() => updateSettings({ response_style: profile.profile_key })} disabled={loading || profile.profile_key === "custom"}>
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium text-amber-100">{profile.name}</span>
                  <span className="text-xs text-slate-500">{profile.style}</span>
                </div>
                <p className="mt-1 text-sm text-slate-400">{profile.description}</p>
              </button>
            ))}
          </div>
        </Panel>

        <Panel title="Custom Personality">
          <div className="grid gap-3">
            <input className={input} value={customName} onChange={(event) => setCustomName(event.target.value)} placeholder="Profile name" />
            <input className={input} value={customWake} onChange={(event) => setCustomWake(event.target.value)} placeholder="Wake responses, comma separated" />
            <input className={input} value={customDone} onChange={(event) => setCustomDone(event.target.value)} placeholder="Completion responses, comma separated" />
            <button className={button} onClick={createCustomPersonality} disabled={loading || !customName.trim()}><Save size={16} /> Save Custom Profile</button>
            <div className="space-y-2">
              {custom.length === 0 ? <Empty text="No custom personalities yet." /> : custom.slice(0, 5).map((item: AnyRecord) => (
                <button key={item.id} className={`w-full rounded-lg border p-3 text-left text-sm ${settings?.custom_personality_id === item.id ? "border-amber-300/50 bg-amber-300/10" : "border-white/10 bg-black/20"}`} onClick={() => updateSettings({ response_style: "custom", custom_personality_id: item.id })}>
                  <div className="font-medium text-amber-100">{item.name}</div>
                  <div className="mt-1 text-slate-400">{(item.wake_responses ?? []).join(", ") || "Custom wake response"}</div>
                </button>
              ))}
            </div>
          </div>
        </Panel>

        <Panel title="Voice Statistics">
          <div className="grid gap-3">
            <Metric label="Wake Events" value={stats.wake_events ?? 0} />
            <Metric label="Commands" value={stats.commands ?? 0} />
            <Metric label="Spoken Responses" value={stats.spoken_responses ?? 0} />
            <Metric label="Errors" value={stats.errors ?? 0} />
            <Metric label="Recent Profiles" value={(stats.personalities ?? []).join(", ") || "--"} />
          </div>
        </Panel>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Panel title="Wake Word History">
          <History rows={wakeHistory} empty="No wake word events recorded yet." />
        </Panel>
        <Panel title="Recent Voice Responses">
          <History rows={history} empty="No voice responses recorded yet." />
        </Panel>
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-black/20 p-3 text-sm">
      <span className="min-w-0 truncate text-slate-400">{label}</span>
      <span className="shrink-0 font-medium text-amber-100">{value}</span>
    </div>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return (
    <label className="flex h-10 items-center justify-between gap-3 rounded-lg border border-white/10 bg-black/20 px-3 text-sm text-slate-300">
      <span className="flex items-center gap-2"><Settings2 size={15} /> {label}</span>
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
    </label>
  );
}

function History({ rows, empty }: { rows: AnyRecord[]; empty: string }) {
  if (rows.length === 0) {
    return <Empty text={empty} />;
  }
  return (
    <div className="max-h-[420px] space-y-2 overflow-auto pr-1">
      {rows.slice(0, 20).map((row: AnyRecord) => (
        <div key={`${row.id}-${row.created_at}`} className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm">
          <div className="flex items-center justify-between gap-3">
            <span className="font-medium text-amber-100">{row.event_type ?? row.phrase ?? "Voice event"}</span>
            <span className="shrink-0 text-xs text-slate-500">{formatDate(row.created_at)}</span>
          </div>
          <p className="mt-1 text-slate-300">{row.response_text || row.input_text || row.status || "Recorded"}</p>
          <div className="mt-2 flex items-center gap-2 text-xs text-slate-500"><Volume2 size={13} /> {row.personality ?? row.source ?? "voice"}</div>
        </div>
      ))}
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm text-slate-500">{text}</div>;
}

function splitCsv(value: string) {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function labelize(value: string) {
  return value.split("_").map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" ");
}

function formatDate(value: string | undefined) {
  if (!value) {
    return "--";
  }
  return new Date(value).toLocaleString();
}
