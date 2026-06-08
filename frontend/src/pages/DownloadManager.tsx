import React from "react";
import { Archive, BarChart3, Download, FileSearch, FolderInput, HardDrive, ListChecks, Search, ShieldAlert, Trash2 } from "lucide-react";
import { api } from "../lib/api";

type AnyRecord = Record<string, any>;

const panel = "rounded-lg border border-amber-200/10 bg-white/[0.04] p-4";
const button = "inline-flex h-9 items-center gap-2 rounded-lg bg-amber-300 px-3 text-sm font-medium text-black hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-50";
const ghost = "inline-flex h-9 items-center gap-2 rounded-lg border border-amber-200/15 px-3 text-sm text-amber-100 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50";
const input = "h-10 w-full rounded-lg border border-amber-200/10 bg-black/25 px-3 text-sm text-amber-50 outline-none placeholder:text-slate-500 focus:border-amber-300/50";

export function DownloadManager() {
  const [data, setData] = React.useState<AnyRecord | null>(null);
  const [folder, setFolder] = React.useState("");
  const [query, setQuery] = React.useState("find PDFs");
  const [searchResult, setSearchResult] = React.useState<AnyRecord | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");

  const load = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const suffix = folder ? `?folder=${encodeURIComponent(folder)}` : "";
      setData(await api<AnyRecord>(`/evolution/downloads/dashboard${suffix}`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Download Manager");
    } finally {
      setLoading(false);
    }
  }, [folder]);

  React.useEffect(() => {
    void load();
  }, [load]);

  async function run(action: () => Promise<unknown>) {
    setLoading(true);
    setError("");
    try {
      await action();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Download Manager action failed");
    } finally {
      setLoading(false);
    }
  }

  async function search() {
    await run(async () => setSearchResult(await api<AnyRecord>("/evolution/downloads/search", { method: "POST", body: JSON.stringify({ query, limit: 50 }) })));
  }

  const stats = data?.statistics ?? {};
  const recent = data?.recent ?? [];
  const duplicates = data?.duplicates ?? [];
  const cleanup = data?.cleanup_suggestions ?? [];
  const analytics = data?.analytics?.by_category ?? [];
  const largeFiles = data?.large_files ?? [];

  return (
    <div className="space-y-5">
      <section className="flex flex-col gap-3 border-b border-amber-200/10 pb-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm text-amber-200/70"><Download size={16} /> Smart Download Manager</div>
          <h1 className="mt-1 text-2xl font-semibold text-amber-50">Downloads Organizer</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-400">Categorize, organize, search, and clean downloads with local filesystem events and offline-safe history.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className={ghost} onClick={load} disabled={loading}><Search size={16} /> Refresh</button>
          <button className={button} onClick={() => run(() => api("/evolution/downloads/scan", { method: "POST", body: JSON.stringify({ folder: folder || null, large_file_mb: 100 }) }))} disabled={loading}><FileSearch size={16} /> Scan</button>
          <button className={ghost} onClick={() => run(() => api("/evolution/downloads/organize", { method: "POST", body: JSON.stringify({ folder: folder || null, dry_run: true }) }))} disabled={loading}><FolderInput size={16} /> Preview Organize</button>
        </div>
      </section>

      {error && <div className="rounded-lg border border-red-400/25 bg-red-500/10 p-3 text-sm text-red-100">{error}</div>}

      <section className="grid gap-3 lg:grid-cols-[1fr_auto]">
        <input className={input} value={folder} onChange={(event) => setFolder(event.target.value)} placeholder={data?.root ?? "Downloads folder path"} />
        <button className={ghost} onClick={() => run(() => api("/evolution/downloads/rules", { method: "POST", body: JSON.stringify({ name: "Assignment PDFs", pattern: "assignment", match_type: "name_contains", category: "PDF", priority: 20 }) }))} disabled={loading}>Add Assignment Rule</button>
      </section>

      <section className="grid gap-4 xl:grid-cols-5">
        <Metric icon={<HardDrive size={18} />} label="Indexed" value={stats.files_indexed ?? 0} />
        <Metric icon={<Archive size={18} />} label="Storage" value={stats.storage_indexed_label ?? "0 B"} />
        <Metric icon={<ShieldAlert size={18} />} label="Duplicates" value={stats.duplicates ?? duplicates.length} />
        <Metric icon={<Trash2 size={18} />} label="Cleanup" value={stats.cleanup_suggestions ?? cleanup.length} />
        <Metric icon={<BarChart3 size={18} />} label="Health" value={`${Math.round(stats.health_score ?? 100)}%`} />
      </section>

      <section className="grid gap-4 xl:grid-cols-[1fr_0.9fr]">
        <Panel title="Search Downloads">
          <div className="grid gap-2 md:grid-cols-[1fr_auto]">
            <input className={input} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Find PDFs larger than 10 MB" />
            <button className={button} onClick={search} disabled={loading}><Search size={16} /> Search</button>
          </div>
          {searchResult && <div className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm text-slate-300">{searchResult.summary}</div>}
          {(searchResult?.results ?? []).slice(0, 8).map((item: AnyRecord) => <FileRow key={`${item.id}-${item.file_path}`} item={item} />)}
        </Panel>

        <Panel title="Category Analytics">
          {analytics.length === 0 ? <Empty text="Scan downloads to generate analytics." /> : analytics.map((item: AnyRecord) => (
            <div key={item.category} className="rounded-lg border border-white/10 bg-black/20 p-3">
              <div className="flex items-center justify-between gap-3 text-sm">
                <span className="font-medium text-amber-100">{item.category}</span>
                <span className="text-slate-400">{item.file_count} files</span>
              </div>
              <div className="mt-1 text-xs text-slate-500">{formatBytes(item.total_size_bytes)} / {item.duplicate_count} duplicates</div>
            </div>
          ))}
        </Panel>
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <Panel title="Recent Downloads">
          {recent.length === 0 ? <Empty text="No downloads indexed yet." /> : recent.slice(0, 10).map((item: AnyRecord) => <FileRow key={item.id} item={item} />)}
        </Panel>
        <Panel title="Large Files">
          {largeFiles.length === 0 ? <Empty text="No large files detected." /> : largeFiles.slice(0, 10).map((item: AnyRecord) => <FileRow key={item.id ?? item.file_path} item={item} />)}
        </Panel>
        <Panel title="Cleanup Suggestions">
          {cleanup.length === 0 ? <Empty text="No cleanup suggestions." /> : cleanup.slice(0, 10).map((item: AnyRecord) => (
            <div key={item.id} className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm">
              <div className="font-medium text-amber-100">{item.title}</div>
              <div className="mt-1 text-slate-400">{item.message}</div>
              <div className="mt-2 text-xs text-slate-500">{item.severity} / {item.size_label}</div>
            </div>
          ))}
        </Panel>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1fr_0.8fr]">
        <Panel title="Duplicates">
          {duplicates.length === 0 ? <Empty text="No duplicate downloads detected." /> : duplicates.slice(0, 10).map((item: AnyRecord) => <FileRow key={item.id} item={item} />)}
        </Panel>
        <Panel title="Rules">
          {(data?.rules ?? []).length === 0 ? <Empty text="No custom rules. Defaults are active." /> : (data?.rules ?? []).map((item: AnyRecord) => (
            <div key={item.id} className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm">
              <div className="flex items-center justify-between gap-3">
                <span className="font-medium text-amber-100">{item.name}</span>
                <span className="text-slate-400">{item.category}</span>
              </div>
              <div className="mt-1 text-xs text-slate-500">{item.match_type}: {item.pattern}</div>
            </div>
          ))}
        </Panel>
      </section>
    </div>
  );
}

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: React.ReactNode }) {
  return <div className={panel}><div className="mb-2 flex items-center gap-2 text-sm text-slate-400">{icon}{label}</div><div className="text-2xl font-semibold text-amber-50">{value}</div></div>;
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return <div className={panel}><h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-amber-50"><ListChecks size={17} />{title}</h2><div className="space-y-2">{children}</div></div>;
}

function FileRow({ item }: { item: AnyRecord }) {
  return (
    <div className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm">
      <div className="flex items-center justify-between gap-3">
        <span className="min-w-0 truncate font-medium text-amber-100">{item.file_name ?? item.title}</span>
        <span className="shrink-0 text-slate-400">{item.size_label ?? formatBytes(item.size_bytes ?? 0)}</span>
      </div>
      <div className="mt-1 flex flex-wrap gap-2 text-xs text-slate-500">
        <span>{item.category ?? item.duplicate_type ?? item.suggestion_type}</span>
        {item.duplicate_of && <span>Duplicate of {String(item.duplicate_of).split(/[\\/]/).pop()}</span>}
        {item.status && <span>{item.status}</span>}
      </div>
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm text-slate-500">{text}</div>;
}

function formatBytes(value: number) {
  if (!Number.isFinite(value) || value <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = value;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${index === 0 ? Math.round(size) : size.toFixed(1)} ${units[index]}`;
}
