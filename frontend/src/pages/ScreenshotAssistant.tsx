import React from "react";
import { Clipboard, Eye, FileText, Image, Lightbulb, Lock, Mic, RefreshCw, Search, Wand2 } from "lucide-react";
import { api } from "../lib/api";

type AnyRecord = Record<string, any>;

const panel = "rounded-lg border border-amber-200/10 bg-white/[0.04] p-4";
const button = "inline-flex h-9 items-center gap-2 rounded-lg bg-amber-300 px-3 text-sm font-medium text-black hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-50";
const ghost = "inline-flex h-9 items-center gap-2 rounded-lg border border-amber-200/15 px-3 text-sm text-amber-100 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50";
const input = "h-10 w-full rounded-lg border border-amber-200/10 bg-black/25 px-3 text-sm text-amber-50 outline-none placeholder:text-slate-500 focus:border-amber-300/50";

export function ScreenshotAssistant() {
  const [data, setData] = React.useState<AnyRecord | null>(null);
  const [query, setQuery] = React.useState("find coding errors");
  const [searchResult, setSearchResult] = React.useState<AnyRecord | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");

  const load = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await api<AnyRecord>("/evolution/screenshots/dashboard"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Screenshot Assistant");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void load();
  }, [load]);

  async function search() {
    setLoading(true);
    setError("");
    try {
      setSearchResult(await api<AnyRecord>("/evolution/screenshots/search", { method: "POST", body: JSON.stringify({ query, limit: 25 }) }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }

  async function action(screenshotId: number, actionType: string) {
    setLoading(true);
    try {
      await api(`/evolution/screenshots/${screenshotId}/actions`, { method: "POST", body: JSON.stringify({ action_type: actionType, payload: { source: "dashboard" } }) });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setLoading(false);
    }
  }

  const stats = data?.statistics ?? {};
  const recent = data?.recent ?? [];
  const latest = recent[0];

  return (
    <div className="space-y-5">
      <section className="flex flex-col gap-3 border-b border-amber-200/10 pb-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm text-amber-200/70"><Image size={16} /> AI Screenshot Assistant</div>
          <h1 className="mt-1 text-2xl font-semibold text-amber-50">Screenshot Intelligence</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-400">Press Ctrl + Shift + A in Electron to capture, OCR, analyze, summarize, and save screenshots locally.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className={ghost} onClick={load} disabled={loading}><RefreshCw size={16} /> Refresh</button>
          <button className={button} onClick={() => api("/voice/command", { method: "POST", body: JSON.stringify({ command: "capture screen", source: "dashboard" }) })} disabled={loading}><Wand2 size={16} /> Capture Hint</button>
        </div>
      </section>

      {error && <div className="rounded-lg border border-red-400/25 bg-red-500/10 p-3 text-sm text-red-100">{error}</div>}

      <section className="grid gap-4 xl:grid-cols-5">
        <Metric label="Screenshots" value={stats.screenshots ?? 0} icon={<Image size={18} />} />
        <Metric label="OCR Results" value={stats.ocr_results ?? 0} icon={<Eye size={18} />} />
        <Metric label="Errors" value={stats.errors_analyzed ?? 0} icon={<Wand2 size={18} />} />
        <Metric label="Documents" value={stats.documents_summarized ?? 0} icon={<FileText size={18} />} />
        <Metric label="Local Privacy" value={data?.privacy?.local_only ? "On" : "Off"} icon={<Lock size={18} />} />
      </section>

      <section className="grid gap-4 xl:grid-cols-[1fr_0.9fr]">
        <Panel title="Search Screenshot History">
          <div className="grid gap-2 md:grid-cols-[1fr_auto]">
            <input className={input} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Show screenshots from yesterday" />
            <button className={button} onClick={search} disabled={loading}><Search size={16} /> Search</button>
          </div>
          {searchResult && <div className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm text-slate-300">{searchResult.summary}</div>}
          {(searchResult?.results ?? []).slice(0, 5).map((item: AnyRecord) => <ScreenshotCard key={item.id} item={item} onAction={action} />)}
        </Panel>

        <Panel title="Smart Actions">
          {(data?.smart_actions ?? []).map((item: string) => (
            <div key={item} className="flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-black/20 p-3 text-sm">
              <span className="text-amber-100">{item}</span>
              <span className="text-xs text-slate-500">local</span>
            </div>
          ))}
          <div className="rounded-lg border border-emerald-300/20 bg-emerald-400/10 p-3 text-sm text-emerald-100">
            Cloud analysis is disabled by default and requires explicit approval.
          </div>
        </Panel>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1fr_0.9fr]">
        <Panel title="Latest Analysis">
          {latest ? <ScreenshotCard item={latest} onAction={action} detailed /> : <Empty text="No screenshots captured yet." />}
        </Panel>
        <Panel title="Voice Commands">
          {["Capture screen", "Explain this error", "Read screenshot", "Summarize document", "Extract text", "Save notes", "Screenshot history"].map((item) => (
            <div key={item} className="flex items-center gap-2 rounded-lg border border-white/10 bg-black/20 p-3 text-sm text-slate-300"><Mic size={15} />{item}</div>
          ))}
        </Panel>
      </section>

      <Panel title="History">
        <div className="grid gap-3 lg:grid-cols-2">
          {recent.length === 0 ? <Empty text="No screenshot history yet." /> : recent.map((item: AnyRecord) => <ScreenshotCard key={item.id} item={item} onAction={action} />)}
        </div>
      </Panel>
    </div>
  );
}

function ScreenshotCard({ item, onAction, detailed = false }: { item: AnyRecord; onAction: (id: number, action: string) => void; detailed?: boolean }) {
  const summary = item.document_summary?.summary ?? item.analysis;
  const error = item.error_analysis;
  return (
    <div className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate font-medium text-amber-100">{String(item.file_path).split(/[\\/]/).pop()}</div>
          <div className="mt-1 flex flex-wrap gap-2 text-xs text-slate-500">{(item.tags ?? []).map((tag: string) => <span key={tag}>{tag}</span>)}</div>
        </div>
        <span className="text-xs text-slate-500">{new Date(item.created_at).toLocaleString()}</span>
      </div>
      <p className="mt-2 text-slate-300">{summary || "No analysis available."}</p>
      {error && <div className="mt-2 rounded-lg border border-red-300/20 bg-red-500/10 p-2 text-red-100">{error.error_type}: {error.probable_cause}</div>}
      {detailed && item.document_summary?.key_points?.length > 0 && (
        <div className="mt-2 space-y-1 text-xs text-slate-400">{item.document_summary.key_points.slice(0, 5).map((point: string) => <div key={point}>- {point}</div>)}</div>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        <button className={ghost} onClick={() => navigator.clipboard?.writeText(item.extracted_text ?? "")}><Clipboard size={14} /> Copy Text</button>
        <button className={ghost} onClick={() => onAction(item.id, "save_notes")}><Lightbulb size={14} /> Save Notes</button>
        <button className={ghost} onClick={() => onAction(item.id, "save_to_timeline")}>Save Timeline</button>
      </div>
    </div>
  );
}

function Metric({ label, value, icon }: { label: string; value: React.ReactNode; icon: React.ReactNode }) {
  return <div className={panel}><div className="mb-2 flex items-center gap-2 text-sm text-slate-400">{icon}{label}</div><div className="text-2xl font-semibold text-amber-50">{value}</div></div>;
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return <div className={panel}><h2 className="mb-3 text-lg font-semibold text-amber-50">{title}</h2><div className="space-y-2">{children}</div></div>;
}

function Empty({ text }: { text: string }) {
  return <div className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm text-slate-500">{text}</div>;
}
