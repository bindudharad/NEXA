import React from "react";
import { Brain, CalendarDays, Clock, Filter, RefreshCw, Search, Sparkles } from "lucide-react";
import { api } from "../lib/api";

type AnyRecord = Record<string, any>;
type MemoryRow = { id: number; key: string; value: string; scope: string };

const panel = "rounded-lg border border-amber-200/10 bg-white/[0.04] p-4";
const button = "inline-flex h-9 items-center gap-2 rounded-lg bg-amber-300 px-3 text-sm font-medium text-black hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-50";
const ghost = "inline-flex h-9 items-center gap-2 rounded-lg border border-amber-200/15 px-3 text-sm text-amber-100 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50";
const input = "h-10 w-full rounded-lg border border-amber-200/10 bg-black/25 px-3 text-sm text-amber-50 outline-none placeholder:text-slate-500 focus:border-amber-300/50";

export function Memory() {
  const [view, setView] = React.useState("today");
  const [eventType, setEventType] = React.useState("");
  const [query, setQuery] = React.useState("");
  const [timeline, setTimeline] = React.useState<AnyRecord | null>(null);
  const [searchResult, setSearchResult] = React.useState<AnyRecord | null>(null);
  const [rows, setRows] = React.useState<MemoryRow[]>([]);
  const [key, setKey] = React.useState("");
  const [value, setValue] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");

  const load = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ view });
      if (eventType) params.set("event_type", eventType);
      if (query) params.set("q", query);
      const [dashboard, memory] = await Promise.all([
        api<AnyRecord>(`/evolution/timeline/dashboard?${params.toString()}`),
        api<MemoryRow[]>("/memory"),
      ]);
      setTimeline(dashboard);
      setRows(memory);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load memory timeline");
    } finally {
      setLoading(false);
    }
  }, [eventType, query, view]);

  React.useEffect(() => {
    void load();
  }, [load]);

  async function save() {
    await api("/memory", { method: "POST", body: JSON.stringify({ key, value }) });
    setKey("");
    setValue("");
    await load();
  }

  async function naturalSearch() {
    setLoading(true);
    setError("");
    try {
      setSearchResult(await api<AnyRecord>("/evolution/timeline/search", { method: "POST", body: JSON.stringify({ query }) }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Timeline search failed");
    } finally {
      setLoading(false);
    }
  }

  const events = timeline?.events ?? [];
  const insights = timeline?.insights ?? [];
  const stats = timeline?.stats ?? {};

  return (
    <div className="space-y-5">
      <section className="flex flex-col gap-3 border-b border-amber-200/10 pb-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm text-amber-200/70"><Brain size={16} /> AI Memory Timeline</div>
          <h1 className="mt-1 text-2xl font-semibold text-amber-50">Personal Activity Memory</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-400">Remember coding, study, focus, goals, projects, automations, college updates, downloads, and achievements.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className={ghost} onClick={load} disabled={loading}><RefreshCw size={16} /> Refresh</button>
          <button className={button} onClick={naturalSearch} disabled={loading || !query}><Search size={16} /> Search Memory</button>
        </div>
      </section>

      {error && <div className="rounded-lg border border-red-400/25 bg-red-500/10 p-3 text-sm text-red-100">{error}</div>}

      <section className="grid gap-3 lg:grid-cols-[160px_160px_1fr]">
        <select className={input} value={view} onChange={(event) => setView(event.target.value)}>
          {["today", "week", "month", "year"].map((item) => <option key={item}>{item}</option>)}
        </select>
        <select className={input} value={eventType} onChange={(event) => setEventType(event.target.value)}>
          <option value="">all</option>
          {["coding", "study", "focus", "goal", "automation", "download", "college", "project", "achievement", "briefing"].map((item) => <option key={item}>{item}</option>)}
        </select>
        <input className={input} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Ask: What did I do yesterday? Show study history. Show last week's coding." />
      </section>

      <section className="grid gap-4 xl:grid-cols-4">
        <Metric title="Events" value={stats.total_events ?? 0} icon={<CalendarDays size={18} />} />
        <Metric title="Coding" value={formatDuration(stats.coding_seconds)} icon={<Clock size={18} />} />
        <Metric title="Study" value={formatDuration(stats.study_seconds)} icon={<Clock size={18} />} />
        <Metric title="Focus" value={formatDuration(stats.focus_seconds)} icon={<Clock size={18} />} />
      </section>

      <section className="grid gap-4 xl:grid-cols-[1fr_0.8fr]">
        <div className={panel}>
          <h2 className="mb-2 flex items-center gap-2 text-lg font-semibold text-amber-50"><Sparkles size={18} /> Summary</h2>
          <p className="text-sm text-slate-300">{timeline?.summary?.summary ?? "No summary generated yet."}</p>
          {searchResult && <div className="mt-3 rounded-lg border border-amber-200/10 bg-black/20 p-3 text-sm text-amber-100">{searchResult.summary}</div>}
        </div>

        <div className={panel}>
          <h2 className="mb-2 flex items-center gap-2 text-lg font-semibold text-amber-50"><Filter size={18} /> Insights</h2>
          <div className="space-y-2">
            {insights.length === 0 ? <Empty text="No insights yet." /> : insights.slice(0, 5).map((item: AnyRecord) => (
              <div key={item.id} className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm">
                <div className="font-medium text-amber-100">{item.title}</div>
                <div className="mt-1 text-slate-400">{item.message}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className={panel}>
        <h2 className="mb-3 text-lg font-semibold text-amber-50">Chronological Timeline</h2>
        <div className="space-y-2">
          {events.length === 0 ? <Empty text="No timeline events found." /> : events.map((event: AnyRecord) => (
            <div key={event.id} className="grid gap-3 rounded-lg border border-white/10 bg-black/20 p-3 text-sm md:grid-cols-[130px_120px_1fr_90px]">
              <div className="text-slate-500">{new Date(event.created_at).toLocaleString()}</div>
              <div className="text-amber-100">{event.event_type}</div>
              <div>
                <div className="font-medium text-slate-200">{event.title}</div>
                <div className="text-slate-500">{event.description || event.source}</div>
              </div>
              <div className="text-right text-slate-500">{formatDuration(event.duration_seconds)}</div>
            </div>
          ))}
        </div>
      </section>

      <section className={panel}>
        <h2 className="mb-3 text-lg font-semibold text-amber-50">Stored Memories</h2>
        <div className="mb-4 grid grid-cols-1 gap-2 md:grid-cols-[220px_1fr_90px]">
          <input className={input} value={key} onChange={(event) => setKey(event.target.value)} placeholder="Key" />
          <input className={input} value={value} onChange={(event) => setValue(event.target.value)} placeholder="Value" />
          <button className={button} onClick={save} disabled={!key || !value}>Save</button>
        </div>
        <div className="grid gap-2 md:grid-cols-2">
          {rows.map((row) => <div className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm" key={row.id}><strong className="text-amber-100">{row.key}</strong><div className="break-words text-slate-300">{row.value}</div></div>)}
        </div>
      </section>
    </div>
  );
}

function Metric({ title, value, icon }: { title: string; value: React.ReactNode; icon: React.ReactNode }) {
  return <div className={panel}><div className="mb-2 flex items-center gap-2 text-sm text-slate-400">{icon}{title}</div><div className="text-2xl font-semibold text-amber-50">{value}</div></div>;
}

function Empty({ text }: { text: string }) {
  return <div className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm text-slate-500">{text}</div>;
}

function formatDuration(seconds?: number) {
  const value = Number(seconds ?? 0);
  if (value <= 0) return "0m";
  const hours = Math.floor(value / 3600);
  const minutes = Math.round((value % 3600) / 60);
  return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;
}
