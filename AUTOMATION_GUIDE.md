# Automation Guide

Automations use a condition/action structure.

## Conditions

Supported metrics:

- `battery`
- `cpu`
- `ram`
- `vscode_running`
- `cursor_running`

Supported event triggers:

- `download_completed`
- `vscode_closed`
- `codex_queue_finished`

Supported operators:

- `<`
- `>`
- `<=`
- `>=`
- `==`

## Actions

Supported action type:

- `notify`
- `schedule_delay`
- `move_by_extension`
- `backup_folder`

Example:

```json
{
  "name": "High CPU",
  "condition": { "metric": "cpu", "operator": ">", "value": 90 },
  "action": { "type": "notify", "message": "CPU is above 90%" }
}
```

The engine is designed so filesystem, scheduler, and system actions can be registered behind the same confirmation policy.
