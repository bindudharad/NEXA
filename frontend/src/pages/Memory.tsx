import React from "react";
import { api } from "../lib/api";
import { Panel } from "../components/Panel";

type MemoryRow = { id: number; key: string; value: string; scope: string };

export function Memory() {
  const [rows, setRows] = React.useState<MemoryRow[]>([]);
  const [key, setKey] = React.useState("");
  const [value, setValue] = React.useState("");
  const load = () => api<MemoryRow[]>("/memory").then(setRows);
  React.useEffect(() => { load(); }, []);
  async function save() {
    await api("/memory", { method: "POST", body: JSON.stringify({ key, value }) });
    setKey("");
    setValue("");
    load();
  }
  return (
    <div className="space-y-5">
      <Panel title="Stored Memories">
        <div className="mb-4 grid grid-cols-1 gap-2 md:grid-cols-[220px_1fr_90px]">
          <input className="nexa-input h-10 rounded-xl px-3 placeholder:text-slate-500" value={key} onChange={(event) => setKey(event.target.value)} placeholder="Key" />
          <input className="nexa-input h-10 rounded-xl px-3 placeholder:text-slate-500" value={value} onChange={(event) => setValue(event.target.value)} placeholder="Value" />
          <button className="h-10 rounded-xl bg-accent text-obsidian" onClick={save}>Save</button>
        </div>
        <div className="space-y-2">
          {rows.map((row) => <div className="nexa-card rounded-xl p-3 text-sm" key={row.id}><strong>{row.key}</strong><div className="break-words text-slate-300">{row.value}</div></div>)}
        </div>
      </Panel>
    </div>
  );
}
