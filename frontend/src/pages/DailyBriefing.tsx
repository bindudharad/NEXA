import React from "react";
import { Bell, CalendarClock, CheckCircle2, CloudSun, History, Lightbulb, Mic, RefreshCw } from "lucide-react";
import { api } from "../lib/api";

type AnyRecord = Record<string, any>;

const panel = "rounded-lg border border-amber-200/10 bg-white/[0.04] p-4";
const button = "inline-flex h-9 items-center gap-2 rounded-lg bg-amber-300 px-3 text-sm font-medium text-black hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-50";
const ghost = "inline-flex h-9 items-center gap-2 rounded-lg border border-amber-200/15 px-3 text-sm text-amber-100 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50";
const input = "h-10 w-full rounded-lg border border-amber-200/10 bg-black/25 px-3 text-sm text-amber-50 outline-none focus:border-amber-300/50";

export function DailyBriefingPage() {
  const [briefing, setBriefing] = React.useState<AnyRecord | null>(null);
  const [history, setHistory] = React.useState<AnyRecord[]>([]);
  const [recommendations, setRecommendations] = React.useState<AnyRecord[]>([]);
  const [analytics, setAnalytics] = React.useState<AnyRecord[]>([]);
  const [settings, setSettings] = React.useState<AnyRecord>({});
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");

  const load = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [latest, rows, recs, stats, config] = await Promise.all([
        api<AnyRecord | null>("/evolution/daily-briefing/latest"),
        api<AnyRecord[]>("/evolution/daily-briefing/history?limit=10"),
        api<AnyRecord[]>("/evolution/daily-briefing/recommendations?limit=10"),
        api<AnyRecord[]>("/evolution/daily-briefing/analytics?limit=14"),
        api<AnyRecord>("/evolution/daily-briefing/settings")
      ]);
      setBriefing(latest);
      setHistory(rows);
      setRecommendations(recs);
      setAnalytics(stats);
      setSettings(config);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load briefing");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void load();
  }, [load]);

  const generate = async (speak = false) => {
    setLoading(true);
    setError("");
    try {
      const latest = await api<AnyRecord>("/evolution/daily-briefing", { method: "POST", body: JSON.stringify({ speak, notify: true }) });
      setBriefing(latest);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate briefing");
      setLoading(false);
    }
  };

  const updateSettings = async (patch: AnyRecord) => {
    const next = { ...settings, ...patch };
    setSettings(next);
    await api("/evolution/daily-briefing/settings", { method: "PUT", body: JSON.stringify(patch) });
  };

  const payload = briefing?.payload ?? {};
  const sections = payload.sections ?? [];
  const coding = payload.coding ?? {};
  const study = payload.study ?? {};
  const notifications = payload.notifications ?? {};
  const goals = payload.goals ?? {};
  const weather = payload.weather ?? {};

  return (
    <div className="space-y-5">
      <section className="flex flex-col gap-3 border-b border-amber-200/10 pb-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm text-amber-200/70"><CalendarClock size={16} /> Personal Secretary</div>
          <h1 className="mt-1 text-2xl font-semibold text-amber-50">Daily Briefing</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-400">A 30-second executive summary of today’s tasks, battery, coding, study, college, goals, notifications, weather, and Nexa health.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className={ghost} onClick={load} disabled={loading}><RefreshCw size={16} /> Refresh</button>
          <button className={ghost} onClick={() => generate(true)} disabled={loading}><Mic size={16} /> Generate Voice</button>
          <button className={button} onClick={() => generate(false)} disabled={loading}><Bell size={16} /> Generate Briefing</button>
        </div>
      </section>

      {error && <div className="rounded-lg border border-red-400/25 bg-red-500/10 p-3 text-sm text-red-100">{error}</div>}

      <section className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <div className={panel}>
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-amber-50">{briefing?.title ?? "Good Morning"}</h2>
            <span className="text-xs text-slate-400">{payload.current_time ?? "--"}</span>
          </div>
          <p className="text-sm leading-6 text-slate-300">{briefing?.summary ?? "No briefing generated yet."}</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Metric label="Battery" value={`${payload.battery?.battery_percent ?? "--"}%`} />
            <Metric label="Charging" value={payload.charging === true ? "Yes" : payload.charging === false ? "No" : "--"} />
            <Metric label="Tasks" value={payload.todays_tasks?.length ?? 0} />
            <Metric label="Unread" value={notifications.unread ?? 0} />
          </div>
        </div>

        <div className={panel}>
          <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-amber-50"><Lightbulb size={18} /> Secretary Recommendations</h2>
          <div className="space-y-2">
            {recommendations.length === 0 ? <Empty text="No recommendations yet." /> : recommendations.slice(0, 5).map((item) => (
              <div key={item.id} className="rounded-lg border border-white/10 bg-black/20 p-3">
                <div className="flex items-center justify-between gap-2 text-sm">
                  <span className="font-medium text-amber-100">{item.title}</span>
                  <span className="text-xs text-slate-500">{item.priority}</span>
                </div>
                <p className="mt-1 text-sm text-slate-400">{item.message}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <SummaryPanel title="Coding Summary" rows={[
          ["Today", formatDuration(coding.today_seconds)],
          ["Yesterday", formatDuration(coding.yesterday_seconds)],
          ["VS Code Usage", coding.vscode_usage ?? 0],
          ["Cursor Usage", coding.cursor_usage ?? 0],
          ["Projects", (coding.projects ?? []).join(", ") || "--"],
          ["Git Commits", coding.git_commits ?? 0],
          ["Files Modified", coding.files_modified ?? 0],
          ["Productivity", `${coding.productivity_score ?? "--"}%`]
        ]} />
        <SummaryPanel title="Study Summary" rows={[
          ["Yesterday", formatDuration(study.yesterday_seconds)],
          ["Upcoming Exams", study.upcoming_exams?.length ?? 0],
          ["Assignments Due", study.assignments_due?.length ?? 0],
          ["Missed Topics", study.missed_topics?.length ?? 0],
          ["Recommended", (study.recommended_topics ?? []).join(", ") || "--"]
        ]} />
        <SummaryPanel title="Goal Summary" rows={[
          ["Average Progress", `${goals.average_percent ?? 0}%`],
          ["Goals", goals.items?.length ?? 0],
          ["Achievements", goals.achievements?.length ?? 0],
          ["Weather", weather.summary ?? "Hidden offline"],
          ["Nexa Status", payload.nexa_status ?? "--"]
        ]} />
      </section>

      <section className={panel}>
        <h2 className="mb-3 text-lg font-semibold text-amber-50">Smart Priority Order</h2>
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-5">
          {sections.slice(0, 10).map((section: AnyRecord) => (
            <div key={section.id} className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm">
              <div className="font-medium text-amber-100">{section.title}</div>
              <div className="text-xs text-slate-500">Priority {section.priority}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <div className={panel}>
          <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-amber-50"><CloudSun size={18} /> Schedule & Delivery</h2>
          <div className="grid gap-3">
            <label className="grid gap-2 text-sm text-slate-300">Time<input className={input} value={settings.time ?? "08:00"} onChange={(event) => updateSettings({ time: event.target.value })} /></label>
            <label className="grid gap-2 text-sm text-slate-300">Days<select className={input} value={settings.days ?? "all"} onChange={(event) => updateSettings({ days: event.target.value })}>{["all", "weekdays", "weekends"].map((item) => <option key={item}>{item}</option>)}</select></label>
            <label className="grid gap-2 text-sm text-slate-300">Weather Location<input className={input} value={settings.weather_location ?? ""} onChange={(event) => updateSettings({ weather_location: event.target.value })} /></label>
            <label className="flex items-center gap-2 text-sm text-slate-300"><input type="checkbox" checked={Boolean(settings.on_startup)} onChange={(event) => updateSettings({ on_startup: event.target.checked })} /> Run on startup</label>
            <label className="flex items-center gap-2 text-sm text-slate-300"><input type="checkbox" checked={Boolean(settings.speak)} onChange={(event) => updateSettings({ speak: event.target.checked })} /> Voice briefing by default</label>
          </div>
        </div>

        <div className={panel}>
          <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-amber-50"><History size={18} /> Briefing History</h2>
          <div className="space-y-2">
            {history.length === 0 ? <Empty text="No briefing history yet." /> : history.map((item) => (
              <div key={item.id} className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium text-amber-100">{item.briefing_date}</span>
                  <span className="text-xs text-slate-500">{item.delivery_method} / {item.delivery_status}</span>
                </div>
                <div className="mt-1 text-slate-400">Generated in {item.statistics?.generation_ms ?? "--"} ms</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className={panel}>
        <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-amber-50"><CheckCircle2 size={18} /> Insights</h2>
        <div className="grid gap-2 md:grid-cols-2">
          {(analytics[0]?.insight?.trend_messages ?? ["Generate a briefing to begin trend analysis."]).map((item: string) => <div key={item} className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm text-slate-300">{item}</div>)}
        </div>
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-white/10 bg-black/20 p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-1 truncate text-sm font-medium text-amber-100">{value}</div>
    </div>
  );
}

function SummaryPanel({ title, rows }: { title: string; rows: Array<[string, React.ReactNode]> }) {
  return (
    <div className={panel}>
      <h2 className="mb-3 text-lg font-semibold text-amber-50">{title}</h2>
      <div className="space-y-2">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between gap-3 border-b border-white/10 pb-2 text-sm last:border-b-0">
            <span className="text-slate-400">{label}</span>
            <span className="max-w-[60%] truncate text-right font-medium text-amber-100">{value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm text-slate-500">{text}</div>;
}

function formatDuration(seconds: number | undefined) {
  const value = Number(seconds ?? 0);
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  return hours ? `${hours}h ${minutes}m` : `${minutes}m`;
}
