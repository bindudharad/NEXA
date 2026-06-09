import React from "react";
import { Award, BarChart3, CheckCircle2, Plus, RefreshCw, Target, TrendingUp } from "lucide-react";
import { Panel } from "../components/Panel";
import { api } from "../lib/api";

type AnyRecord = Record<string, any>;

const button = "inline-flex h-9 items-center justify-center gap-2 rounded-lg bg-amber-300 px-3 text-sm font-medium text-black hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-50";
const ghost = "inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-amber-200/15 px-3 text-sm text-amber-100 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50";
const input = "h-10 w-full rounded-lg border border-amber-200/10 bg-black/25 px-3 text-sm text-amber-50 outline-none placeholder:text-slate-500 focus:border-amber-300/50";

export function GoalTracker() {
  const [dashboard, setDashboard] = React.useState<AnyRecord | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");
  const [title, setTitle] = React.useState("Code 4 Hours Daily");
  const [target, setTarget] = React.useState(4);
  const [unit, setUnit] = React.useState("hours");
  const [goalType, setGoalType] = React.useState("coding");
  const [deadline, setDeadline] = React.useState("");

  const refresh = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setDashboard(await api<AnyRecord>("/evolution/goals/dashboard"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Goal Tracker");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void refresh();
  }, [refresh]);

  async function run(operation: () => Promise<unknown>) {
    setLoading(true);
    setError("");
    try {
      await operation();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Goal operation failed");
      setLoading(false);
    }
  }

  const goals = dashboard?.goals ?? [];
  const active = dashboard?.active_goals ?? [];
  const completed = dashboard?.completed_goals ?? [];
  const stats = dashboard?.statistics ?? {};
  const analytics = dashboard?.analytics ?? {};
  const recommendations = dashboard?.recommendations ?? [];
  const streaks = dashboard?.streaks ?? [];
  const achievements = dashboard?.achievements ?? [];
  const history = dashboard?.recent_activity ?? [];

  return (
    <div className="space-y-5">
      <section className="flex flex-col gap-3 border-b border-amber-200/10 pb-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm text-amber-200/70"><Target size={16} /> Goal Tracker</div>
          <h1 className="mt-1 text-2xl font-semibold text-amber-50">Productivity Goals</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-400">Track coding, study, project, task, habit, reading, health, and custom goals with local progress history, streaks, achievements, and recommendations.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className={ghost} onClick={refresh} disabled={loading}><RefreshCw size={16} /> Refresh</button>
          <button className={button} onClick={() => run(() => api("/evolution/goals/auto-track", { method: "POST" }))} disabled={loading}><TrendingUp size={16} /> Auto Track</button>
        </div>
      </section>

      {error && <div className="rounded-lg border border-red-400/25 bg-red-500/10 p-3 text-sm text-red-100">{error}</div>}

      <section className="grid gap-4 xl:grid-cols-4">
        <Metric label="Active Goals" value={active.length} />
        <Metric label="Completed" value={completed.length} />
        <Metric label="Average Progress" value={`${stats.average_progress_percent ?? 0}%`} />
        <Metric label="Success Rate" value={`${analytics.success_rate ?? 0}%`} />
      </section>

      <section className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <Panel title="Create Goal">
          <div className="grid gap-3">
            <input className={input} value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Goal name" />
            <div className="grid gap-3 sm:grid-cols-4">
              <input className={input} type="number" min="0.1" step="0.1" value={target} onChange={(event) => setTarget(Number(event.target.value))} />
              <select className={input} value={unit} onChange={(event) => setUnit(event.target.value)}>
                {["hours", "minutes", "chapters", "tasks", "pages", "count"].map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
              <select className={input} value={goalType} onChange={(event) => setGoalType(event.target.value)}>
                {["coding", "study", "project", "habit", "health", "task", "assignment", "reading", "automation", "custom"].map((item) => <option key={item} value={item}>{labelize(item)}</option>)}
              </select>
              <input className={input} type="date" value={deadline} onChange={(event) => setDeadline(event.target.value)} />
            </div>
            <button className={button} onClick={() => run(() => api("/evolution/goals", { method: "POST", body: JSON.stringify({ title, target_value: target, unit, goal_type: goalType, period: "daily", deadline, priority: "medium", category: goalType, reminder_settings: { enabled: true } }) }))} disabled={loading || !title.trim()}><Plus size={16} /> Create Goal</button>
          </div>
        </Panel>

        <Panel title="Recommendations">
          <div className="space-y-2">
            {recommendations.length === 0 ? <Empty text="No recommendations yet." /> : recommendations.map((item: AnyRecord, index: number) => (
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

      <section className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <Panel title="Active Goals">
          <div className="space-y-3">
            {goals.length === 0 ? <Empty text="No goals created yet." /> : goals.filter((goal: AnyRecord) => goal.status !== "deleted").slice(0, 12).map((goal: AnyRecord) => (
              <div key={goal.id} className="rounded-lg border border-white/10 bg-black/20 p-3">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <div className="font-medium text-amber-100">{goal.title}</div>
                    <div className="mt-1 text-sm text-slate-400">{labelize(goal.goal_type)} / {formatNumber(goal.current_value)} of {formatNumber(goal.target_value)} {goal.unit}</div>
                  </div>
                  <div className="flex shrink-0 gap-2">
                    <button className={ghost} onClick={() => run(() => api(`/evolution/goals/${goal.id}/increment`, { method: "POST", body: JSON.stringify({ delta_value: 1, source: "dashboard", note: "Quick progress" }) }))} disabled={loading}>+1</button>
                    <button className={button} onClick={() => run(() => api(`/evolution/goals/${goal.id}`, { method: "PUT", body: JSON.stringify({ current_value: goal.target_value, source: "dashboard", note: "Marked complete" }) }))} disabled={loading}><CheckCircle2 size={16} /> Complete</button>
                  </div>
                </div>
                <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/10">
                  <div className="h-full rounded-full bg-amber-300" style={{ width: `${Math.min(100, goal.progress_percent)}%` }} />
                </div>
                <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-500">
                  <span>{goal.progress_percent}% complete</span>
                  <span>{formatNumber(goal.remaining_value)} {goal.unit} remaining</span>
                  {goal.deadline && <span>Due {goal.deadline}</span>}
                  {goal.streak && <span>{goal.streak.current_count} day streak</span>}
                </div>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Streaks & Achievements">
          <div className="grid gap-4">
            <Summary title="Streaks" icon={<TrendingUp size={17} />} items={streaks.slice(0, 6).map((item: AnyRecord) => `${labelize(item.streak_type)}: ${item.current_count} days`)} />
            <Summary title="Achievements" icon={<Award size={17} />} items={achievements.slice(0, 6).map((item: AnyRecord) => item.title)} />
          </div>
        </Panel>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Panel title="Analytics">
          <div className="grid gap-3 sm:grid-cols-2">
            <Metric label="Completion Rate" value={`${analytics.completion_rate ?? 0}%`} />
            <Metric label="Average Completion" value={`${analytics.average_goal_completion_time_days ?? 0} days`} />
            <Metric label="Weekly Updates" value={analytics.weekly_progress?.length ?? 0} />
            <Metric label="Monthly Updates" value={analytics.monthly_progress?.length ?? 0} />
          </div>
          <div className="mt-4">
            <Summary title="Weak Areas" icon={<BarChart3 size={17} />} items={(analytics.weak_areas ?? []).map((goal: AnyRecord) => `${goal.title}: ${goal.progress_percent}%`)} />
          </div>
        </Panel>

        <Panel title="Recent Activity">
          <div className="max-h-[420px] space-y-2 overflow-auto pr-1">
            {history.length === 0 ? <Empty text="No goal history yet." /> : history.slice(0, 20).map((item: AnyRecord) => (
              <div key={item.id} className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium text-amber-100">{item.title}</span>
                  <span className="text-xs text-slate-500">{formatDate(item.created_at)}</span>
                </div>
                <p className="mt-1 text-slate-300">{item.message || item.event_type}</p>
              </div>
            ))}
          </div>
        </Panel>
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-amber-200/10 bg-white/[0.04] p-4">
      <div className="text-sm text-slate-400">{label}</div>
      <div className="mt-1 text-xl font-semibold text-amber-100">{value}</div>
    </div>
  );
}

function Summary({ title, icon, items }: { title: string; icon: React.ReactNode; items: string[] }) {
  return (
    <div>
      <div className="mb-2 flex items-center gap-2 text-sm font-medium text-amber-100">{icon}{title}</div>
      <div className="space-y-2">
        {items.length === 0 ? <Empty text="No data yet." /> : items.map((item) => <div key={item} className="rounded-lg border border-white/10 bg-black/20 p-2 text-sm text-slate-300">{item}</div>)}
      </div>
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm text-slate-500">{text}</div>;
}

function labelize(value: string) {
  return value.split("_").map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" ");
}

function formatDate(value: string | undefined) {
  return value ? new Date(value).toLocaleString() : "--";
}

function formatNumber(value: number | string | undefined) {
  const number = Number(value ?? 0);
  return Number.isInteger(number) ? String(number) : number.toFixed(2);
}
