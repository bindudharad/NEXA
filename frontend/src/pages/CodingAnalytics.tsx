import React from "react";
import { api } from "../lib/api";
import { Panel } from "../components/Panel";

type Report = { apps: Record<string, string>; files_modified: number; commits: number; projects: string[] };

export function CodingAnalytics() {
  const [report, setReport] = React.useState<Report | null>(null);
  React.useEffect(() => { api<Report>("/coding/report").then(setReport); }, []);
  const chart = Object.entries(report?.apps ?? {}).map(([name, value]) => ({ name, minutes: Number(value.split("h")[0]) * 60 + Number(value.split("h ")[1]?.replace("m", "") ?? 0) }));
  const max = Math.max(1, ...chart.map((item) => item.minutes));

  return (
    <div className="space-y-5">
      <Panel title="Coding Today">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Summary label="Files Modified" value={String(report?.files_modified ?? 0)} />
          <Summary label="Commits" value={String(report?.commits ?? 0)} />
          <Summary label="Projects" value={String(report?.projects.length ?? 0)} />
        </div>
        <div className="mt-5 space-y-3">
          {chart.length === 0 && <div className="rounded-xl border border-dashed border-amber-200/15 px-3 py-8 text-center text-sm text-slate-400">No coding activity recorded yet</div>}
          {chart.map((item) => (
            <div className="grid gap-2" key={item.name}>
              <div className="flex items-center justify-between text-xs text-slate-300">
                <span>{item.name}</span>
                <span>{item.minutes}m</span>
              </div>
              <div className="h-3 overflow-hidden rounded-full bg-white/8">
                <div className="h-full rounded-full bg-accent" style={{ width: `${Math.max(6, (item.minutes / max) * 100)}%` }} />
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function Summary({ label, value }: { label: string; value: string }) {
  return <div className="nexa-card rounded-xl p-3"><div className="text-xs text-amber-100/70">{label}</div><div className="text-xl font-semibold">{value}</div></div>;
}
