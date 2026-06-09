import React from "react";
import { BarChart3, CheckCircle2, Clock, Copy, PauseCircle, PlayCircle, Plus, RefreshCw, ShieldAlert, Wand2, XCircle } from "lucide-react";
import { api } from "../lib/api";
import { Panel } from "../components/Panel";

type AnyRecord = Record<string, any>;

const button = "inline-flex h-9 items-center gap-2 rounded-lg bg-amber-300 px-3 text-sm font-medium text-black hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-50";
const ghost = "inline-flex h-9 items-center gap-2 rounded-lg border border-amber-200/15 px-3 text-sm text-amber-100 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50";
const input = "h-10 w-full rounded-lg border border-amber-200/10 bg-black/25 px-3 text-sm text-amber-50 outline-none placeholder:text-slate-500 focus:border-amber-300/50";

export function Automations() {
  const [dashboard, setDashboard] = React.useState<AnyRecord | null>(null);
  const [prompt, setPrompt] = React.useState("When battery reaches 20% and charger is not connected, notify me every 2 minutes.");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");

  const load = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setDashboard(await api<AnyRecord>("/automations/dashboard"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load automations");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void load();
  }, [load]);

  async function build() {
    setLoading(true);
    setError("");
    try {
      await api<AnyRecord>("/evolution/automation-builder", { method: "POST", body: JSON.stringify({ prompt }) });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Automation builder failed");
    } finally {
      setLoading(false);
    }
  }

  async function toggle(id: number, enabled: boolean) {
    await api<AnyRecord>(`/automations/${id}/toggle`, { method: "PUT", body: JSON.stringify({ enabled }) });
    await load();
  }

  const active = dashboard?.active ?? [];
  const paused = dashboard?.paused ?? [];
  const failed = dashboard?.failed ?? [];
  const completed = dashboard?.completed ?? [];
  const history = dashboard?.recent_executions ?? [];
  const templates = dashboard?.templates ?? [];
  const stats = dashboard?.statistics ?? {};

  return (
    <div className="space-y-5">
      <section className="flex flex-col gap-3 border-b border-amber-200/10 pb-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm text-amber-200/70"><Wand2 size={16} /> AI Automation Builder</div>
          <h1 className="mt-1 text-2xl font-semibold text-amber-50">Plain-English Automations</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-400">Convert natural language into triggers, conditions, actions, schedules, approvals, and history-backed workflows.</p>
        </div>
        <button className={ghost} onClick={load} disabled={loading}><RefreshCw size={16} /> Refresh</button>
      </section>

      {error && <div className="rounded-lg border border-red-400/25 bg-red-500/10 p-3 text-sm text-red-100">{error}</div>}

      <Panel title="Create Automation">
        <div className="grid gap-2 lg:grid-cols-[1fr_auto]">
          <input className={input} value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Describe the automation in plain English" />
          <button className={button} onClick={build} disabled={loading || !prompt.trim()}><Plus size={16} /> Generate</button>
        </div>
      </Panel>

      <section className="grid gap-4 xl:grid-cols-5">
        <Metric title="Active" value={active.length} icon={<PlayCircle size={18} />} />
        <Metric title="Paused" value={paused.length} icon={<PauseCircle size={18} />} />
        <Metric title="Completed" value={completed.length} icon={<CheckCircle2 size={18} />} />
        <Metric title="Failed" value={failed.length} icon={<XCircle size={18} />} />
        <Metric title="Success" value={`${Math.round(stats.success_rate ?? 0)}%`} icon={<BarChart3 size={18} />} />
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <Panel title="Automations">
          {[...active, ...paused].length === 0 ? <Empty text="No automations created yet." /> : [...active, ...paused].map((item: AnyRecord) => (
            <div key={item.id} className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm">
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                  <div className="font-medium text-amber-100">{item.name}</div>
                  <div className="mt-1 text-xs text-slate-500">IF {formatRule(item.condition)} THEN {item.action?.type ?? "action"}</div>
                  <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-400">
                    {(item.triggers ?? []).map((trigger: AnyRecord) => <span key={trigger.id} className="rounded border border-white/10 px-2 py-1">{trigger.trigger_type}</span>)}
                    {(item.actions ?? []).some((action: AnyRecord) => action.requires_approval) && <span className="inline-flex items-center gap-1 rounded border border-amber-300/20 px-2 py-1 text-amber-200"><ShieldAlert size={12} /> Approval</span>}
                  </div>
                </div>
                <button className={ghost} onClick={() => toggle(item.id, !item.enabled)}>{item.enabled ? "Pause" : "Resume"}</button>
              </div>
            </div>
          ))}
        </Panel>

        <Panel title="Analytics">
          <div className="grid gap-2 text-sm">
            <MetricLine label="Executions" value={stats.total_executions ?? 0} />
            <MetricLine label="Failure Rate" value={`${stats.failure_rate ?? 0}%`} />
            <MetricLine label="Pending Approvals" value={stats.pending_approvals ?? 0} />
            <MetricLine label="Avg Runtime" value={`${stats.average_runtime_ms ?? 0} ms`} />
          </div>
        </Panel>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Panel title="Templates">
          {templates.length === 0 ? <Empty text="Templates will appear after refresh." /> : templates.slice(0, 10).map((item: AnyRecord) => (
            <div key={item.id} className="flex items-start gap-3 rounded-lg border border-white/10 bg-black/20 p-3 text-sm">
              <Copy size={16} className="mt-0.5 shrink-0 text-amber-200" />
              <div>
                <div className="font-medium text-amber-100">{item.name}</div>
                <div className="text-slate-400">{item.description}</div>
              </div>
            </div>
          ))}
        </Panel>

        <Panel title="Recent History">
          {history.length === 0 ? <Empty text="No automation history yet." /> : history.slice(0, 10).map((item: AnyRecord) => (
            <div key={item.id} className="flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-black/20 p-3 text-sm">
              <div>
                <div className="font-medium text-amber-100">{item.event_type}</div>
                <div className="text-xs text-slate-500">{new Date(item.created_at).toLocaleString()}</div>
              </div>
              <span className="inline-flex items-center gap-1 text-slate-400"><Clock size={14} /> {item.status}</span>
            </div>
          ))}
        </Panel>
      </section>
    </div>
  );
}

function formatRule(rule: AnyRecord): string {
  if (rule?.all) return rule.all.map(formatRule).join(" AND ");
  if (rule?.any) return rule.any.map(formatRule).join(" OR ");
  if (rule?.event_type) return rule.event_type;
  return `${rule?.metric ?? "event"} ${rule?.operator ?? ""} ${rule?.value ?? ""}`.trim();
}

function Metric({ title, value, icon }: { title: string; value: React.ReactNode; icon: React.ReactNode }) {
  return <div className="rounded-lg border border-amber-200/10 bg-white/[0.04] p-4"><div className="mb-2 flex items-center gap-2 text-sm text-slate-400">{icon}{title}</div><div className="text-2xl font-semibold text-amber-50">{value}</div></div>;
}

function MetricLine({ label, value }: { label: string; value: React.ReactNode }) {
  return <div className="flex items-center justify-between rounded-lg border border-white/10 bg-black/20 px-3 py-2"><span className="text-slate-400">{label}</span><span className="text-amber-100">{value}</span></div>;
}

function Empty({ text }: { text: string }) {
  return <div className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm text-slate-500">{text}</div>;
}
