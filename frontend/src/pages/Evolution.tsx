import React from "react";
import { Award, BookOpen, BrainCircuit, BriefcaseBusiness, CalendarClock, Download, GraduationCap, HeartPulse, Play, Shield, Sparkles, Target, Timer, Wand2 } from "lucide-react";
import { api } from "../lib/api";

type AnyRecord = Record<string, any>;

const panel = "rounded-lg border border-amber-200/10 bg-white/[0.04] p-4";
const button = "inline-flex h-9 items-center gap-2 rounded-lg bg-amber-300 px-3 text-sm font-medium text-black hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-50";
const ghost = "inline-flex h-9 items-center gap-2 rounded-lg border border-amber-200/15 px-3 text-sm text-amber-100 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50";
const input = "h-10 w-full rounded-lg border border-amber-200/10 bg-black/25 px-3 text-sm text-amber-50 outline-none placeholder:text-slate-500 focus:border-amber-300/50";

export function Evolution() {
  const [overview, setOverview] = React.useState<AnyRecord | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");
  const [studyTitle, setStudyTitle] = React.useState("DBMS Exam Plan");
  const [topics, setTopics] = React.useState("ER model,SQL normalization,Transactions");
  const [goalTitle, setGoalTitle] = React.useState("Code 4 Hours");
  const [automationPrompt, setAutomationPrompt] = React.useState("When battery reaches 20% notify me");
  const [timelineQuery, setTimelineQuery] = React.useState("");

  const refresh = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setOverview(await api<AnyRecord>("/evolution/overview"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Evolution data");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void refresh();
  }, [refresh]);

  const run = async (operation: () => Promise<unknown>) => {
    setLoading(true);
    setError("");
    try {
      await operation();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Operation failed");
    } finally {
      setLoading(false);
    }
  };

  const searchTimeline = async () => {
    setLoading(true);
    setError("");
    try {
      const rows = await api<AnyRecord[]>(`/evolution/timeline?q=${encodeURIComponent(timelineQuery)}`);
      setOverview((current) => ({ ...(current ?? {}), timeline: rows }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Timeline search failed");
    } finally {
      setLoading(false);
    }
  };

  const suggestions = overview?.copilot ?? [];
  const goals = overview?.goals ?? [];
  const achievements = overview?.achievements ?? [];
  const timeline = overview?.timeline ?? [];
  const college = overview?.college ?? [];
  const selfHealth = overview?.self_health;
  const focus = overview?.focus;
  const briefing = overview?.briefing;

  return (
    <div className="space-y-5">
      <section className="flex flex-col gap-3 border-b border-amber-200/10 pb-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm text-amber-200/70"><Sparkles size={16} /> Evolution Pack v2.0</div>
          <h1 className="mt-1 text-2xl font-semibold text-amber-50">Copilot, College, Productivity, Recovery</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-400">Event-driven assistant modules with database history, notifications, voice command hooks, and mobile-ready API output.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className={ghost} onClick={refresh} disabled={loading}><Play size={16} /> Refresh</button>
          <button className={button} onClick={() => run(() => api("/evolution/copilot/evaluate", { method: "POST" }))} disabled={loading}><BrainCircuit size={16} /> Evaluate Copilot</button>
        </div>
      </section>

      {error && <div className="rounded-lg border border-red-400/25 bg-red-500/10 p-3 text-sm text-red-100">{error}</div>}

      <section className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <div className={panel}>
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="flex items-center gap-2 text-lg font-semibold text-amber-50"><BrainCircuit size={18} /> AI Copilot</h2>
            <span className="text-xs text-slate-400">{suggestions.length} suggestions</span>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {suggestions.length === 0 ? <Empty text="No copilot suggestions yet." /> : suggestions.map((item: AnyRecord) => (
              <div key={item.id} className="rounded-lg border border-white/10 bg-black/20 p-3">
                <div className="text-sm font-medium text-amber-100">{item.title}</div>
                <p className="mt-1 text-sm text-slate-300">{item.message}</p>
                <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
                  <span>{item.suggestion_type}</span><span>{item.severity}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className={panel}>
          <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-amber-50"><HeartPulse size={18} /> Nexa Self Health</h2>
          <Metric label="Health Score" value={`${selfHealth?.health_score ?? "--"}%`} />
          <Metric label="Automations" value={selfHealth?.automations ?? "--"} />
          <Metric label="Notifications" value={selfHealth?.notifications ?? "--"} />
          <Metric label="Errors" value={selfHealth?.errors ?? "--"} />
          <div className="mt-3 space-y-1 text-sm text-slate-400">
            {(selfHealth?.recommendations ?? []).map((item: string) => <div key={item}>{item}</div>)}
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <div className={panel}>
          <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-amber-50"><CalendarClock size={18} /> Daily Briefing</h2>
          <p className="min-h-16 text-sm text-slate-300">{briefing?.summary ?? "Generate a daily briefing for tasks, battery, coding, notifications, and automations."}</p>
          <button className={`${button} mt-4`} onClick={() => run(() => api("/evolution/daily-briefing", { method: "POST", body: JSON.stringify({ speak: false, notify: true }) }))} disabled={loading}>Generate</button>
        </div>

        <div className={panel}>
          <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-amber-50"><Timer size={18} /> Focus Mode</h2>
          <p className="text-sm text-slate-300">{focus ? `${focus.title} is active since ${new Date(focus.started_at).toLocaleTimeString()}` : "No active focus session."}</p>
          <div className="mt-4 flex gap-2">
            <button className={button} onClick={() => run(() => api("/evolution/focus/start", { method: "POST", body: JSON.stringify({ title: "Study Focus", duration_minutes: 25, break_minutes: 5 }) }))} disabled={loading || Boolean(focus)}>Start</button>
            <button className={ghost} onClick={() => run(() => api("/evolution/focus/end", { method: "POST", body: JSON.stringify({ tasks_completed: 1, distraction_count: 0 }) }))} disabled={loading || !focus}>End</button>
          </div>
        </div>

        <div className={panel}>
          <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-amber-50"><GraduationCap size={18} /> College Companion</h2>
          <p className="text-sm text-slate-300">{college[0]?.message ?? "Connect KCET, Contineo, or ERP profiles from Website Vault."}</p>
          <button className={`${button} mt-4`} onClick={() => run(() => api("/evolution/college/check", { method: "POST", body: JSON.stringify({ source: "college" }) }))} disabled={loading}>Check Updates</button>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <div className={panel}>
          <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-amber-50"><BookOpen size={18} /> Smart Study Assistant</h2>
          <div className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
            <input className={input} value={studyTitle} onChange={(event) => setStudyTitle(event.target.value)} />
            <input className={input} value={topics} onChange={(event) => setTopics(event.target.value)} />
            <button className={button} onClick={() => run(() => api("/evolution/study/plans", { method: "POST", body: JSON.stringify({ title: studyTitle, topics: topics.split(",").map((item) => item.trim()).filter(Boolean) }) }))} disabled={loading}>Create</button>
          </div>
        </div>

        <div className={panel}>
          <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-amber-50"><Wand2 size={18} /> Automation Builder</h2>
          <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
            <input className={input} value={automationPrompt} onChange={(event) => setAutomationPrompt(event.target.value)} />
            <button className={button} onClick={() => run(() => api("/evolution/automation-builder", { method: "POST", body: JSON.stringify({ prompt: automationPrompt }) }))} disabled={loading}>Build</button>
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <div className={panel}>
          <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-amber-50"><Target size={18} /> Goal Tracker</h2>
          <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
            <input className={input} value={goalTitle} onChange={(event) => setGoalTitle(event.target.value)} />
            <button className={button} onClick={() => run(() => api("/evolution/goals", { method: "POST", body: JSON.stringify({ title: goalTitle, target_value: 4, unit: "hours", goal_type: "coding" }) }))} disabled={loading}>Add</button>
          </div>
          <div className="mt-3 space-y-2">
            {goals.slice(0, 4).map((goal: AnyRecord) => <Metric key={goal.id} label={goal.title} value={`${goal.progress_percent}%`} />)}
          </div>
        </div>

        <div className={panel}>
          <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-amber-50"><Award size={18} /> Achievements</h2>
          <div className="space-y-2">
            {achievements.length === 0 ? <Empty text="No achievements unlocked yet." /> : achievements.slice(0, 5).map((item: AnyRecord) => <Metric key={item.id} label={item.title} value={item.unlocked ? "Unlocked" : `${item.progress_percent}%`} />)}
          </div>
        </div>

        <div className={panel}>
          <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-amber-50"><Download size={18} /> Downloads</h2>
          <p className="text-sm text-slate-300">Categorize PDFs, archives, images, videos, documents, programs, and code files on demand.</p>
          <button className={`${ghost} mt-4`} onClick={() => run(() => api("/evolution/downloads/scan", { method: "POST", body: JSON.stringify({}) }))} disabled={loading}>Scan Downloads</button>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1fr_0.8fr]">
        <div className={panel}>
          <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-amber-50"><BriefcaseBusiness size={18} /> Memory Timeline</h2>
          <div className="mb-3 grid gap-2 sm:grid-cols-[1fr_auto]">
            <input className={input} placeholder="Search timeline" value={timelineQuery} onChange={(event) => setTimelineQuery(event.target.value)} />
            <button className={ghost} onClick={searchTimeline} disabled={loading}>Search</button>
          </div>
          <div className="space-y-2">
            {timeline.length === 0 ? <Empty text="No timeline events yet." /> : timeline.map((event: AnyRecord) => (
              <div key={event.id} className="flex items-start justify-between gap-3 rounded-lg border border-white/10 bg-black/20 p-3 text-sm">
                <div>
                  <div className="font-medium text-amber-100">{event.title}</div>
                  <div className="text-slate-400">{event.description || event.source}</div>
                </div>
                <span className="shrink-0 text-xs text-slate-500">{event.event_type}</span>
              </div>
            ))}
          </div>
        </div>

        <div className={panel}>
          <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-amber-50"><Shield size={18} /> Project Guardian</h2>
          <p className="text-sm text-slate-300">Recovery snapshots are available through the API before high-risk project actions. Git push, delete, shutdown, and restart flows should call this before approval execution.</p>
          <div className="mt-4 rounded-lg border border-white/10 bg-black/20 p-3 text-xs text-slate-400">Endpoint: POST /api/evolution/project-guardian/snapshot</div>
        </div>
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-white/10 py-2 text-sm last:border-b-0">
      <span className="min-w-0 truncate text-slate-400">{label}</span>
      <span className="shrink-0 font-medium text-amber-100">{value}</span>
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm text-slate-500">{text}</div>;
}
