# Nexa Orbital Assistant

Nexa Orbital Assistant is the Electron desktop companion surface for Nexa. It is a transparent, always-on-top orbital launcher rather than a dashboard, sidebar, or browser-style popup.

## Behavior

- Nexa starts as a compact floating logo.
- The logo can be dragged and its last dock position is persisted in Electron user data.
- Clicking the logo expands a 360-degree orbital menu around the center hub.
- The center hub contains the Nexa logo and a close control that collapses back to the docked logo.
- The overlay is transparent, frameless, always on top, and clamped to the active display work area.

## Permanent Buttons

- Chat: natural language commands, task creation, quick automation creation, voice input readiness, and voice output feedback.
- Tasks: active, queued, running, completed, failed, and scheduled task visibility with pause, resume, cancel, and retry actions.

## Dynamic Buttons

Dynamic buttons appear and disappear from live system context:

- VS Code, Cursor, or Git activity: Coding module.
- Chrome running: Browser module.
- Spotify running: Media module.
- Active downloads: Files module.
- Low battery or active battery alert: Battery module.
- High system load: System alert module.
- Enabled automations: Automation module.

## Modules

- Battery: battery percentage, health, charging status, estimated time, power mode, temperature, battery saver, and alert settings.
- System Health: CPU, RAM, GPU placeholder, disk, network, temperature, process count, and health score.
- Coding Analytics: daily and weekly activity, VS Code/Cursor time, Git activity, projects, file changes, commits, heatmap readiness, and productivity state.
- Automation: active automations, triggers, schedules, conditions, and enable/disable controls.
- Files: Downloads, Documents, Desktop, and Projects quick open actions.
- Chat: command execution, suggestions, voice input readiness, voice output, and automation creation.

## Electron Notes

- Main process: `desktop/electron/main.cjs`.
- Renderer: `desktop/electron/overlay.html`.
- Preload IPC bridge: `desktop/electron/preload.cjs`.
- Optional renderer debug port for QA: set `NEXA_ELECTRON_DEBUG_PORT`, then launch `npm run electron`.
- Production launch: `npm run electron`.

## Validation

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests\backend
npm run build --prefix frontend
npm run electron:build
npm run electron
```

Use the bubble to verify expand, collapse, drag, Chat, Tasks, dynamic context buttons, and module panels.
