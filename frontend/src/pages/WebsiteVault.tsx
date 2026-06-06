import React from "react";
import { Clock, Download, Eye, Globe, KeyRound, Play, Save, Search, Trash2, Upload } from "lucide-react";
import { Panel } from "../components/Panel";
import { api, type WebsiteAnalysis, type WebsiteProfile } from "../lib/api";

export function WebsiteVault() {
  const [profiles, setProfiles] = React.useState<WebsiteProfile[]>([]);
  const [analysis, setAnalysis] = React.useState<WebsiteAnalysis | null>(null);
  const [name, setName] = React.useState("Contineo");
  const [url, setUrl] = React.useState("");
  const [credentials, setCredentials] = React.useState('{"username":"","password":""}');
  const [kcetApp, setKcetApp] = React.useState("");
  const [kcetDob, setKcetDob] = React.useState("");
  const [message, setMessage] = React.useState("");

  React.useEffect(() => {
    loadProfiles();
  }, []);

  async function loadProfiles() {
    setProfiles(await api<WebsiteProfile[]>("/website-profiles"));
  }

  async function analyze() {
    setMessage("");
    const result = await api<WebsiteAnalysis>("/website-profiles/analyze", { method: "POST", body: JSON.stringify({ name, url }) });
    setAnalysis(result);
  }

  async function saveProfile() {
    if (!analysis) return;
    const parsedCredentials = safeJson(credentials);
    const saved = await api<WebsiteProfile>("/website-profiles", {
      method: "POST",
      body: JSON.stringify({
        name: analysis.name,
        url: analysis.url,
        field_mapping: analysis.field_mapping,
        navigation_rules: analysis.navigation,
        login_process: { submit_selector: String(analysis.login_forms[0]?.submit_selector ?? "button[type=submit]") },
        retry_policy: { max_retries: 5, retry_interval_seconds: 5, backoff_multiplier: 2 },
        success_check: analysis.success_check,
        credentials: parsedCredentials
      })
    });
    setMessage(`Saved ${saved.name}`);
    await loadProfiles();
  }

  async function testLogin(profile: WebsiteProfile) {
    const result = await api<Record<string, unknown>>(`/website-profiles/${profile.id}/auto-login`, { method: "POST" });
    setMessage(`${profile.name}: ${String(result.status ?? "unknown")}`);
    await loadProfiles();
  }

  async function openProfile(profile: WebsiteProfile) {
    const result = await api<Record<string, unknown>>("/websites/open", { method: "POST", body: JSON.stringify({ name: profile.name }) });
    setMessage(`${profile.name}: ${String(result.status ?? result.message ?? "opened")}`);
  }

  async function toggleMonitor(profile: WebsiteProfile) {
    const next = await api<WebsiteProfile>(`/website-profiles/${profile.id}/monitoring`, { method: "PUT", body: JSON.stringify({ enabled: !profile.monitoring_enabled, interval_seconds: profile.monitoring_interval_seconds || 300 }) });
    setProfiles((current) => current.map((item) => (item.id === next.id ? next : item)));
  }

  async function deleteProfile(profile: WebsiteProfile) {
    await api(`/website-profiles/${profile.id}`, { method: "DELETE" });
    setMessage(`Deleted ${profile.name}`);
    await loadProfiles();
  }

  async function exportProfile(profile: WebsiteProfile) {
    const exported = await api<Record<string, unknown>>(`/website-profiles/${profile.id}/export`);
    setMessage(JSON.stringify(exported).slice(0, 240));
  }

  async function viewHistory(profile: WebsiteProfile) {
    const history = await api<Array<Record<string, unknown>>>(`/website-profiles/${profile.id}/history`);
    setMessage(JSON.stringify(history.slice(0, 5)).slice(0, 480));
  }

  async function updateCredentials(profile: WebsiteProfile) {
    await api(`/website-profiles/${profile.id}/credentials`, { method: "PUT", body: JSON.stringify({ credentials: safeJson(credentials) }) });
    setMessage(`Credentials updated for ${profile.name}`);
  }

  async function runKcet() {
    const result = await api<Record<string, unknown>>("/websites/kcet-result", { method: "POST", body: JSON.stringify({ application_number: kcetApp || null, date_of_birth: kcetDob || null, save_profile: Boolean(kcetApp && kcetDob), url: url || null }) });
    setMessage(JSON.stringify(result));
    await loadProfiles();
  }

  return (
    <div className="space-y-5">
      <Panel title="Website Vault">
        <div className="grid gap-3 xl:grid-cols-[1fr_auto]">
          <div className="grid gap-2 md:grid-cols-2">
            <input className="nexa-input h-11 rounded-xl px-3" value={name} onChange={(event) => setName(event.target.value)} placeholder="Website name" />
            <input className="nexa-input h-11 rounded-xl px-3" value={url} onChange={(event) => setUrl(event.target.value)} placeholder="Website URL" />
          </div>
          <button className="flex h-11 items-center justify-center gap-2 rounded-xl bg-accent px-4 font-semibold text-obsidian" onClick={analyze}>
            <Search size={17} />
            Analyze
          </button>
        </div>
        {analysis && (
          <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_360px]">
            <div className="nexa-card rounded-2xl p-4">
              <div className="mb-3 text-sm font-semibold text-amber-100">Website Profile Detected</div>
              <div className="grid gap-2 md:grid-cols-2">
                <Info label="Fields" value={String(analysis.fields.length)} />
                <Info label="Buttons" value={String(analysis.buttons.length)} />
                <Info label="Dropdowns" value={String(analysis.dropdowns.length)} />
                <Info label="Captcha" value={analysis.captcha_present ? "Detected" : "Not detected"} />
              </div>
              <pre className="mt-3 max-h-56 overflow-auto rounded-xl bg-black/25 p-3 text-xs text-slate-300">{JSON.stringify(analysis.field_mapping, null, 2)}</pre>
            </div>
            <div className="nexa-card rounded-2xl p-4">
              <div className="mb-3 text-sm font-semibold text-amber-100">Save Website?</div>
              <textarea className="nexa-input min-h-32 rounded-xl p-3 text-xs" value={credentials} onChange={(event) => setCredentials(event.target.value)} />
              <button className="mt-3 flex h-10 w-full items-center justify-center gap-2 rounded-xl bg-accent px-3 text-sm font-semibold text-obsidian" onClick={saveProfile}>
                <Save size={16} />
                Save Profile
              </button>
            </div>
          </div>
        )}
        {message && <div className="mt-4 rounded-xl border border-amber-200/20 bg-amber-300/10 p-3 text-sm text-amber-100">{message}</div>}
      </Panel>

      <Panel title="Saved Websites">
        <div className="grid gap-3">
          {profiles.map((profile) => (
            <div key={profile.id} className="nexa-card rounded-2xl p-4">
              <div className="grid gap-3 xl:grid-cols-[1fr_auto]">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 text-lg font-semibold text-amber-100"><Globe size={18} />{profile.name}</div>
                  <div className="truncate text-sm text-slate-400">{profile.url}</div>
                  <div className="mt-2 grid gap-2 md:grid-cols-4">
                    <Info label="Fields" value={Object.keys(profile.field_mapping).join(", ") || "None"} />
                    <Info label="Retries" value={String(profile.retry_policy.max_retries ?? 5)} />
                    <Info label="Monitoring" value={profile.monitoring_enabled ? "On" : "Off"} />
                    <Info label="Interval" value={`${profile.monitoring_interval_seconds / 60} min`} />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-2">
                  <Action icon={<Eye size={15} />} label="Open" onClick={() => openProfile(profile)} />
                  <Action icon={<Play size={15} />} label="Test Login" onClick={() => testLogin(profile)} />
                  <Action icon={<KeyRound size={15} />} label="Credentials" onClick={() => updateCredentials(profile)} />
                  <Action icon={<Upload size={15} />} label={profile.monitoring_enabled ? "Stop Monitor" : "Monitor"} onClick={() => toggleMonitor(profile)} />
                  <Action icon={<Clock size={15} />} label="History" onClick={() => viewHistory(profile)} />
                  <Action icon={<Download size={15} />} label="Export" onClick={() => exportProfile(profile)} />
                  <Action icon={<Trash2 size={15} />} label="Delete" danger onClick={() => deleteProfile(profile)} />
                </div>
              </div>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="KCET Result Automation">
        <div className="grid gap-2 md:grid-cols-[1fr_1fr_auto]">
          <input className="nexa-input h-11 rounded-xl px-3" value={kcetApp} onChange={(event) => setKcetApp(event.target.value)} placeholder="Application Number" />
          <input className="nexa-input h-11 rounded-xl px-3" value={kcetDob} onChange={(event) => setKcetDob(event.target.value)} placeholder="Date of Birth" />
          <button className="rounded-xl bg-accent px-4 font-semibold text-obsidian" onClick={runKcet}>Run KCET</button>
        </div>
      </Panel>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
      <div className="text-xs uppercase tracking-[0.16em] text-amber-200/55">{label}</div>
      <div className="mt-1 break-words text-sm text-slate-100">{value}</div>
    </div>
  );
}

function Action({ icon, label, onClick, danger = false }: { icon: React.ReactNode; label: string; onClick: () => void; danger?: boolean }) {
  return (
    <button className={`flex h-10 items-center justify-center gap-2 rounded-xl px-3 text-sm ${danger ? "bg-red-500/15 text-red-100" : "bg-white/8 text-amber-100 hover:bg-amber-300/15"}`} onClick={onClick}>
      {icon}
      {label}
    </button>
  );
}

function safeJson(value: string) {
  try {
    return JSON.parse(value);
  } catch {
    return {};
  }
}
