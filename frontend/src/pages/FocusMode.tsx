import React from "react";
import { Ban, Coffee, Pause, Play, Plus, Square, Target, Timer, TrendingUp } from "lucide-react";
import { api } from "../lib/api";

type AnyRecord = Record<string, any>;

const panel = "rounded-lg border border-amber-200/10 bg-white/[0.04] p-4";
const button = "inline-flex h-9 items-center gap-2 rounded-lg bg-amber-300 px-3 text-sm font-medium text-black hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-50";
const ghost = "inline-flex h-9 items-center gap-2 rounded-lg border border-amber-200/15 px-3 text-sm text-amber-100 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50";
const input = "h-10 w-full rounded-lg border border-amber-200/10 bg-black/25 px-3 text-sm text-amber-50 outline-none placeholder:text-slate-500 focus:border-amber-300/50";

export function FocusModePage() {
  const [data, setData] = React.useState<AnyRecord | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");
  const [sessionType, setSessionType] = React.useState("study");
  const [duration, setDuration] = React.useState(25);
  const [goal, setGoal] = React.useState("Complete one focused task");
  const [sites, setSites] = React.useState("youtube.com,instagram.com,reddit.com");

  const load = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await api<AnyRecord>("/evolution/focus/dashboard"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load focus dashboard");
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
      setError(err instanceof Error ? err.message : "Focus action failed");
      setLoading(false);
    }
  };

  const active = data?.active ?? { active: false };
  const progress = Number(active.session_progress_percent ?? 0);
  const detail = active.detail ?? {};
  const analytics = data?.analytics ?? [];
  const goals = data?.goals ?? [];
  const history = data?.history ?? [];

  return (
    <div className="space-y-5">
      <section className="flex flex-col gap-3 border-b border-amber-200/10 pb-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm text-amber-200/70"><Timer size={16} /> Productivity System</div>
          <h1 className="mt-1 text-2xl font-semibold text-amber-50">Focus Mode</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-400">Create a distraction-free study, coding, work, reading, or custom session with Pomodoro timing, blockers, goal tracking, and productivity analytics.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className={ghost} onClick={load} disabled={loading}><Play size={16} /> Refresh</button>
          <button className={button} onClick={() => run(() => api("/evolution/focus/start", { method: "POST", body: JSON.stringify({ title: `${sessionType} focus`, session_type: sessionType, duration_minutes: duration, current_goal: goal, blocked_websites: sites.split(",").map((item) => item.trim()).filter(Boolean) }) }))} disabled={loading || active.active}><Plus size={16} /> Start Focus</button>
        </div>
      </section>

      {error && <div className="rounded-lg border border-red-400/25 bg-red-500/10 p-3 text-sm text-red-100">{error}</div>}

      <section className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <div className={panel}>
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-amber-50">{active.active ? active.title : "No Active Session"}</h2>
            <span className="rounded-full bg-amber-300/15 px-3 py-1 text-xs text-amber-100">{active.status ?? "idle"}</span>
          </div>
          <div className="h-3 overflow-hidden rounded-full bg-black/30">
            <div className="h-full bg-amber-300" style={{ width: `${Math.min(100, progress)}%` }} />
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Metric label="Progress" value={`${Math.round(progress)}%`} />
            <Metric label="Remaining" value={`${Math.floor((active.remaining_seconds ?? 0) / 60)}m`} />
            <Metric label="Goal" value={detail.current_goal || "--"} />
            <Metric label="Score" value={`${active.productivity_score ?? "--"}%`} />
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <button className={ghost} onClick={() => run(() => api("/evolution/focus/pause", { method: "POST", body: JSON.stringify({ reason: "dashboard" }) }))} disabled={loading || !active.active}><Pause size={16} /> Pause</button>
            <button className={ghost} onClick={() => run(() => api("/evolution/focus/resume", { method: "POST", body: JSON.stringify({}) }))} disabled={loading}><Play size={16} /> Resume</button>
            <button className={ghost} onClick={() => run(() => api("/evolution/focus/break", { method: "POST", body: JSON.stringify({ minutes: 5 }) }))} disabled={loading || !active.active}><Coffee size={16} /> Break</button>
            <button className={ghost} onClick={() => run(() => api("/evolution/focus/extend", { method: "POST", body: JSON.stringify({ minutes: 10, reason: "dashboard" }) }))} disabled={loading || !active.active}><Plus size={16} /> Extend</button>
            <button className={ghost} onClick={() => run(() => api("/evolution/focus/end", { method: "POST", body: JSON.stringify({ tasks_completed: 1, distraction_count: active.distraction_count ?? 0, goal_completion_percent: 100 }) }))} disabled={loading || !active.active}><Square size={16} /> End</button>
          </div>
        </div>

        <div className={panel}>
          <h2 className="mb-3 text-lg font-semibold text-amber-50">Session Setup</h2>
          <div className="grid gap-3">
            <select className={input} value={sessionType} onChange={(event) => setSessionType(event.target.value)}>{["study", "coding", "work", "reading", "custom"].map((item) => <option key={item}>{item}</option>)}</select>
            <input className={input} type="number" min={1} max={240} value={duration} onChange={(event) => setDuration(Number(event.target.value))} />
            <input className={input} value={goal} onChange={(event) => setGoal(event.target.value)} />
            <input className={input} value={sites} onChange={(event) => setSites(event.target.value)} />
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <Summary title="Blocked Distractions" icon={<Ban size={18} />} items={[...(data?.blocked_sites ?? []).map((item: AnyRecord) => item.domain), ...(data?.blocked_apps ?? []).map((item: AnyRecord) => item.app_name)]} />
        <Summary title="Focus Goals" icon={<Target size={18} />} items={goals.map((item: AnyRecord) => `${item.title}: ${item.completion_percent}%`)} />
        <Summary title="Productivity Analytics" icon={<TrendingUp size={18} />} items={analytics.map((item: AnyRecord) => `Score ${Math.round(item.productivity_score)}% / ${Math.round(item.focus_seconds / 60)}m`)} />
      </section>

      <section className={panel}>
        <h2 className="mb-3 text-lg font-semibold text-amber-50">Focus History</h2>
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {history.length === 0 ? <Empty text="No focus history yet." /> : history.slice(0, 12).map((item: AnyRecord) => (
            <div key={item.id} className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm">
              <div className="font-medium text-amber-100">{item.event_type}</div>
              <div className="text-xs text-slate-500">{new Date(item.created_at).toLocaleString()}</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return <div className="rounded-lg border border-white/10 bg-black/20 p-3"><div className="text-xs text-slate-500">{label}</div><div className="mt-1 truncate text-sm font-medium text-amber-100">{value}</div></div>;
}

function Summary({ title, icon, items }: { title: string; icon: React.ReactNode; items: string[] }) {
  return (
    <div className={panel}>
      <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-amber-50">{icon}{title}</h2>
      <div className="space-y-2">{items.length ? items.slice(0, 6).map((item) => <div key={item} className="rounded-lg border border-white/10 bg-black/20 p-2 text-sm text-slate-300">{item}</div>) : <Empty text="No data yet." />}</div>
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm text-slate-500">{text}</div>;
}
