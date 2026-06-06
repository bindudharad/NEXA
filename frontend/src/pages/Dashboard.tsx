import React from "react";
import { Activity, Cpu, HardDrive, RefreshCw, ShieldCheck } from "lucide-react";
import { api, type BatteryAlertStatus, type Task } from "../lib/api";
import { Panel } from "../components/Panel";

type DashboardData = {
  system: { cpu_percent: number; ram_percent: number; battery_percent: number | null };
  battery_alert: BatteryAlertStatus;
  tasks: Task[];
  automations: unknown[];
  notifications: { id: number; title: string; message: string }[];
  scheduled_jobs: unknown[];
};

export function Dashboard() {
  const [data, setData] = React.useState<DashboardData | null>(null);
  const load = React.useCallback(() => api<DashboardData>("/dashboard").then(setData), []);
  React.useEffect(() => {
    load();
    const timer = window.setInterval(load, 5000);
    return () => window.clearInterval(timer);
  }, [load]);

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric icon={<Cpu size={18} />} label="CPU" value={`${data?.system.cpu_percent ?? 0}%`} />
        <Metric icon={<HardDrive size={18} />} label="RAM" value={`${data?.system.ram_percent ?? 0}%`} />
        <Metric icon={<ShieldCheck size={18} />} label="Battery" value={data?.system.battery_percent == null ? "N/A" : `${data.system.battery_percent}%`} />
        <Metric icon={<RefreshCw size={18} />} label="Automations" value={`${data?.automations.length ?? 0}`} />
      </div>
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1.35fr_0.65fr]">
        <Panel title="Running Tasks">
          <div className="max-h-[420px] space-y-2 overflow-auto pr-1">
            {(data?.tasks ?? []).map((task) => (
              <div key={task.id} className="nexa-card grid gap-3 rounded-xl px-3 py-3 text-sm sm:grid-cols-[1fr_auto] sm:items-center">
                <span className="min-w-0 break-words text-slate-100">{task.command}</span>
                <span className="w-fit rounded-full bg-amber-300/15 px-2.5 py-1 text-xs text-amber-100">{task.status}</span>
              </div>
            ))}
            {(data?.tasks ?? []).length === 0 && <Empty label="No active tasks" />}
          </div>
        </Panel>
        <Panel title="Recent Activity">
          <div className="max-h-[420px] space-y-2 overflow-auto pr-1">
            {(data?.notifications ?? []).map((item) => (
              <div key={item.id} className="nexa-card rounded-xl px-3 py-3">
                <div className="break-words text-sm font-medium text-slate-100">{item.title}</div>
                <div className="text-xs text-slate-300">{item.message}</div>
              </div>
            ))}
            {(data?.notifications ?? []).length === 0 && <Empty label="No recent notifications" />}
          </div>
        </Panel>
      </div>
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <Panel title="Automation Status">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Status icon={<RefreshCw size={18} />} label="Active Automations" value={`${data?.automations.length ?? 0}`} />
            <Status icon={<Activity size={18} />} label="Scheduled Jobs" value={`${data?.scheduled_jobs.length ?? 0}`} />
          </div>
        </Panel>
        <Panel title="System Health">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Status icon={<Cpu size={18} />} label="CPU" value={`${data?.system.cpu_percent ?? 0}%`} />
            <Status icon={<HardDrive size={18} />} label="RAM" value={`${data?.system.ram_percent ?? 0}%`} />
            <Status icon={<ShieldCheck size={18} />} label="Battery" value={data?.system.battery_percent == null ? "N/A" : `${data.system.battery_percent}%`} />
          </div>
        </Panel>
      </div>
      <Panel title="Battery Alert">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <Status icon={<ShieldCheck size={18} />} label="Battery Status" value={data?.battery_alert.battery_percent == null ? "Unavailable" : "Available"} />
          <Status icon={<Activity size={18} />} label="Battery %" value={data?.battery_alert.battery_percent == null ? "N/A" : `${data.battery_alert.battery_percent}%`} />
          <Status icon={<Activity size={18} />} label="Charging Status" value={data?.battery_alert.is_charging == null ? "Unknown" : data.battery_alert.is_charging ? "Charging" : "Not charging"} />
          <Status icon={<RefreshCw size={18} />} label="Alert Status" value={data?.battery_alert.alert_active ? "Active" : "Idle"} />
          <Status icon={<Activity size={18} />} label="Last Alert Time" value={data?.battery_alert.last_alert_time ? new Date(data.battery_alert.last_alert_time).toLocaleTimeString() : "Never"} />
        </div>
      </Panel>
    </div>
  );
}

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="glass-panel rounded-2xl p-4">
      <div className="mb-3 flex items-center gap-2 text-sm text-amber-100/70">{icon}{label}</div>
      <div className="text-2xl font-semibold">{value}</div>
    </div>
  );
}

function Status({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return <div className="nexa-card rounded-xl p-4"><div className="mb-2 flex items-center gap-2 text-xs text-amber-100/70">{icon}{label}</div><div className="text-lg font-semibold">{value}</div></div>;
}

function Empty({ label }: { label: string }) {
  return <div className="rounded-xl border border-dashed border-amber-200/15 px-3 py-6 text-center text-sm text-slate-400">{label}</div>;
}
