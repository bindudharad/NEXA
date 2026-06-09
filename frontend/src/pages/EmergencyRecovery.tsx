import React from "react";
import { AlertTriangle, CheckCircle2, HeartPulse, LifeBuoy, RefreshCw, RotateCcw, ShieldAlert, TerminalSquare } from "lucide-react";
import { api } from "../lib/api";

type AnyRecord = Record<string, any>;

const panel = "rounded-lg border border-amber-200/10 bg-white/[0.04] p-4";
const button = "inline-flex h-9 items-center gap-2 rounded-lg bg-amber-300 px-3 text-sm font-medium text-black hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-50";
const ghost = "inline-flex h-9 items-center gap-2 rounded-lg border border-amber-200/15 px-3 text-sm text-amber-100 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50";
const input = "h-10 w-full rounded-lg border border-amber-200/10 bg-black/25 px-3 text-sm text-amber-50 outline-none placeholder:text-slate-500 focus:border-amber-300/50";

export function EmergencyRecovery() {
  const [data, setData] = React.useState<AnyRecord | null>(null);
  const [projectPath, setProjectPath] = React.useState("C:\\Programs\\codex\\NEXA");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");

  const load = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await api<AnyRecord>("/evolution/recovery/dashboard"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Emergency Recovery");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void load();
  }, [load]);

  const run = async (operation: () => Promise<unknown>) => {
    setLoading(true);
    setError("");
    try {
      await operation();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Recovery action failed");
    } finally {
      setLoading(false);
    }
  };

  const summary = data?.summary ?? {};
  const reports = data?.crash_reports ?? [];
  const sessions = data?.recovery_sessions ?? [];
  const incidents = data?.incident_reports ?? [];
  const apps = data?.recovered_applications ?? [];
  const events = data?.events ?? [];
  const recommendations = data?.recommendations ?? [];
  const latestSession = sessions[0];

  return (
    <div className="space-y-5">
      <section className="flex flex-col gap-3 border-b border-amber-200/10 pb-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm text-amber-200/70"><LifeBuoy size={16} /> Emergency Recovery</div>
          <h1 className="mt-1 text-2xl font-semibold text-amber-50">Crash, Power Loss & Session Restore</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-400">Capture recovery state, review incidents, restore sessions, and connect crash reports to Project Guardian recovery points.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className={ghost} onClick={load} disabled={loading}><RefreshCw size={16} /> Refresh</button>
          <button className={button} onClick={() => run(() => api("/evolution/recovery/sessions", { method: "POST", body: JSON.stringify({ session_type: "manual_capture", applications: [{ name: "VS Code", workspace_path: projectPath }], project_path: projectPath }) }))} disabled={loading}><ShieldAlert size={16} /> Capture</button>
        </div>
      </section>

      {error && <div className="rounded-lg border border-red-400/25 bg-red-500/10 p-3 text-sm text-red-100">{error}</div>}

      <section className="grid gap-3 lg:grid-cols-[1fr_auto_auto_auto]">
        <input className={input} value={projectPath} onChange={(event) => setProjectPath(event.target.value)} placeholder="Project path for recovery snapshots" />
        <button className={ghost} disabled={loading} onClick={() => run(() => api("/evolution/recovery/simulate", { method: "POST", body: JSON.stringify({ event_type: "vscode_crash", application: "VS Code", project_path: projectPath }) }))}>Simulate VS Code</button>
        <button className={ghost} disabled={loading} onClick={() => run(() => api("/evolution/recovery/simulate", { method: "POST", body: JSON.stringify({ event_type: "terminal_crash", application: "Terminal", project_path: projectPath }) }))}>Simulate Terminal</button>
        <button className={ghost} disabled={loading || !latestSession} onClick={() => run(() => api(`/evolution/recovery/sessions/${latestSession.id}/restore`, { method: "POST" }))}><RotateCcw size={16} /> Restore Latest</button>
      </section>

      <section className="grid gap-4 xl:grid-cols-5">
        <Metric title="Health" value={`${Math.round(summary.health_score ?? 0)}%`} icon={<HeartPulse size={18} />} />
        <Metric title="Crash Reports" value={summary.crash_reports ?? 0} icon={<AlertTriangle size={18} />} />
        <Metric title="Open Reports" value={summary.open_reports ?? 0} icon={<ShieldAlert size={18} />} />
        <Metric title="Sessions" value={summary.recovery_sessions ?? 0} icon={<RotateCcw size={18} />} />
        <Metric title="App Restores" value={summary.available_app_restores ?? 0} icon={<TerminalSquare size={18} />} />
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <Panel title="Crash Reports">
          {reports.length === 0 ? <Empty text="No crash reports recorded." /> : reports.slice(0, 8).map((item: AnyRecord) => (
            <div key={item.id} className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm">
              <div className="flex items-center justify-between gap-3">
                <div className="font-medium text-amber-100">{item.application || item.crash_type}</div>
                <span className="text-xs uppercase text-amber-200/70">{item.severity}</span>
              </div>
              <p className="mt-1 text-slate-400">{item.message}</p>
              <div className="mt-2 text-xs text-slate-500">{new Date(item.created_at).toLocaleString()} / {item.status}</div>
            </div>
          ))}
        </Panel>

        <Panel title="Restore Sessions">
          {sessions.length === 0 ? <Empty text="No captured recovery sessions." /> : sessions.slice(0, 8).map((item: AnyRecord) => (
            <div key={item.id} className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm">
              <div className="flex items-center justify-between gap-3">
                <div className="font-medium text-amber-100">{item.session_type}</div>
                <span className="text-slate-400">{item.status}</span>
              </div>
              <div className="mt-2 text-xs text-slate-500">{item.restore_plan?.length ?? 0} restore action(s)</div>
            </div>
          ))}
        </Panel>
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <Summary title="Incident Reports" items={incidents.map((item: AnyRecord) => `${item.title}: ${item.status}`)} />
        <Summary title="Recovered Applications" items={apps.map((item: AnyRecord) => `${item.app_name}: ${item.restore_command || "manual review"}`)} />
        <Summary title="Recovery Events" items={events.map((item: AnyRecord) => `${item.title}: ${item.severity}`)} />
      </section>

      <Panel title="Recommendations">
        {recommendations.length === 0 ? <Empty text="No recommendations." /> : recommendations.map((item: AnyRecord) => (
          <div key={`${item.title}-${item.priority}`} className="flex items-start gap-3 rounded-lg border border-white/10 bg-black/20 p-3 text-sm">
            <CheckCircle2 size={17} className="mt-0.5 shrink-0 text-amber-200" />
            <div>
              <div className="font-medium text-amber-100">{item.title}</div>
              <div className="text-slate-400">{item.message}</div>
            </div>
          </div>
        ))}
      </Panel>
    </div>
  );
}

function Metric({ title, value, icon }: { title: string; value: React.ReactNode; icon: React.ReactNode }) {
  return <div className={panel}><div className="mb-2 flex items-center gap-2 text-sm text-slate-400">{icon}{title}</div><div className="text-2xl font-semibold text-amber-50">{value}</div></div>;
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return <div className={panel}><h2 className="mb-3 text-lg font-semibold text-amber-50">{title}</h2><div className="space-y-2">{children}</div></div>;
}

function Summary({ title, items }: { title: string; items: string[] }) {
  return <Panel title={title}>{items.length === 0 ? <Empty text="Nothing recorded yet." /> : items.slice(0, 8).map((item) => <div key={item} className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm text-slate-300">{item}</div>)}</Panel>;
}

function Empty({ text }: { text: string }) {
  return <div className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm text-slate-500">{text}</div>;
}
