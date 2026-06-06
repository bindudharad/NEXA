# API Documentation

Base URL: `http://127.0.0.1:8000/api`

## Commands

`POST /commands`

```json
{ "command": "Open Chrome", "auto_confirm": false }
```

`POST /tasks/{task_id}/confirm` confirms a dangerous pending task.

## Dashboard

`GET /dashboard` returns system status, recent tasks, automations, notifications, and scheduled jobs.

## Automation

`POST /automations`

```json
{
  "name": "Low battery",
  "condition": { "metric": "battery", "operator": "<", "value": 20 },
  "action": { "type": "notify", "message": "Battery below 20%" }
}
```

`POST /automations/evaluate` evaluates active rules against current system metrics.

`POST /events` ingests event-driven triggers.

```json
{ "event_type": "download_completed", "payload": { "file": "report.pdf" } }
```

## Memory

`GET /memory`

`POST /memory`

```json
{ "key": "preferred_editor", "value": "VS Code", "scope": "global" }
```

`GET /memory/conversation-history`

`POST /settings`

```json
{ "key": "theme", "value": "dark" }
```

## Analytics

`GET /coding/report`

`GET /coding/weekly-report`

`POST /coding/snapshot`

## Files

`POST /files/create`

`POST /files/move`

`POST /files/rename`

`POST /files/search`

`POST /files/delete`

Deletion requires `X-Confirm-Danger: true`.

## Browser

`POST /browser/search`

`POST /browser/fill-form`

`POST /browser/download`
