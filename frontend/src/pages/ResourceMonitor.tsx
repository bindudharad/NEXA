import React from "react";
import { Activity, AlertTriangle, BarChart3, Battery, Cpu, Database, Gauge, HeartPulse, RefreshCw, ServerCog, Thermometer, Zap } from "lucide-react";
import { Panel } from "../components/Panel";
import { api } from "../lib/api";

type AnyRecord = Record<string, any>;

const button = "inline-flex h-9 items-center justify-center gap-2 rounded-lg bg-amber-300 px-3 text-sm font-medium text-black hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-50";
const ghost = "inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-amber-200/15 px-3 text-sm text-amber-100 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50";

export function ResourceMonitor() {
  const [health, setHealth] = React.useState<AnyRecord | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");

  const load = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setHealth(await api<AnyRecord>("/evolution/self-health"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Self Health Dashboard");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void load();
    const timer = window.setInterval(load, 30000);
    return () => window.clearInterval(timer);
  }, [load]);

  async function optimize(action = "optimize") {
    setLoading(true);
    setError("");
    try {
      const result = await api<AnyRecord>("/evolution/self-health/optimize", { method: "POST", body: JSON.stringify({ action }) });
      setHealth(result.dashboard);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Optimization failed");
    } finally {
      setLoading(false);
    }
  }

  const cpu = health?.cpu ?? {};
  const ram = health?.ram ?? {};
  const gpu = health?.gpu ?? {};
  const battery = health?.battery_impact ?? {};
  const thermal = health?.thermal_impact ?? {};
  const apiHealth = health?.api_health ?? {};
  const automation = health?.automation_health ?? {};
  const errors = health?.error_monitor ?? {};
  const logs = health?.log_monitor ?? {};
  const moduleScores = health?.module_scores ?? {};
  const recommendations = health?.recommendations ?? [];
  const trends = health?.trends ?? {};

  return (
    <div className="space-y-5">
      <section className="flex flex-col gap-3 border-b border-amber-200/10 pb-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm text-amber-200/70"><HeartPulse size={16} /> Nexa Self Health</div>
          <h1 className="mt-1 text-2xl font-semibold text-amber-50">Self Health Dashboard</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-400">Monitor Nexa CPU, RAM, GPU, battery impact, thermal impact, APIs, automations, logs, services, and optimization recommendations.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className={ghost} onClick={load} disabled={loading}><RefreshCw size={16} /> Refresh</button>
          <button className={button} onClick={() => optimize("optimize")} disabled={loading}><Zap size={16} /> Optimize Nexa</button>
        </div>
      </section>

      {error && <div className="rounded-lg border border-red-400/25 bg-red-500/10 p-3 text-sm text-red-100">{error}</div>}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <Metric icon={<Gauge size={18} />} label="Overall Health" value={`${Math.round(health?.health_score ?? 100)}%`} detail={health?.status ?? "excellent"} />
        <Metric icon={<Cpu size={18} />} label="Nexa CPU" value={`${cpu.current_percent ?? 0}%`} detail={`avg ${cpu.average_percent ?? 0}%`} />
        <Metric icon={<Activity size={18} />} label="Nexa RAM" value={`${ram.current_mb ?? 0} MB`} detail={`peak ${ram.peak_mb ?? 0} MB`} />
        <Metric icon={<Battery size={18} />} label="Battery Impact" value={`${battery.score ?? 0}`} detail={battery.status ?? "low"} />
        <Metric icon={<Thermometer size={18} />} label="Thermal Impact" value={`${thermal.score ?? 0}`} detail={`${thermal.nexa_contribution_estimate ?? 0}% estimate`} />
      </section>

      <section className="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <Panel title="Resource Usage">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <Status label="CPU Current" value={`${cpu.current_percent ?? 0}%`} />
            <Status label="CPU Peak" value={`${cpu.peak_percent ?? 0}%`} />
            <Status label="RAM Current" value={`${ram.current_mb ?? 0} MB`} />
            <Status label="RAM Growth" value={`${ram.growth_mb ?? 0} MB`} />
            <Status label="Potential Leak" value={ram.potential_leak ? "Yes" : "No"} />
            <Status label="GPU Usage" value={`${gpu.usage_percent ?? 0}%`} />
            <Status label="Rendering Load" value={gpu.rendering_load ?? "low"} />
            <Status label="Power Mode" value={health?.resource_manager?.mode ?? "normal"} />
            <Status label="Threads" value={String(health?.resource_manager?.process_threads ?? 0)} />
          </div>
        </Panel>

        <Panel title="Reliability">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <Status label="API Status" value={apiHealth.summary?.status ?? "healthy"} />
            <Status label="API Success" value={`${apiHealth.summary?.success_rate ?? 100}%`} />
            <Status label="Automations" value={String(automation.executions ?? 0)} />
            <Status label="Automation Success" value={`${automation.success_rate ?? 100}%`} />
            <Status label="Failures" value={String(automation.failures ?? 0)} />
            <Status label="Errors" value={String(errors.count ?? 0)} />
            <Status label="Database" value={health?.database_health ?? "ok"} />
            <Status label="Notifications" value={String(health?.notifications ?? 0)} />
            <Status label="Tasks" value={String(health?.tasks ?? 0)} />
          </div>
        </Panel>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <Panel title="Module Health Scores">
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {Object.entries(moduleScores).map(([name, score]) => (
              <div key={name} className="rounded-lg border border-white/10 bg-black/20 p-3">
                <div className="flex items-center justify-between gap-3 text-sm">
                  <span className="truncate text-slate-300">{name}</span>
                  <span className="font-medium text-amber-100">{Math.round(Number(score))}%</span>
                </div>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/10">
                  <div className="h-full rounded-full bg-amber-300" style={{ width: `${Math.max(0, Math.min(100, Number(score)))}%` }} />
                </div>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Optimization Recommendations">
          <div className="space-y-2">
            {recommendations.length === 0 ? <Empty text="No optimization recommendations right now." /> : recommendations.map((item: AnyRecord, index: number) => (
              <div key={`${item.title}-${index}`} className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium text-amber-100">{item.title}</span>
                  <span className="text-xs text-slate-500">{item.priority}</span>
                </div>
                <p className="mt-1 text-slate-300">{item.message}</p>
              </div>
            ))}
          </div>
        </Panel>
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <Panel title="API Health">
          <HealthBlock data={apiHealth.backend} label="Backend API" />
          <HealthBlock data={apiHealth.groq} label="Groq API" />
          <HealthBlock data={apiHealth.local} label="Local APIs" />
        </Panel>

        <Panel title="Background Services">
          <div className="space-y-2">
            {Object.entries(health?.background_tasks ?? {}).map(([name, value]) => <Status key={name} label={labelize(name)} value={typeof value === "object" ? JSON.stringify(value).slice(0, 80) : String(value)} />)}
          </div>
        </Panel>

        <Panel title="Log Monitor">
          <div className="space-y-2">
            {(logs.files ?? []).map((file: AnyRecord) => <Status key={file.path} label={file.path.split(/[\\/]/).pop() ?? file.path} value={file.exists ? bytes(file.size_bytes) : "Missing"} />)}
          </div>
        </Panel>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <Panel title="Recent Errors">
          <div className="max-h-[360px] space-y-2 overflow-auto pr-1">
            {(errors.recent ?? []).length === 0 ? <Empty text="No recent errors found." /> : errors.recent.slice(0, 12).map((item: AnyRecord, index: number) => (
              <div key={`${item.file}-${index}`} className="rounded-lg border border-red-400/20 bg-red-500/10 p-3 text-sm text-red-50">
                <div className="flex items-center gap-2 font-medium"><AlertTriangle size={15} /> {item.file}</div>
                <p className="mt-1 text-red-100/80">{item.message}</p>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Health Trends">
          <div className="grid gap-3 sm:grid-cols-2">
            <Status label="Resource Samples" value={String(trends.resource_usage?.length ?? 0)} />
            <Status label="Score Samples" value={String(trends.health_scores?.length ?? 0)} />
            <Status label="Performance Score" value={`${Math.round(health?.performance_score ?? 100)}%`} />
            <Status label="Reliability Score" value={`${Math.round(health?.reliability_score ?? 100)}%`} />
            <Status label="Resource Score" value={`${Math.round(health?.resource_score ?? 100)}%`} />
            <Status label="Offline Support" value={health?.offline_ready ? "Ready" : "Unknown"} />
          </div>
        </Panel>
      </section>
    </div>
  );
}

function Metric({ icon, label, value, detail }: { icon: React.ReactNode; label: string; value: string; detail: string }) {
  return (
    <div className="glass-panel rounded-lg p-4">
      <div className="mb-3 flex items-center gap-2 text-sm text-amber-100/70">{icon}{label}</div>
      <div className="break-words text-2xl font-semibold">{value}</div>
      <div className="mt-1 text-xs text-slate-500">{detail}</div>
    </div>
  );
}

function Status({ label, value }: { label: string; value: string }) {
  return <div className="nexa-card rounded-lg p-3"><div className="mb-1 text-xs text-amber-100/70">{label}</div><div className="break-words text-sm font-semibold text-slate-100">{value}</div></div>;
}

function HealthBlock({ label, data }: { label: string; data?: AnyRecord }) {
  return (
    <div className="mb-2 rounded-lg border border-white/10 bg-black/20 p-3 text-sm">
      <div className="mb-2 flex items-center justify-between gap-3">
        <span className="font-medium text-amber-100">{label}</span>
        <span className="text-xs text-slate-500">{data?.status ?? "unknown"}</span>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Status label="Success" value={`${data?.success_rate ?? 0}%`} />
        <Status label="Failures" value={`${data?.failure_rate ?? 0}%`} />
      </div>
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm text-slate-500">{text}</div>;
}

function bytes(value: number | null | undefined) {
  if (value == null) return "0 B";
  if (value >= 1024 * 1024 * 1024) return `${(value / (1024 * 1024 * 1024)).toFixed(1)} GB`;
  if (value >= 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  if (value >= 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${value} B`;
}

function labelize(value: string) {
  return value.split("_").map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" ");
}
