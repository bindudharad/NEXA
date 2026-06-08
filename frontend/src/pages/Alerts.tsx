import React from "react";
import { Bell, CheckCheck, Download, Search, Trash2 } from "lucide-react";
import { Panel } from "../components/Panel";
import { api, type NotificationAlert } from "../lib/api";

const severities = ["all", "low", "medium", "high", "critical"];

export function Alerts() {
  const [alerts, setAlerts] = React.useState<NotificationAlert[]>([]);
  const [query, setQuery] = React.useState("");
  const [severity, setSeverity] = React.useState("all");
  const [unreadOnly, setUnreadOnly] = React.useState(false);
  const [stats, setStats] = React.useState<{ total: number; unread: number; by_severity: Record<string, number> } | null>(null);

  const load = React.useCallback(() => {
    const params = new URLSearchParams();
    if (query.trim()) params.set("q", query.trim());
    if (severity !== "all") params.set("severity", severity);
    if (unreadOnly) params.set("unread_only", "true");
    api<NotificationAlert[]>(`/notifications?${params.toString()}`).then(setAlerts);
    api<{ total: number; unread: number; by_severity: Record<string, number> }>("/notifications/stats").then(setStats);
  }, [query, severity, unreadOnly]);

  React.useEffect(() => {
    load();
  }, [load]);

  async function markRead(id: number) {
    await api<NotificationAlert>(`/notifications/${id}/read?read=true`, { method: "PUT" });
    load();
  }

  async function recordAction(id: number, action: string) {
    await api<NotificationAlert>(`/notifications/${id}/actions`, { method: "POST", body: JSON.stringify({ action }) });
    load();
  }

  async function deleteAlert(id: number) {
    await api(`/notifications/${id}`, { method: "DELETE" });
    load();
  }

  async function exportAlerts() {
    const data = await api<{ notifications: NotificationAlert[] }>("/notifications/export");
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "nexa-alert-history.json";
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Summary label="Total Alerts" value={String(stats?.total ?? 0)} />
        <Summary label="Unread" value={String(stats?.unread ?? 0)} />
        <Summary label="High/Critical" value={String((stats?.by_severity.high ?? 0) + (stats?.by_severity.critical ?? 0))} />
      </div>

      <Panel
        title="Notification Center"
        action={
          <button className="grid h-9 w-9 place-items-center rounded-lg text-slate-200 hover:bg-white/10" onClick={exportAlerts} aria-label="Export alerts">
            <Download size={17} />
          </button>
        }
      >
        <div className="mb-4 grid gap-3 lg:grid-cols-[1fr_160px_auto]">
          <label className="nexa-input flex h-10 items-center gap-2 rounded-lg px-3">
            <Search size={16} className="shrink-0 text-amber-100/70" />
            <input className="min-w-0 flex-1 bg-transparent text-sm outline-none" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search alerts" />
          </label>
          <select className="nexa-input h-10 rounded-lg px-3 text-sm" value={severity} onChange={(event) => setSeverity(event.target.value)}>
            {severities.map((item) => <option key={item} value={item}>{item === "all" ? "All severity" : item}</option>)}
          </select>
          <label className="nexa-card flex h-10 items-center gap-2 rounded-lg px-3 text-sm text-slate-200">
            <input type="checkbox" checked={unreadOnly} onChange={(event) => setUnreadOnly(event.target.checked)} />
            Unread
          </label>
        </div>
        <div className="max-h-[620px] space-y-3 overflow-auto pr-1">
          {alerts.map((alert) => (
            <article key={alert.id} className={`rounded-lg border p-4 ${alert.read ? "border-amber-200/10 bg-white/[0.035]" : "border-amber-300/30 bg-amber-300/[0.055]"}`}>
              <div className="grid gap-3 xl:grid-cols-[1fr_auto]">
                <div className="min-w-0">
                  <div className="mb-1 flex flex-wrap items-center gap-2">
                    <span className="grid h-7 w-7 place-items-center rounded-lg" style={{ backgroundColor: `${alert.color}24`, color: alert.color }}><Bell size={15} /></span>
                    <h3 className="break-words text-sm font-semibold text-slate-100">{alert.title}</h3>
                    <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs text-slate-300">{alert.severity}</span>
                    <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs text-slate-300">{alert.module}</span>
                  </div>
                  <p className="whitespace-pre-line break-words text-sm text-slate-300">{alert.message}</p>
                  <div className="mt-3 grid gap-1 text-xs text-slate-400 sm:grid-cols-2">
                    <span>{new Date(alert.timestamp).toLocaleString()}</span>
                    <span>Action: {alert.suggested_action}</span>
                    <span>Sound: {alert.sound_used ? alert.sound_used.split(/[\\/]/).pop() : "none"}</span>
                    <span>Voice: {alert.voice_used || "none"}</span>
                  </div>
                </div>
                <div className="flex flex-wrap items-start gap-2 xl:justify-end">
                  {alert.action_buttons.map((button) => (
                    <button key={button} className="h-9 rounded-lg bg-accent px-3 text-xs font-medium text-obsidian" onClick={() => recordAction(alert.id, button)}>{button}</button>
                  ))}
                  <button className="grid h-9 w-9 place-items-center rounded-lg bg-white/10 text-slate-200 hover:bg-white/15" onClick={() => markRead(alert.id)} aria-label="Mark read">
                    <CheckCheck size={16} />
                  </button>
                  <button className="grid h-9 w-9 place-items-center rounded-lg bg-red-500/15 text-red-200 hover:bg-red-500/25" onClick={() => deleteAlert(alert.id)} aria-label="Delete alert">
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            </article>
          ))}
          {alerts.length === 0 && <div className="rounded-lg border border-dashed border-amber-200/15 px-3 py-8 text-center text-sm text-slate-400">No alerts found</div>}
        </div>
      </Panel>
    </div>
  );
}

function Summary({ label, value }: { label: string; value: string }) {
  return (
    <div className="glass-panel rounded-lg p-4">
      <div className="text-xs text-amber-100/70">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-slate-100">{value}</div>
    </div>
  );
}
