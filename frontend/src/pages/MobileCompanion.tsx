import React from "react";
import { KeyRound, Link2, QrCode, RefreshCw, ShieldCheck, Smartphone, Trash2, Wifi } from "lucide-react";
import { Panel } from "../components/Panel";
import { api } from "../lib/api";

type AnyRecord = Record<string, any>;

const button = "inline-flex h-9 items-center justify-center gap-2 rounded-lg bg-amber-300 px-3 text-sm font-medium text-black hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-50";
const ghost = "inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-amber-200/15 px-3 text-sm text-amber-100 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50";

export function MobileCompanion() {
  const [dashboard, setDashboard] = React.useState<AnyRecord | null>(null);
  const [pairing, setPairing] = React.useState<AnyRecord | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");

  const load = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setDashboard(await api<AnyRecord>("/mobile/dashboard"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Mobile Companion");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void load();
  }, [load]);

  async function startPairing() {
    setLoading(true);
    setError("");
    try {
      setPairing(await api<AnyRecord>("/mobile/pairing/start", { method: "POST", body: JSON.stringify({ device_name: "Android Device" }) }));
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start pairing");
    } finally {
      setLoading(false);
    }
  }

  async function revokeDevice(id: number) {
    setLoading(true);
    setError("");
    try {
      await api(`/mobile/devices/${id}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to revoke device");
    } finally {
      setLoading(false);
    }
  }

  const devices = dashboard?.devices ?? [];
  const queues = dashboard?.queues ?? {};
  const security = dashboard?.security ?? {};
  const audit = dashboard?.audit_logs ?? [];

  return (
    <div className="space-y-5">
      <section className="flex flex-col gap-3 border-b border-amber-200/10 pb-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm text-amber-200/70"><Smartphone size={16} /> Mobile Companion</div>
          <h1 className="mt-1 text-2xl font-semibold text-amber-50">Android-Ready Mobile Gateway</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-400">Pair trusted devices, inspect mobile permissions, prepare offline sync, and validate secure remote command infrastructure before the Android app is built.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className={ghost} onClick={load} disabled={loading}><RefreshCw size={16} /> Refresh</button>
          <button className={button} onClick={startPairing} disabled={loading}><QrCode size={16} /> Start Pairing</button>
        </div>
      </section>

      {error && <div className="rounded-lg border border-red-400/25 bg-red-500/10 p-3 text-sm text-red-100">{error}</div>}

      {pairing && (
        <section className="rounded-lg border border-amber-300/25 bg-amber-300/10 p-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="flex items-center gap-2 text-sm font-medium text-amber-100"><KeyRound size={16} /> Pairing Code</div>
              <div className="mt-2 font-mono text-3xl font-semibold tracking-[0.18em] text-amber-50">{pairing.pairing_code}</div>
              <div className="mt-1 text-xs text-slate-400">Expires at {formatTime(pairing.expires_at)}</div>
            </div>
            <div className="max-w-xl rounded-lg border border-white/10 bg-black/25 p-3 font-mono text-xs text-slate-300">
              {JSON.stringify(pairing.qr_payload)}
            </div>
          </div>
        </section>
      )}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric icon={<Smartphone size={18} />} label="Trusted Devices" value={String(devices.filter((item: AnyRecord) => item.status === "active").length)} detail={`${devices.length} total`} />
        <Metric icon={<Link2 size={18} />} label="Pending Pairings" value={String(dashboard?.pairing?.pending_codes ?? 0)} detail="10 minute TTL" />
        <Metric icon={<Wifi size={18} />} label="Sync Pending" value={String(queues.sync_pending ?? 0)} detail={`${queues.sync_failed ?? 0} failed`} />
        <Metric icon={<ShieldCheck size={18} />} label="Security" value="Ready" detail={security.high_risk_commands ?? "approval required"} />
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <Panel title="Connected Devices">
          <div className="space-y-2">
            {devices.length === 0 && <div className="rounded-lg border border-white/10 bg-black/20 p-4 text-sm text-slate-400">No mobile devices paired yet.</div>}
            {devices.map((device: AnyRecord) => (
              <div key={device.id} className="flex flex-col gap-3 rounded-lg border border-white/10 bg-black/20 p-3 lg:flex-row lg:items-center lg:justify-between">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-amber-50">{device.device_name}</div>
                  <div className="mt-1 text-xs text-slate-400">{device.device_type} · {device.security_status} · last active {formatTime(device.last_active_at)}</div>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {Object.entries(device.permissions ?? {}).slice(0, 8).map(([permission, allowed]) => (
                      <span key={permission} className={`rounded border px-2 py-1 text-[11px] ${allowed ? "border-emerald-300/20 bg-emerald-400/10 text-emerald-100" : "border-red-300/20 bg-red-400/10 text-red-100"}`}>{permission}</span>
                    ))}
                  </div>
                </div>
                <button className={ghost} onClick={() => revokeDevice(device.id)} disabled={loading || device.status === "revoked"}><Trash2 size={15} /> Revoke</button>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Gateway Security">
          <div className="grid gap-3 sm:grid-cols-2">
            <Status label="Token Storage" value={security.token_storage ?? "hashed"} />
            <Status label="Access Token TTL" value={`${security.access_token_ttl_minutes ?? 30} min`} />
            <Status label="Refresh Token TTL" value={`${security.refresh_token_ttl_days ?? 30} days`} />
            <Status label="Command Policy" value={security.high_risk_commands ?? "approval required"} />
            <Status label="Daily Briefing API" value={dashboard?.daily_briefing_ready ? "Ready" : "Missing"} />
            <Status label="Timeline API" value={dashboard?.timeline_ready ? "Ready" : "Missing"} />
          </div>
        </Panel>
      </section>

      <section className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <Panel title="Architecture">
          <div className="space-y-2">
            {(dashboard?.architecture ?? []).map((step: string, index: number) => (
              <div key={step} className="flex items-center gap-3 rounded-lg border border-white/10 bg-black/20 p-3 text-sm text-slate-200">
                <span className="grid h-7 w-7 place-items-center rounded-lg bg-amber-300/15 text-xs text-amber-100">{index + 1}</span>
                {step}
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Recent Mobile Audit">
          <div className="space-y-2">
            {audit.slice(0, 8).map((item: AnyRecord) => (
              <div key={item.id} className="rounded-lg border border-white/10 bg-black/20 p-3">
                <div className="flex items-center justify-between gap-3 text-sm">
                  <span className="font-medium text-amber-50">{item.event_type}</span>
                  <span className="text-xs text-slate-500">{formatTime(item.created_at)}</span>
                </div>
                <div className="mt-1 text-xs text-slate-400">{item.action} · {item.status}</div>
              </div>
            ))}
            {audit.length === 0 && <div className="text-sm text-slate-400">No mobile audit activity yet.</div>}
          </div>
        </Panel>
      </section>
    </div>
  );
}

function Metric({ icon, label, value, detail }: { icon: React.ReactNode; label: string; value: string; detail: string }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.04] p-4">
      <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-amber-200/60">{icon}{label}</div>
      <div className="mt-3 text-2xl font-semibold text-amber-50">{value}</div>
      <div className="mt-1 text-xs text-slate-400">{detail}</div>
    </div>
  );
}

function Status({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-white/10 bg-black/20 p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-1 truncate text-sm text-slate-100">{value}</div>
    </div>
  );
}

function formatTime(value?: string | null) {
  if (!value) return "never";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}
