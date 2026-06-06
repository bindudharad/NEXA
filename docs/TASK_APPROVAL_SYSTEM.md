# Nexa AI Task Approval System

Nexa routes natural-language commands through an approval pipeline before execution.

## Provider Layer

Configuration uses the existing `NEXA_` environment prefix:

- `NEXA_AI_PROVIDER=groq`
- `NEXA_GROQ_API_KEY=<key>`
- `NEXA_GROQ_BASE_URL=https://api.groq.com/openai/v1`
- `NEXA_GROQ_MODEL=llama-3.3-70b-versatile`

If Groq is unavailable or no key is configured, Nexa falls back to the local rule interpreter.

## Workflow

1. User submits a command through `/api/commands`.
2. Nexa creates a `TaskApproval` record.
3. The AI layer corrects grammar and spelling, extracts intent, schedule, trigger, risk, and confidence.
4. Nexa stores interpretation and history records.
5. Nexa creates a notification titled `Nexa Task Approval Required`.
6. The task is not executed until the user approves it through `/api/task-approvals/{id}/approve`.

## Approval Actions

- Approve: creates and executes the task.
- Edit: updates title, date, time, trigger, conditions, or priority, then returns to pending approval.
- Reject: cancels the approval and does not create a task.

Commands below 80% confidence require edit/clarification before approval.

## Persistence

Nexa stores approval data in:

- `task_approvals`
- `approval_history`
- `ai_interpretations`
- `correction_history`

## Security

High-risk commands such as shutdown, restart, delete, process kill, browser automation, and automations are flagged and require explicit approval.
