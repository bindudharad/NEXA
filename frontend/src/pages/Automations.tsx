import React from "react";
import { Plus } from "lucide-react";
import { api } from "../lib/api";
import { Panel } from "../components/Panel";

type Automation = { id: number; name: string; condition: { metric: string; operator: string; value: number }; action: { type: string; message: string }; enabled: boolean };

export function Automations() {
  const [items, setItems] = React.useState<Automation[]>([]);
  const [name, setName] = React.useState("Low battery alert");
  const [metric, setMetric] = React.useState("battery");
  const [value, setValue] = React.useState(20);
  const load = () => api<Automation[]>("/automations").then(setItems);
  React.useEffect(() => { load(); }, []);

  async function create() {
    await api<Automation>("/automations", {
      method: "POST",
      body: JSON.stringify({ name, condition: { metric, operator: "<", value }, action: { type: "notify", message: `${metric} below ${value}` } })
    });
    load();
  }

  return (
    <div className="space-y-5">
      <Panel title="Create Automation">
        <div className="grid grid-cols-1 gap-2 lg:grid-cols-[1fr_180px_140px_48px]">
          <input className="nexa-input h-10 rounded-xl px-3" value={name} onChange={(event) => setName(event.target.value)} />
          <select className="nexa-input h-10 rounded-xl px-3" value={metric} onChange={(event) => setMetric(event.target.value)}>
            <option value="battery">Battery</option>
            <option value="cpu">CPU</option>
            <option value="ram">RAM</option>
          </select>
          <input className="nexa-input h-10 rounded-xl px-3" type="number" value={value} onChange={(event) => setValue(Number(event.target.value))} />
          <button className="grid h-10 place-items-center rounded-xl bg-accent text-obsidian" onClick={create} title="Create automation"><Plus size={18} /></button>
        </div>
      </Panel>
      <Panel title="Active Automations">
        <div className="space-y-2">
          {items.map((item) => <div key={item.id} className="nexa-card rounded-xl p-3 text-sm">{item.name}: IF {item.condition.metric} {item.condition.operator} {item.condition.value} THEN {item.action.type}</div>)}
        </div>
      </Panel>
    </div>
  );
}
