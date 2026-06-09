import React from "react";
import { Activity, Bell, BrainCircuit, CheckCircle2, Eye, Lightbulb, Lock, RefreshCw, Save, Sparkles, Zap } from "lucide-react";
import { Panel } from "../components/Panel";
import { api } from "../lib/api";

type AnyRecord = Record<string, any>;

const button = "inline-flex h-9 items-center justify-center gap-2 rounded-lg bg-amber-300 px-3 text-sm font-medium text-black hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-50";
const ghost = "inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-amber-200/15 px-3 text-sm text-amber-100 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50";

export function CopilotCenter() {
  const [dashboard, setDashboard] = React.useState<AnyRecord | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");

  const load = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setDashboard(await api<AnyRecord>("/evolution/copilot/dashboard"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Copilot Center");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void load();
  }, [load]);

  async function evaluate() {
    setLoading(true);
    setError("");
    try {
      await api("/evolution/copilot/evaluate", { method: "POST" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Copilot evaluation failed");
      setLoading(false);
    }
  }

  async function action(id: number, actionType: "act" | "save" | "dismiss") {
    setLoading(true);
    setError("");
    try {
      await api(`/evolution/copilot/suggestions/${id}/actions`, { method: "POST", body: JSON.stringify({ action_type: actionType }) });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Copilot action failed");
      setLoading(false);
    }
  }

  const suggestions = dashboard?.suggestions ?? [];
  const context = dashboard?.context?.payload ?? {};
  const warnings = dashboard?.warnings ?? [];
  const insights = dashboard?.insights ?? [];
  const quickActions = dashboard?.quick_actions ?? [];
  const history = dashboard?.history ?? [];
  const status = dashboard?.system_status ?? {};

  return (
    <div className="space-y-5">
      <section className="flex flex-col gap-3 border-b border-amber-200/10 pb-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm text-amber-200/70"><BrainCircuit size={16} /> AI Copilot Mode</div>
          <h1 className="mt-1 text-2xl font-semibold text-amber-50">Copilot Center</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-400">Context-aware recommendations from battery, health, tasks, college, study, goals, projects, automations, and timeline activity. Local-first and non-intrusive.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className={ghost} onClick={load} disabled={loading}><RefreshCw size={16} /> Refresh</button>
          <button className={button} onClick={evaluate} disabled={loading}><Sparkles size={16} /> Evaluate Context</button>
        </div>
      </section>

      {error && <div className="rounded-lg border border-red-400/25 bg-red-500/10 p-3 text-sm text-red-100">{error}</div>}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <Metric icon={<Zap size={18} />} label="Status" value={status.status ?? "ready"} detail={status.message ?? "Monitoring local context"} />
        <Metric icon={<Lightbulb size={18} />} label="Suggestions" value={String(suggestions.length)} detail={`${dashboard?.orbital?.critical_count ?? 0} critical`} />
        <Metric icon={<Activity size={18} />} label="Activity" value={context.activity?.type ?? "idle"} detail={context.priority_context ?? "normal"} />
        <Metric icon={<Bell size={18} />} label="Warnings" value={String(warnings.filter((item: AnyRecord) => item.status === "open").length)} detail="open warnings" />
        <Metric icon={<Lock size={18} />} label="Privacy" value={dashboard?.privacy?.privacy_mode ?? "local"} detail="cloud upload disabled" />
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <Panel title="Recommendations">
          <div className="space-y-3">
            {suggestions.length === 0 && <Empty text="No open Copilot recommendations. Evaluate context to refresh." />}
            {suggestions.map((item: AnyRecord) => (
              <div key={item.id} className="rounded-lg border border-white/10 bg-black/20 p-3">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-medium text-amber-50">{item.title}</span>
                      <Pill tone={item.severity}>{item.severity}</Pill>
                      <Pill>{item.suggestion_type}</Pill>
                    </div>
                    <p className="mt-2 text-sm text-slate-300">{item.message}</p>
                    <div className="mt-2 text-xs text-slate-500">{item.module} · {formatTime(item.created_at)}</div>
                  </div>
                  <div className="flex shrink-0 flex-wrap gap-2">
                    <button className={ghost} onClick={() => action(item.id, "act")} disabled={loading}><CheckCircle2 size={14} /> Act</button>
                    <button className={ghost} onClick={() => action(item.id, "save")} disabled={loading}><Save size={14} /> Save</button>
                    <button className={ghost} onClick={() => action(item.id, "dismiss")} disabled={loading}>Dismiss</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Quick Actions">
          <div className="grid gap-2">
            {quickActions.map((item: AnyRecord) => (
              <div key={item.id} className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm text-slate-200">
                <div className="flex items-center gap-2"><Eye size={15} className="text-amber-200" /> {item.label}</div>
              </div>
            ))}
            {quickActions.length === 0 && <Empty text="No quick actions right now." />}
          </div>
        </Panel>
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <Panel title="Context Snapshot">
          <div className="grid gap-2">
            <Status label="Current App" value={dashboard?.context?.current_app || "unknown"} />
            <Status label="Activity" value={dashboard?.context?.activity_type || "idle"} />
            <Status label="Battery" value={`${context.battery?.battery_percent ?? "--"}% ${context.battery?.is_charging ? "charging" : "not charging"}`} />
            <Status label="Nexa Health" value={`${context.health?.health_score ?? "--"}%`} />
            <Status label="Unread Notifications" value={String(context.notifications?.unread ?? 0)} />
          </div>
        </Panel>

        <Panel title="Insights">
          <div className="space-y-2">
            {insights.slice(0, 6).map((item: AnyRecord) => (
              <div key={item.id} className="rounded-lg border border-white/10 bg-black/20 p-3">
                <div className="text-sm font-medium text-amber-50">{item.title}</div>
                <p className="mt-1 text-sm text-slate-300">{item.message}</p>
                <div className="mt-1 text-xs text-slate-500">{item.recommendation}</div>
              </div>
            ))}
            {insights.length === 0 && <Empty text="No insights yet." />}
          </div>
        </Panel>

        <Panel title="Warnings">
          <div className="space-y-2">
            {warnings.slice(0, 6).map((item: AnyRecord) => (
              <div key={item.id} className="rounded-lg border border-white/10 bg-black/20 p-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-medium text-amber-50">{item.title}</span>
                  <Pill tone={item.severity}>{item.severity}</Pill>
                </div>
                <p className="mt-1 text-sm text-slate-300">{item.message}</p>
              </div>
            ))}
            {warnings.length === 0 && <Empty text="No warnings." />}
          </div>
        </Panel>
      </section>

      <Panel title="Copilot History">
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {history.slice(0, 9).map((item: AnyRecord) => (
            <div key={item.id} className="rounded-lg border border-white/10 bg-black/20 p-3">
              <div className="text-sm font-medium text-amber-50">{item.title}</div>
              <div className="mt-1 text-xs text-slate-500">{item.event_type} · {formatTime(item.created_at)}</div>
            </div>
          ))}
          {history.length === 0 && <Empty text="No Copilot history yet." />}
        </div>
      </Panel>
    </div>
  );
}

function Metric({ icon, label, value, detail }: { icon: React.ReactNode; label: string; value: string; detail: string }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.04] p-4">
      <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-amber-200/60">{icon}{label}</div>
      <div className="mt-3 truncate text-2xl font-semibold capitalize text-amber-50">{value}</div>
      <div className="mt-1 text-xs text-slate-400">{detail}</div>
    </div>
  );
}

function Status({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-white/10 bg-black/20 p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-1 truncate text-sm text-slate-100">{value}</div>
    </div>
  );
}

function Pill({ children, tone = "low" }: { children: React.ReactNode; tone?: string }) {
  const cls = tone === "critical" ? "border-red-300/30 bg-red-400/10 text-red-100" : tone === "high" ? "border-orange-300/30 bg-orange-400/10 text-orange-100" : "border-amber-200/15 bg-amber-300/10 text-amber-100";
  return <span className={`rounded border px-2 py-0.5 text-[11px] ${cls}`}>{children}</span>;
}

function Empty({ text }: { text: string }) {
  return <div className="rounded-lg border border-dashed border-amber-200/15 px-3 py-6 text-center text-sm text-slate-400">{text}</div>;
}

function formatTime(value?: string | null) {
  if (!value) return "unknown";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}
