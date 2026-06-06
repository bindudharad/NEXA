import React from "react";
import { Check, Send, ShieldAlert } from "lucide-react";
import { confirmTask, runCommand, type Task } from "../lib/api";
import { Panel } from "../components/Panel";

export function Chat() {
  const [command, setCommand] = React.useState("");
  const [tasks, setTasks] = React.useState<Task[]>([]);
  const [error, setError] = React.useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!command.trim()) return;
    setError("");
    try {
      const task = await runCommand(command);
      setTasks((current) => [task, ...current]);
      setCommand("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Command failed");
    }
  }

  async function approve(taskId: number) {
    const task = await confirmTask(taskId);
    setTasks((current) => current.map((item) => (item.id === task.id ? task : item)));
  }

  return (
    <div>
      <Panel title="Nexa Command Console">
        <form className="mb-4 grid gap-2 sm:grid-cols-[1fr_44px]" onSubmit={submit}>
          <input className="nexa-input h-11 rounded-xl px-3 placeholder:text-slate-500" value={command} onChange={(event) => setCommand(event.target.value)} placeholder="Type command..." />
          <button className="grid h-11 place-items-center rounded-xl bg-accent text-obsidian" title="Send command">
            <Send size={18} />
          </button>
        </form>
        {error && <div className="mb-3 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}
        <div className="space-y-2">
          {tasks.map((task) => (
            <div key={task.id} className="nexa-card rounded-xl p-3">
              <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-center">
                <div className="min-w-0">
                  <div className="text-xs text-amber-200/70">User</div>
                  <div className="break-words font-medium">{task.command}</div>
                  <div className="mt-2 text-xs text-amber-200/70">Nexa</div>
                  <div className="text-sm text-slate-300">{task.agent} / {task.intent}</div>
                </div>
                {task.status === "pending_confirmation" ? (
                  <button className="flex h-9 w-fit items-center gap-2 rounded-lg bg-amber-100 px-3 text-sm text-amber-900" onClick={() => approve(task.id)}>
                    <ShieldAlert size={16} />
                    Confirm
                  </button>
                ) : (
                  <span className="flex w-fit items-center gap-2 rounded-lg bg-amber-300/15 px-3 py-2 text-sm text-amber-100"><Check size={16} />{task.status}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
