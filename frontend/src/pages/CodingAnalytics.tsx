import React from "react";
import { Activity, Brain, Clock, Code2, GitBranch, Keyboard, MousePointer2, RefreshCw, ShieldCheck, Sparkles, TimerOff } from "lucide-react";
import { api } from "../lib/api";
import { Panel } from "../components/Panel";

type Report = {
  apps: Record<string, string>;
  real_coding_seconds: number;
  coding_time: string;
  total_time: string;
  deep_coding_seconds: number;
  deep_coding_time: string;
  focus_coding_time: string;
  idle_time: string;
  distraction_time: string;
  activity_score: number;
  productivity_score: number;
  average_session: string;
  longest_session: string;
  files_modified: number;
  commits: number;
  terminal_commands: number;
  builds: number;
  tests: number;
  errors_fixed: number;
  projects: string[];
  project_time: Record<string, string>;
  languages: Record<string, string>;
  insights: string[];
  validation: {
    idle_timeout_seconds: number;
    active_threshold: number;
    counts_only_active_work: boolean;
    excludes_distractions: boolean;
  };
};

export function CodingAnalytics() {
  const [report, setReport] = React.useState<Report | null>(null);
  const [weekly, setWeekly] = React.useState<Report | null>(null);
  const [loading, setLoading] = React.useState(false);
  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const [daily, week] = await Promise.all([api<Report>("/coding/report"), api<Report>("/coding/weekly-report")]);
      setReport(daily);
      setWeekly(week);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { void load(); }, [load]);

  const appChart = Object.entries(report?.apps ?? {}).map(([name, value]) => ({ name, value }));
  const projectChart = Object.entries(report?.project_time ?? {});
  const languages = Object.entries(report?.languages ?? {});

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-[0.28em] text-amber-200/70">Smart Coding Analytics</div>
          <h1 className="text-2xl font-semibold text-slate-50">True Coding Time</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-400">Counts active editor, terminal, Git, navigation, and code-change events. Idle time and distractions are excluded from coding totals.</p>
        </div>
        <button className="nexa-button h-10 rounded-xl px-4 text-sm" onClick={load} disabled={loading}><RefreshCw size={16} /> Refresh</button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric icon={<Code2 size={18} />} label="Real Coding" value={report?.coding_time ?? "0h 0m"} />
        <Metric icon={<Brain size={18} />} label="Deep Coding" value={report?.deep_coding_time ?? "0h 0m"} />
        <Metric icon={<TimerOff size={18} />} label="Idle Removed" value={report?.idle_time ?? "0h 0m"} />
        <Metric icon={<ShieldCheck size={18} />} label="Productivity" value={`${report?.productivity_score ?? 0}%`} />
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1.2fr_0.8fr]">
        <Panel title="Focus Validation">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Metric icon={<Keyboard size={18} />} label="Activity Score" value={`${report?.activity_score ?? 0}%`} />
            <Metric icon={<MousePointer2 size={18} />} label="Focus Coding" value={report?.focus_coding_time ?? "0h 0m"} />
            <Metric icon={<TimerOff size={18} />} label="Distractions" value={report?.distraction_time ?? "0h 0m"} />
          </div>
          <div className="mt-4 grid gap-2 text-sm text-slate-300 sm:grid-cols-2">
            <Check label="Counts only active work" active={report?.validation?.counts_only_active_work ?? true} />
            <Check label={`Idle pauses after ${report?.validation?.idle_timeout_seconds ?? 30}s`} active />
            <Check label="YouTube/Reels/social excluded" active={report?.validation?.excludes_distractions ?? true} />
            <Check label={`Activity threshold ${report?.validation?.active_threshold ?? 55}%`} active />
          </div>
        </Panel>

        <Panel title="AI Coding Insights">
          <div className="space-y-2">
            {(report?.insights ?? []).map((item) => (
              <div key={item} className="nexa-card rounded-xl p-3 text-sm text-slate-200"><Sparkles className="mr-2 inline text-amber-200" size={16} />{item}</div>
            ))}
            {(report?.insights ?? []).length === 0 && <div className="rounded-xl border border-dashed border-amber-200/15 p-5 text-center text-sm text-slate-400">No coding insights yet</div>}
          </div>
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
        <Panel title="Project Tracking">
          <List rows={projectChart.length ? projectChart.map(([name, value]) => [name, value]) : (report?.projects ?? []).map((item) => [item, "Detected"])} empty="No active project time recorded" />
        </Panel>
        <Panel title="Editor Activity">
          <List rows={appChart.map((item) => [item.name, item.value])} empty="No active editor sessions recorded" />
        </Panel>
        <Panel title="Languages">
          <List rows={languages} empty="No language activity recorded" />
        </Panel>
      </div>

      <Panel title="Daily Engineering Metrics">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-6">
          <Metric icon={<Activity size={18} />} label="Files Modified" value={String(report?.files_modified ?? 0)} />
          <Metric icon={<GitBranch size={18} />} label="Commits/Git" value={String(report?.commits ?? 0)} />
          <Metric icon={<Code2 size={18} />} label="Terminal" value={String(report?.terminal_commands ?? 0)} />
          <Metric icon={<ShieldCheck size={18} />} label="Builds" value={String(report?.builds ?? 0)} />
          <Metric icon={<ShieldCheck size={18} />} label="Tests" value={String(report?.tests ?? 0)} />
          <Metric icon={<Brain size={18} />} label="Errors Fixed" value={String(report?.errors_fixed ?? 0)} />
        </div>
      </Panel>

      <Panel title="Weekly Baseline">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
          <Metric icon={<Clock size={18} />} label="Weekly Coding" value={weekly?.coding_time ?? "0h 0m"} />
          <Metric icon={<Brain size={18} />} label="Weekly Deep Work" value={weekly?.deep_coding_time ?? "0h 0m"} />
          <Metric icon={<Activity size={18} />} label="Average Session" value={weekly?.average_session ?? "0h 0m"} />
          <Metric icon={<ShieldCheck size={18} />} label="Longest Session" value={weekly?.longest_session ?? "0h 0m"} />
        </div>
      </Panel>
    </div>
  );
}

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return <div className="nexa-card rounded-xl p-3"><div className="mb-2 flex items-center gap-2 text-xs text-amber-100/70">{icon}{label}</div><div className="text-xl font-semibold text-slate-50">{value}</div></div>;
}

function Check({ label, active }: { label: string; active: boolean }) {
  return <div className="flex items-center gap-2 rounded-xl border border-amber-200/10 bg-black/20 px-3 py-2"><span className={`h-2.5 w-2.5 rounded-full ${active ? "bg-emerald-300" : "bg-slate-500"}`} />{label}</div>;
}

function List({ rows, empty }: { rows: Array<[string, string]>; empty: string }) {
  return <div className="space-y-2">{rows.length ? rows.slice(0, 8).map(([name, value]) => <div key={`${name}-${value}`} className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm"><span className="min-w-0 truncate text-slate-100">{name}</span><span className="shrink-0 text-amber-100">{value}</span></div>) : <div className="rounded-xl border border-dashed border-amber-200/15 p-5 text-center text-sm text-slate-400">{empty}</div>}</div>;
}
