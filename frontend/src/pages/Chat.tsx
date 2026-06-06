import React from "react";
import { Check, Pencil, Send, ShieldAlert, X } from "lucide-react";
import { approveTaskApproval, editTaskApproval, rejectTaskApproval, runCommand, type TaskApproval } from "../lib/api";
import { Panel } from "../components/Panel";

type EditState = {
  task_title: string;
  date: string;
  time: string;
  trigger: string;
  priority: string;
};

export function Chat() {
  const [command, setCommand] = React.useState("");
  const [approvals, setApprovals] = React.useState<TaskApproval[]>([]);
  const [editingId, setEditingId] = React.useState<number | null>(null);
  const [editState, setEditState] = React.useState<EditState>({ task_title: "", date: "", time: "", trigger: "", priority: "normal" });
  const [error, setError] = React.useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!command.trim()) return;
    setError("");
    try {
      const approval = await runCommand(command);
      setApprovals((current) => [approval, ...current]);
      setCommand("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Command failed");
    }
  }

  async function approve(approvalId: number) {
    try {
      const approval = await approveTaskApproval(approvalId);
      updateApproval(approval);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approval failed");
    }
  }

  async function reject(approvalId: number) {
    const approval = await rejectTaskApproval(approvalId, "Rejected by user");
    updateApproval(approval);
  }

  async function saveEdit(approvalId: number) {
    const approval = await editTaskApproval(approvalId, editState);
    updateApproval(approval);
    setEditingId(null);
  }

  function startEdit(approval: TaskApproval) {
    setEditingId(approval.id);
    setEditState({
      task_title: approval.corrected_text,
      date: String(approval.structured_task.date ?? ""),
      time: String(approval.structured_task.time ?? ""),
      trigger: String(approval.structured_task.trigger ?? ""),
      priority: String(approval.structured_task.priority ?? "normal")
    });
  }

  function updateApproval(approval: TaskApproval) {
    setApprovals((current) => current.map((item) => (item.id === approval.id ? approval : item)));
  }

  return (
    <div>
      <Panel title="Nexa Task Approval Console">
        <form className="mb-4 grid gap-2 sm:grid-cols-[1fr_44px]" onSubmit={submit}>
          <input className="nexa-input h-11 rounded-xl px-3 placeholder:text-slate-500" value={command} onChange={(event) => setCommand(event.target.value)} placeholder="Type command..." />
          <button className="grid h-11 place-items-center rounded-xl bg-accent text-obsidian" title="Send command">
            <Send size={18} />
          </button>
        </form>
        {error && <div className="mb-3 rounded-xl border border-red-400/30 bg-red-500/10 p-3 text-sm text-red-100">{error}</div>}
        <div className="space-y-3">
          {approvals.map((approval) => (
            <div key={approval.id} className="nexa-card rounded-2xl p-4">
              <div className="grid gap-4 xl:grid-cols-[1fr_auto]">
                <div className="min-w-0 space-y-3">
                  <div>
                    <div className="text-xs uppercase tracking-[0.2em] text-amber-200/60">Your Request</div>
                    <div className="break-words text-slate-100">{approval.original_text}</div>
                  </div>
                  <div>
                    <div className="text-xs uppercase tracking-[0.2em] text-amber-200/60">AI Interpretation</div>
                    <div className="break-words text-lg font-semibold text-amber-100">{approval.corrected_text}</div>
                  </div>
                  <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                    <Preview label="Type" value={approval.task_type} />
                    <Preview label="Intent" value={approval.intent} />
                    <Preview label="Confidence" value={`${approval.confidence}%`} warning={approval.confidence < 80} />
                    <Preview label="Risk" value={approval.high_risk ? "High" : "Normal"} warning={approval.high_risk} />
                  </div>
                  <div className="grid gap-2 md:grid-cols-2">
                    <Preview label="Schedule" value={[approval.structured_task.date, approval.structured_task.time].filter(Boolean).join(" at ") || "Not scheduled"} />
                    <Preview label="Trigger" value={String(approval.structured_task.trigger ?? "Manual approval")} />
                    <Preview label="Action" value={String(approval.structured_task.action ?? "Create task")} />
                    <Preview label="Impact" value={String(approval.structured_task.execution_impact ?? "No execution before approval")} />
                  </div>
                  {approval.clarification_required && (
                    <div className="rounded-xl border border-amber-300/30 bg-amber-300/10 p-3 text-sm text-amber-100">
                      Confidence is below 80%. Edit the task before approval.
                    </div>
                  )}
                  {editingId === approval.id && (
                    <div className="grid gap-2 rounded-xl border border-amber-200/15 bg-black/20 p-3 md:grid-cols-2">
                      <input className="nexa-input h-10 rounded-xl px-3" value={editState.task_title} onChange={(event) => setEditState({ ...editState, task_title: event.target.value })} placeholder="Task title" />
                      <input className="nexa-input h-10 rounded-xl px-3" value={editState.date} onChange={(event) => setEditState({ ...editState, date: event.target.value })} placeholder="Date" />
                      <input className="nexa-input h-10 rounded-xl px-3" value={editState.time} onChange={(event) => setEditState({ ...editState, time: event.target.value })} placeholder="Time" />
                      <input className="nexa-input h-10 rounded-xl px-3" value={editState.trigger} onChange={(event) => setEditState({ ...editState, trigger: event.target.value })} placeholder="Trigger or condition" />
                      <button className="rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-obsidian" onClick={() => saveEdit(approval.id)} type="button">Save and Review Again</button>
                    </div>
                  )}
                </div>
                <div className="flex flex-wrap gap-2 xl:w-40 xl:flex-col">
                  <button className="flex h-10 items-center justify-center gap-2 rounded-xl bg-accent px-3 text-sm font-semibold text-obsidian disabled:opacity-50" disabled={approval.status === "approved" || approval.status === "rejected" || approval.clarification_required} onClick={() => approve(approval.id)}>
                    <Check size={16} />
                    Approve
                  </button>
                  <button className="flex h-10 items-center justify-center gap-2 rounded-xl border border-amber-200/20 bg-white/5 px-3 text-sm text-amber-100" onClick={() => startEdit(approval)}>
                    <Pencil size={16} />
                    Edit
                  </button>
                  <button className="flex h-10 items-center justify-center gap-2 rounded-xl border border-red-300/20 bg-red-500/10 px-3 text-sm text-red-100 disabled:opacity-50" disabled={approval.status === "approved" || approval.status === "rejected"} onClick={() => reject(approval.id)}>
                    <X size={16} />
                    Reject
                  </button>
                  <span className="flex min-h-10 items-center justify-center gap-2 rounded-xl bg-amber-300/10 px-3 text-sm text-amber-100">
                    <ShieldAlert size={16} />
                    {approval.status}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function Preview({ label, value, warning = false }: { label: string; value: string; warning?: boolean }) {
  return (
    <div className={`rounded-xl border p-3 ${warning ? "border-amber-300/40 bg-amber-300/10" : "border-white/10 bg-white/[0.03]"}`}>
      <div className="text-xs uppercase tracking-[0.18em] text-amber-200/55">{label}</div>
      <div className="mt-1 break-words text-sm text-slate-100">{value}</div>
    </div>
  );
}
