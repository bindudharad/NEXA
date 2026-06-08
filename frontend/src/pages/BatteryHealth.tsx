import React from "react";
import { BatteryCharging, Download, PlugZap, Search } from "lucide-react";
import { Panel } from "../components/Panel";
import { api, type PowerHistory, type PowerMonitorStatus } from "../lib/api";

export function BatteryHealth() {
  const [status, setStatus] = React.useState<PowerMonitorStatus | null>(null);
  const [history, setHistory] = React.useState<PowerHistory | null>(null);
  const [recommendations, setRecommendations] = React.useState<Array<{ title: string; message: string; severity: string }>>([]);
  const [query, setQuery] = React.useState("");

  const load = React.useCallback(() => {
    const params = new URLSearchParams();
    if (query.trim()) params.set("q", query.trim());
    api<PowerMonitorStatus>("/power-monitor/status").then(setStatus);
    api<PowerHistory>(`/power-monitor/history?${params.toString()}`).then(setHistory);
    api<Array<{ title: string; message: string; severity: string }>>("/power-monitor/recommendations").then(setRecommendations);
  }, [query]);

  React.useEffect(() => {
    load();
    const timer = window.setInterval(load, 30000);
    return () => window.clearInterval(timer);
  }, [load]);

  async function exportHistory() {
    const data = await api<PowerHistory & { exported_at: string }>("/power-monitor/export");
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "nexa-power-history.json";
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Battery" value={status?.battery_percent == null ? "N/A" : `${status.battery_percent}%`} />
        <Metric label="Charging" value={status?.is_charging == null ? "Unknown" : status.is_charging ? "Charging" : "On battery"} />
        <Metric label="Health Score" value={status?.battery_health_percent == null ? "Unknown" : `${status.battery_health_percent}%`} />
        <Metric label="Wear" value={status?.battery_wear_percent == null ? "Unknown" : `${status.battery_wear_percent}%`} />
      </div>

      <Panel title="Battery Health Dashboard" action={<button className="grid h-9 w-9 place-items-center rounded-lg text-slate-200 hover:bg-white/10" onClick={exportHistory} aria-label="Export power history"><Download size={17} /></button>}>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Status label="Power Source" value={status?.power_source ?? "unknown"} />
          <Status label="Adapter Status" value={status?.adapter_status ?? "unknown"} />
          <Status label="Charge Cycles" value={fmt(status?.charge_cycles)} />
          <Status label="Charging Speed" value={status?.charging_speed_percent_per_hour == null ? "N/A" : `${status.charging_speed_percent_per_hour}%/h`} />
          <Status label="Full Charge Capacity" value={capacity(status?.full_charge_capacity_mwh)} />
          <Status label="Design Capacity" value={capacity(status?.design_capacity_mwh)} />
          <Status label="Estimated Remaining" value={seconds(status?.estimated_remaining_seconds)} />
          <Status label="Battery Temperature" value={status?.battery_temperature_celsius == null ? "Unavailable" : `${status.battery_temperature_celsius}°C`} />
          <Status label="Average Daily Usage" value={status?.average_daily_usage_percent == null ? "Learning" : `${status.average_daily_usage_percent}%`} />
          <Status label="Average Charging Time" value={seconds(status?.average_charging_time_seconds)} />
          <Status label="Battery Age" value={status?.battery_age_days == null ? "Unavailable" : `${status.battery_age_days} days`} />
          <Status label="Last Full Charge" value={status?.last_full_charge_time ? new Date(status.last_full_charge_time).toLocaleString() : "Not recorded"} />
          <Status label="Active Session" value={status?.active_charge_session_id ? `#${status.active_charge_session_id}` : "None"} />
          <Status label="Last Power Event" value={status?.last_event_type ?? "None"} />
          <Status label="Monitor Mode" value={status?.testing_mode ? "Simulation" : "Live"} />
        </div>
      </Panel>

      <Panel title="Smart Charging Recommendations">
        <div className="grid gap-3">
          {recommendations.map((item) => (
            <div key={item.title} className="rounded-lg border border-amber-200/15 bg-white/[0.045] p-3">
              <div className="text-sm font-semibold text-slate-100">{item.title}</div>
              <div className="mt-1 text-sm text-slate-300">{item.message}</div>
            </div>
          ))}
          {recommendations.length === 0 && <div className="rounded-lg border border-dashed border-amber-200/15 px-3 py-6 text-center text-sm text-slate-400">No battery recommendations yet</div>}
        </div>
      </Panel>

      <Panel title="Power Event History">
        <div className="mb-4 max-w-xl">
          <label className="nexa-input flex h-10 items-center gap-2 rounded-lg px-3">
            <Search size={16} className="shrink-0 text-amber-100/70" />
            <input className="min-w-0 flex-1 bg-transparent text-sm outline-none" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search power events" />
          </label>
        </div>
        <div className="max-h-[420px] space-y-2 overflow-auto pr-1">
          {(history?.events ?? []).map((event) => (
            <div key={event.id} className="nexa-card rounded-lg p-3">
              <div className="flex flex-wrap items-center gap-2">
                <PlugZap size={15} className="text-amber-200" />
                <div className="text-sm font-semibold text-slate-100">{event.title}</div>
                <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs text-slate-300">{event.event_type}</span>
              </div>
              <div className="mt-1 whitespace-pre-line text-sm text-slate-300">{event.message}</div>
              <div className="mt-2 text-xs text-slate-400">{new Date(event.created_at).toLocaleString()} · {event.power_source}</div>
            </div>
          ))}
          {(history?.events ?? []).length === 0 && <div className="rounded-lg border border-dashed border-amber-200/15 px-3 py-6 text-center text-sm text-slate-400">No power events recorded</div>}
        </div>
      </Panel>

      <Panel title="Charge Session History">
        <div className="grid gap-2">
          {(history?.charge_sessions ?? []).map((session) => (
            <div key={session.id} className="nexa-card grid gap-2 rounded-lg p-3 text-sm sm:grid-cols-[1fr_auto] sm:items-center">
              <div>
                <div className="font-semibold text-slate-100">Started {new Date(session.started_at).toLocaleString()}</div>
                <div className="text-slate-300">{fmt(session.start_percent)}% to {session.end_percent == null ? "active" : `${session.end_percent}%`} · +{session.charge_added_percent}% · {seconds(session.duration_seconds)}</div>
              </div>
              <span className="w-fit rounded-full bg-amber-300/15 px-2.5 py-1 text-xs text-amber-100">{session.status}</span>
            </div>
          ))}
          {(history?.charge_sessions ?? []).length === 0 && <div className="rounded-lg border border-dashed border-amber-200/15 px-3 py-6 text-center text-sm text-slate-400">No charge sessions recorded</div>}
        </div>
      </Panel>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="glass-panel rounded-lg p-4">
      <div className="mb-3 flex items-center gap-2 text-sm text-amber-100/70"><BatteryCharging size={18} />{label}</div>
      <div className="text-2xl font-semibold">{value}</div>
    </div>
  );
}

function Status({ label, value }: { label: string; value: string }) {
  return <div className="nexa-card rounded-lg p-4"><div className="mb-2 text-xs text-amber-100/70">{label}</div><div className="break-words text-lg font-semibold text-slate-100">{value}</div></div>;
}

function fmt(value: number | null | undefined) {
  return value == null ? "N/A" : String(value);
}

function capacity(value: number | null | undefined) {
  return value == null ? "Unavailable" : `${value} mWh`;
}

function seconds(value: number | null | undefined) {
  if (value == null || value < 0) return "Unknown";
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;
}
