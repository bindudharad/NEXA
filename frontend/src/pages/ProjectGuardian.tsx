import React from "react";
import { GitBranch, HeartPulse, RotateCcw, Save, Search, Shield, ShieldCheck } from "lucide-react";
import { api } from "../lib/api";

type AnyRecord = Record<string, any>;

const panel = "rounded-lg border border-amber-200/10 bg-white/[0.04] p-4";
const button = "inline-flex h-9 items-center gap-2 rounded-lg bg-amber-300 px-3 text-sm font-medium text-black hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-50";
const ghost = "inline-flex h-9 items-center gap-2 rounded-lg border border-amber-200/15 px-3 text-sm text-amber-100 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50";
const input = "h-10 w-full rounded-lg border border-amber-200/10 bg-black/25 px-3 text-sm text-amber-50 outline-none placeholder:text-slate-500 focus:border-amber-300/50";

export function ProjectGuardian() {
  const [data, setData] = React.useState<AnyRecord | null>(null);
  const [projectPath, setProjectPath] = React.useState("C:\\Programs\\codex\\NEXA");
  const [restorePath, setRestorePath] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");

  const load = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const query = projectPath ? `?project_path=${encodeURIComponent(projectPath)}` : "";
      setData(await api<AnyRecord>(`/evolution/project-guardian/dashboard${query}`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Project Guardian");
    } finally {
      setLoading(false);
    }
  }, [projectPath]);

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
      setError(err instanceof Error ? err.message : "Project Guardian action failed");
    } finally {
      setLoading(false);
    }
  };

  const projects = data?.projects ?? [];
  const backups = data?.backups ?? [];
  const snapshots = data?.snapshots ?? [];
  const recovery = data?.recovery_points ?? [];
  const git = data?.git_history ?? [];
  const health = data?.health ?? [];
  const events = data?.events ?? [];
  const latestHealth = health[0];
  const latestRecovery = recovery[0];

  return (
    <div className="space-y-5">
      <section className="flex flex-col gap-3 border-b border-amber-200/10 pb-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm text-amber-200/70"><Shield size={16} /> Project Guardian</div>
          <h1 className="mt-1 text-2xl font-semibold text-amber-50">Project Protection & Recovery</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-400">Create recovery snapshots before risky operations, track Git state, and restore lost work offline.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className={ghost} onClick={load} disabled={loading}><Search size={16} /> Refresh</button>
          <button className={button} onClick={() => run(() => api("/evolution/project-guardian/snapshot", { method: "POST", body: JSON.stringify({ project_path: projectPath, action: "manual_snapshot" }) }))} disabled={loading}><Save size={16} /> Snapshot</button>
        </div>
      </section>

      {error && <div className="rounded-lg border border-red-400/25 bg-red-500/10 p-3 text-sm text-red-100">{error}</div>}

      <section className="grid gap-3 lg:grid-cols-[1fr_auto_auto]">
        <input className={input} value={projectPath} onChange={(event) => setProjectPath(event.target.value)} placeholder="Project path" />
        <button className={ghost} onClick={() => run(() => api("/evolution/project-guardian/protect", { method: "POST", body: JSON.stringify({ project_path: projectPath, operation: "git_push", reason: "Manual dashboard protection" }) }))} disabled={loading}>Protect Git Push</button>
        <button className={ghost} onClick={() => run(() => api("/evolution/project-guardian/protect", { method: "POST", body: JSON.stringify({ project_path: projectPath, operation: "delete", reason: "Delete protection check" }) }))} disabled={loading}>Delete Protection</button>
      </section>

      <section className="grid gap-4 xl:grid-cols-4">
        <Metric title="Projects" value={projects.length} icon={<ShieldCheck size={18} />} />
        <Metric title="Backups" value={backups.length} icon={<Save size={18} />} />
        <Metric title="Recovery Points" value={recovery.length} icon={<RotateCcw size={18} />} />
        <Metric title="Health" value={latestHealth ? `${Math.round(latestHealth.health_score)}%` : "--"} icon={<HeartPulse size={18} />} />
      </section>

      <section className="grid gap-4 xl:grid-cols-[1fr_0.8fr]">
        <Panel title="Projects">
          {projects.length === 0 ? <Empty text="No projects registered yet." /> : projects.map((project: AnyRecord) => (
            <div key={project.id} className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="font-medium text-amber-100">{project.name}</div>
                  <div className="break-all text-xs text-slate-500">{project.path}</div>
                </div>
                <div className="text-right text-amber-100">{Math.round(project.health_score ?? 0)}%</div>
              </div>
              <div className="mt-2 text-xs text-slate-500">Branch: {project.git_branch || "none"} / Commit: {project.commit_hash || "none"}</div>
            </div>
          ))}
        </Panel>

        <Panel title="Git Guardian">
          {git.length === 0 ? <Empty text="No protected Git operations yet." /> : git.slice(0, 8).map((item: AnyRecord) => (
            <div key={item.id} className="flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-black/20 p-3 text-sm">
              <div><div className="font-medium text-amber-100">{item.operation}</div><div className="text-xs text-slate-500">{item.branch_name || "no branch"}</div></div>
              <span className="text-slate-400">{item.risk_level}</span>
            </div>
          ))}
        </Panel>
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <Summary title="Snapshots" items={snapshots.map((item: AnyRecord) => `${item.project_name}: ${item.action}`)} />
        <Summary title="Backups" items={backups.map((item: AnyRecord) => `${item.action}: ${item.status}`)} />
        <Summary title="Project Events" items={events.map((item: AnyRecord) => `${item.title}: ${item.severity}`)} />
      </section>

      <Panel title="Recovery">
        <div className="mb-3 grid gap-2 md:grid-cols-[1fr_auto]">
          <input className={input} value={restorePath} onChange={(event) => setRestorePath(event.target.value)} placeholder="Restore path" />
          <button className={button} disabled={loading || !latestRecovery || !restorePath} onClick={() => run(() => api("/evolution/project-guardian/restore", { method: "POST", body: JSON.stringify({ backup_id: latestRecovery.backup_id, restore_path: restorePath }) }))}><RotateCcw size={16} /> Restore Latest</button>
        </div>
        {recovery.length === 0 ? <Empty text="No recovery points yet." /> : recovery.slice(0, 8).map((item: AnyRecord) => (
          <div key={item.id} className="flex items-center justify-between gap-3 border-b border-white/10 py-2 text-sm last:border-b-0">
            <span className="text-slate-300">{item.title}</span>
            <span className="text-slate-500">{item.status}</span>
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
