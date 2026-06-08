import React from "react";
import { Activity, Cpu, Gauge, Thermometer } from "lucide-react";
import { Panel } from "../components/Panel";
import { api, type ResourceManagerStatus } from "../lib/api";

export function ResourceMonitor() {
  const [status, setStatus] = React.useState<ResourceManagerStatus | null>(null);
  const load = React.useCallback(() => api<ResourceManagerStatus>("/resource-manager/status").then(setStatus), []);

  React.useEffect(() => {
    load();
    const timer = window.setInterval(load, 30000);
    return () => window.clearInterval(timer);
  }, [load]);

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric icon={<Gauge size={18} />} label="Resource Mode" value={status?.mode ?? "normal"} />
        <Metric icon={<Cpu size={18} />} label="Nexa CPU" value={`${status?.process_cpu_percent ?? 0}%`} />
        <Metric icon={<Activity size={18} />} label="Nexa RAM" value={`${status?.process_ram_mb ?? 0} MB`} />
        <Metric icon={<Thermometer size={18} />} label="Health Score" value={`${status?.health_score ?? 100}/100`} />
      </div>

      <Panel title="Nexa Resource Monitor">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Status label="System CPU" value={`${status?.cpu_percent ?? 0}%`} />
          <Status label="Process Threads" value={String(status?.process_threads ?? 0)} />
          <Status label="Power Saving" value={status?.power_saving ? "Active" : "Inactive"} />
          <Status label="Thermal Protection" value={status?.thermal_protection ? "Active" : "Inactive"} />
          <Status label="Heavy Load" value={status?.heavy_load ? "Active" : "Inactive"} />
          <Status label="User Idle" value={status?.user_idle ? "Yes" : "No"} />
          <Status label="Disk Read" value={bytes(status?.disk_read_bytes)} />
          <Status label="Disk Write" value={bytes(status?.disk_write_bytes)} />
          <Status label="Network Sent" value={bytes(status?.network_bytes_sent)} />
          <Status label="Network Received" value={bytes(status?.network_bytes_recv)} />
          <Status label="Battery" value={status?.battery_percent == null ? "N/A" : `${status.battery_percent}%`} />
          <Status label="Charging" value={status?.is_charging == null ? "Unknown" : status.is_charging ? "Charging" : "On battery"} />
        </div>
      </Panel>

      <Panel title="Optimization Policy">
        <div className="grid gap-3 text-sm text-slate-300">
          <Policy label="Power Saving" value="Battery at or below 30% slows non-critical monitors and skips website checks." />
          <Policy label="Thermal Protection" value="High temperature slows background intervals and delays non-critical work." />
          <Policy label="Idle Mode" value="When the user is inactive, UI and notification polling back off." />
          <Policy label="Offline First" value="Local logic handles routine commands before any cloud AI path is used." />
        </div>
      </Panel>
    </div>
  );
}

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="glass-panel rounded-lg p-4">
      <div className="mb-3 flex items-center gap-2 text-sm text-amber-100/70">{icon}{label}</div>
      <div className="break-words text-2xl font-semibold">{value}</div>
    </div>
  );
}

function Status({ label, value }: { label: string; value: string }) {
  return <div className="nexa-card rounded-lg p-4"><div className="mb-2 text-xs text-amber-100/70">{label}</div><div className="break-words text-lg font-semibold text-slate-100">{value}</div></div>;
}

function Policy({ label, value }: { label: string; value: string }) {
  return <div className="nexa-card rounded-lg p-3"><span className="font-semibold text-amber-100">{label}: </span>{value}</div>;
}

function bytes(value: number | null | undefined) {
  if (value == null) return "0 B";
  if (value >= 1024 * 1024 * 1024) return `${(value / (1024 * 1024 * 1024)).toFixed(1)} GB`;
  if (value >= 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  if (value >= 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${value} B`;
}
