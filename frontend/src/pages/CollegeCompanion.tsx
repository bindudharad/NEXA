import React from "react";
import { Bell, BookOpenCheck, CalendarDays, ClipboardList, GraduationCap, RefreshCw, ShieldCheck, WalletCards } from "lucide-react";
import { api } from "../lib/api";

type AnyRecord = Record<string, any>;

const panel = "rounded-lg border border-amber-200/10 bg-white/[0.04] p-4";
const button = "inline-flex h-9 items-center gap-2 rounded-lg bg-amber-300 px-3 text-sm font-medium text-black hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-50";
const ghost = "inline-flex h-9 items-center gap-2 rounded-lg border border-amber-200/15 px-3 text-sm text-amber-100 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50";

export function CollegeCompanion() {
  const [data, setData] = React.useState<AnyRecord | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");

  const load = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await api<AnyRecord>("/evolution/college/dashboard"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load College Companion");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void load();
  }, [load]);

  async function checkUpdates() {
    setLoading(true);
    setError("");
    try {
      const result = await api<AnyRecord>("/evolution/college/check", { method: "POST", body: JSON.stringify({ source: "college" }) });
      setData(result.dashboard);
    } catch (err) {
      setError(err instanceof Error ? err.message : "College update check failed");
    } finally {
      setLoading(false);
    }
  }

  const stats = data?.statistics ?? {};
  const attendance = data?.attendance ?? [];
  const marks = data?.marks ?? [];
  const results = data?.results ?? [];
  const assignments = data?.assignments ?? [];
  const fees = data?.fees ?? [];
  const timetables = data?.timetables ?? [];
  const announcements = data?.announcements ?? [];
  const kcet = data?.kcet ?? [];
  const recommendations = data?.recommendations ?? [];

  return (
    <div className="space-y-5">
      <section className="flex flex-col gap-3 border-b border-amber-200/10 pb-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm text-amber-200/70"><GraduationCap size={16} /> College Companion</div>
          <h1 className="mt-1 text-2xl font-semibold text-amber-50">College Dashboard</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-400">Attendance, marks, results, fees, timetable, assignments, announcements, KCET, and Website Vault automation in one place.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className={ghost} onClick={load} disabled={loading}><RefreshCw size={16} /> Refresh</button>
          <button className={button} onClick={checkUpdates} disabled={loading}><ShieldCheck size={16} /> Check Updates</button>
        </div>
      </section>

      {error && <div className="rounded-lg border border-red-400/25 bg-red-500/10 p-3 text-sm text-red-100">{error}</div>}

      <section className={panel}>
        <div className="text-sm text-slate-400">Daily College Summary</div>
        <div className="mt-2 text-lg text-amber-50">{data?.summary ?? "No college data cached yet. Connect Website Vault profiles or create a college profile."}</div>
      </section>

      <section className="grid gap-4 xl:grid-cols-4">
        <Metric icon={<BookOpenCheck size={18} />} label="Attendance" value={attendance[0]?.percentage == null ? "--" : `${attendance[0].percentage}%`} />
        <Metric icon={<ClipboardList size={18} />} label="Assignments" value={stats.pending_assignments ?? 0} />
        <Metric icon={<WalletCards size={18} />} label="Pending Fees" value={stats.pending_fees ?? 0} />
        <Metric icon={<Bell size={18} />} label="Announcements" value={stats.announcements ?? 0} />
      </section>

      <section className="grid gap-4 xl:grid-cols-[1fr_0.9fr]">
        <Panel title="AI Recommendations">
          {recommendations.length === 0 ? <Empty text="No urgent college recommendations." /> : recommendations.map((item: AnyRecord) => (
            <div key={`${item.type}-${item.title}`} className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm">
              <div className="flex items-center justify-between gap-3">
                <span className="font-medium text-amber-100">{item.title}</span>
                <span className="text-xs text-slate-500">{item.priority}</span>
              </div>
              <p className="mt-1 text-slate-400">{item.message}</p>
            </div>
          ))}
        </Panel>
        <Panel title="Website Vault Security">
          <Row label="Profiles" value={data?.profiles?.length ?? 0} />
          <Row label="Credentials" value={data?.security?.credentials_encrypted ? "Encrypted" : "Not configured"} />
          <Row label="Sessions" value={data?.security?.sessions_encrypted ? "Encrypted" : "Not configured"} />
          <Row label="Offline Dashboard" value={data?.offline_ready ? "Ready" : "Unavailable"} />
        </Panel>
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <Summary title="Attendance" items={attendance.map((item: AnyRecord) => `${item.subject}: ${item.percentage}% (${item.status})`)} />
        <Summary title="Internal Marks" items={marks.map((item: AnyRecord) => `${item.subject} ${item.component}: ${item.marks_obtained}/${item.max_marks}`)} />
        <Summary title="Results & KCET" items={[...results.map((item: AnyRecord) => `${item.exam_name}: ${item.summary || item.score || item.status}`), ...kcet.map((item: AnyRecord) => `${item.title}: ${item.rank || item.status}`)]} />
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <Summary title="Assignments" items={assignments.map((item: AnyRecord) => `${item.title}: ${item.status}${item.due_at ? ` due ${new Date(item.due_at).toLocaleDateString()}` : ""}`)} />
        <Summary title="Fees" items={fees.map((item: AnyRecord) => `${item.fee_type}: ${item.status} ${item.amount ? `${item.currency} ${item.amount}` : ""}`)} />
        <Summary title="Timetable" items={timetables.map((item: AnyRecord) => `${item.title}: ${item.starts_at ? new Date(item.starts_at).toLocaleString() : "unscheduled"}`)} />
      </section>

      <Panel title="Announcements">
        {announcements.length === 0 ? <Empty text="No announcements cached." /> : announcements.slice(0, 8).map((item: AnyRecord) => (
          <div key={item.id} className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm">
            <div className="font-medium text-amber-100">{item.title}</div>
            <p className="mt-1 text-slate-400">{item.message || item.announcement_type}</p>
          </div>
        ))}
      </Panel>
    </div>
  );
}

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: React.ReactNode }) {
  return <div className={panel}><div className="mb-2 flex items-center gap-2 text-sm text-slate-400">{icon}{label}</div><div className="text-2xl font-semibold text-amber-50">{value}</div></div>;
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return <div className={panel}><h2 className="mb-3 text-lg font-semibold text-amber-50">{title}</h2><div className="space-y-2">{children}</div></div>;
}

function Summary({ title, items }: { title: string; items: string[] }) {
  return <Panel title={title}>{items.length === 0 ? <Empty text="No cached data." /> : items.slice(0, 8).map((item) => <div key={item} className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm text-slate-300">{item}</div>)}</Panel>;
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return <div className="flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-black/20 p-3 text-sm"><span className="text-slate-400">{label}</span><span className="text-amber-100">{value}</span></div>;
}

function Empty({ text }: { text: string }) {
  return <div className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm text-slate-500">{text}</div>;
}
