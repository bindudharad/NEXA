const { app, BrowserWindow, Menu, Tray, ipcMain, nativeImage, screen, shell, Notification, desktopCapturer, globalShortcut } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

let overlay;
let tray;
let backendProcess;
let saveBoundsTimer;
let dockBounds;
let alertPollTimer;
const shownAlertIds = new Set();
let recentAlerts = [];
let voiceStatus = { microphone_status: "offline", mode: "offline", muted: false };
let resourceStatus = { mode: "normal" };
const apiBase = process.env.NEXA_API_BASE || "http://127.0.0.1:8010/api";
const backendUrl = new URL(apiBase);
const dashboardUrl = process.env.NEXA_DASHBOARD_URL || "http://127.0.0.1:5173/";

if (process.env.NEXA_ELECTRON_DEBUG_PORT) {
  app.commandLine.appendSwitch("remote-debugging-port", process.env.NEXA_ELECTRON_DEBUG_PORT);
}

function boundsFile() {
  return path.join(app.getPath("userData"), "overlay-bounds.json");
}

function readSavedBounds() {
  try {
    const bounds = JSON.parse(fs.readFileSync(boundsFile(), "utf8"));
    return clampToDisplay({ ...bounds, width: 96, height: 96 });
  } catch {
    return clampToDisplay({ width: 96, height: 96, x: 40, y: 80 });
  }
}

function clampToDisplay(bounds) {
  const display = screen.getDisplayMatching(bounds);
  const area = display.workArea;
  const width = Math.max(72, Math.min(bounds.width || 96, area.width));
  const height = Math.max(72, Math.min(bounds.height || 96, area.height));
  return {
    width,
    height,
    x: Math.max(area.x, Math.min(bounds.x ?? area.x + 40, area.x + area.width - width)),
    y: Math.max(area.y, Math.min(bounds.y ?? area.y + 80, area.y + area.height - height))
  };
}

function saveBoundsSoon() {
  if (!overlay) return;
  clearTimeout(saveBoundsTimer);
  saveBoundsTimer = setTimeout(() => {
    try {
      fs.writeFileSync(boundsFile(), JSON.stringify(overlay.getBounds(), null, 2));
    } catch {
      // Position persistence is best-effort.
    }
  }, 200);
}

function createOverlay() {
  const bounds = readSavedBounds();
  overlay = new BrowserWindow({
    title: "Nexa",
    width: bounds.width,
    height: bounds.height,
    minWidth: 72,
    minHeight: 72,
    x: bounds.x,
    y: bounds.y,
    alwaysOnTop: true,
    transparent: true,
    frame: false,
    resizable: true,
    skipTaskbar: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false
    }
  });
  app.setName("Nexa");
  overlay.setTitle("Nexa");
  overlay.setAlwaysOnTop(true, "screen-saver");
  overlay.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  overlay.loadFile(path.join(__dirname, "overlay.html"));
  overlay.on("moved", saveBoundsSoon);
  overlay.on("resized", saveBoundsSoon);
  createTray();
}

async function ensureBackend() {
  try {
    const response = await fetch(`${apiBase}/health`);
    if (response.ok) return;
  } catch {
    // Start the local backend below.
  }
  const root = path.resolve(__dirname, "..", "..");
  const python = process.platform === "win32" ? path.join(root, ".venv", "Scripts", "python.exe") : path.join(root, ".venv", "bin", "python");
  const host = backendUrl.hostname || "127.0.0.1";
  const port = backendUrl.port || "8010";
  backendProcess = spawn(python, ["-m", "uvicorn", "backend.main:app", "--host", host, "--port", port], {
    cwd: root,
    detached: false,
    windowsHide: true,
    stdio: "ignore"
  });
}

function createTray() {
  const icon = nativeImage.createFromDataURL(
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAVUlEQVR4nGNgoBAwUqifYdSokP///zMwMDD8Z2BgYGBk+M+ABqA0DGRiYGCAqQGkGJrBqAGkGBrBqAGkGBqBIyMjw39GRkYGhQkGJqDqQKkAAGm5C+9P3W6VAAAAAElFTkSuQmCC"
  );
  tray = new Tray(icon);
  tray.setToolTip("Nexa");
  refreshTrayMenu();
}

function refreshTrayMenu(unreadCount = 0) {
  const loginSettings = app.getLoginItemSettings();
  if (tray) {
    tray.setToolTip(unreadCount > 0 ? `Nexa - ${unreadCount} unread alerts` : "Nexa");
  }
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: "Nexa", enabled: false },
      { label: unreadCount > 0 ? `${unreadCount} unread alerts` : "No unread alerts", enabled: false },
      { label: `Voice: ${voiceStatus.microphone_status || "offline"} (${voiceStatus.mode || "offline"})`, enabled: false },
      { label: `Resource mode: ${resourceStatus.mode || "normal"}`, enabled: false },
      ...recentAlerts.slice(0, 5).map((alert) => ({
        label: `${alert.title} - ${alert.module}`,
        click: () => shell.openExternal(dashboardUrl)
      })),
      { type: "separator" },
      { label: "Show", click: () => overlay?.show() },
      { label: "Hide", click: () => overlay?.hide() },
      { label: "Pause Listening", enabled: !voiceStatus.muted, click: () => setListening(true) },
      { label: "Resume Listening", enabled: !!voiceStatus.muted, click: () => setListening(false) },
      { label: "Show Tasks", click: () => shell.openExternal(dashboardUrl) },
      { label: "Show Notifications", click: () => shell.openExternal(dashboardUrl) },
      {
        label: "Start Nexa on login",
        type: "checkbox",
        checked: loginSettings.openAtLogin,
        click: (item) => app.setLoginItemSettings({ openAtLogin: item.checked })
      },
      { type: "separator" },
      { label: "Quit", click: () => app.quit() }
    ])
  );
}

async function pollAlerts() {
  try {
    const response = await fetch(`${apiBase}/notifications?unread_only=true&limit=10`);
    if (!response.ok) return;
    const alerts = await response.json();
    try {
      const voiceResponse = await fetch(`${apiBase}/voice/status`);
      if (voiceResponse.ok) voiceStatus = await voiceResponse.json();
      const resourceResponse = await fetch(`${apiBase}/resource-manager/status`);
      if (resourceResponse.ok) resourceStatus = await resourceResponse.json();
    } catch {
      // Voice status is best-effort for the tray.
    }
    recentAlerts = alerts;
    refreshTrayMenu(alerts.length);
    for (const alert of alerts) {
      if (shownAlertIds.has(alert.id)) continue;
      shownAlertIds.add(alert.id);
      showElectronAlert(alert);
    }
  } catch {
    // Backend may still be starting.
  }
}

async function setListening(paused) {
  try {
    const response = await fetch(`${apiBase}/voice/${paused ? "pause" : "resume"}`, { method: "POST" });
    if (response.ok) voiceStatus = await response.json();
    refreshTrayMenu(recentAlerts.length);
  } catch {
    // The next poll will retry when the backend is available.
  }
}

function showElectronAlert(alert) {
  if (!Notification.isSupported()) return;
  const notification = new Notification({
    title: alert.title,
    body: `${alert.message}\n\nAction: ${alert.suggested_action}\nModule: ${alert.module}`,
    silent: true,
    urgency: alert.severity === "critical" ? "critical" : "normal",
    actions: (alert.action_buttons || []).slice(0, 2).map((text) => ({ type: "button", text }))
  });
  notification.on("click", () => shell.openExternal(dashboardUrl));
  notification.on("action", async (_event, index) => {
    const action = (alert.action_buttons || [])[index] || "Opened";
    try {
      await fetch(`${apiBase}/notifications/${alert.id}/actions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, payload: { source: "electron_notification" } })
      });
    } catch {
      // Action persistence is best-effort from the shell.
    }
  });
  notification.show();
}

function startAlertPolling() {
  clearInterval(alertPollTimer);
  pollAlerts();
  alertPollTimer = setInterval(pollAlerts, 30000);
}

async function captureScreenshotAssistant(mode = "full_screen") {
  try {
    const display = screen.getPrimaryDisplay();
    const sourceTypes = mode === "active_window" ? ["window"] : ["screen"];
    const sources = await desktopCapturer.getSources({
      types: sourceTypes,
      thumbnailSize: { width: display.size.width, height: display.size.height }
    });
    const source = sources[0];
    if (!source) return;
    const folder = path.join(app.getPath("userData"), "screenshots");
    fs.mkdirSync(folder, { recursive: true });
    const filePath = path.join(folder, `nexa-screenshot-${new Date().toISOString().replace(/[:.]/g, "-")}.png`);
    fs.writeFileSync(filePath, source.thumbnail.toPNG());
    const response = await fetch(`${apiBase}/evolution/screenshots`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_path: filePath, source: "ctrl_shift_a", capture_mode: mode, language: "eng" })
    });
    if (response.ok && Notification.isSupported()) {
      const result = await response.json();
      new Notification({
        title: "Nexa Screenshot Assistant",
        body: `${result.analysis || "Screenshot analyzed."}\n\nModule: screenshot_assistant`,
        silent: true
      }).show();
    }
  } catch (error) {
    try {
      await fetch(`${apiBase}/notifications`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: "Nexa Screenshot Assistant",
          message: `Screenshot capture failed: ${error.message || error}`,
          alert_type: "screenshot",
          module: "screenshot_assistant",
          severity: "medium",
          priority: "medium",
          category: "warning",
          suggested_action: "Check Electron permissions and try Ctrl+Shift+A again.",
          action_buttons: ["Dismiss"]
        })
      });
    } catch {
      // Backend may be unavailable during shutdown/startup.
    }
  }
}

function registerGlobalShortcuts() {
  globalShortcut.unregister("Control+Shift+A");
  globalShortcut.register("Control+Shift+A", () => {
    void captureScreenshotAssistant("full_screen");
  });
}

ipcMain.handle("agent:command", async (_event, command) => {
  if (typeof command !== "string" || command.trim().length === 0 || command.length > 2000) {
    throw new Error("Invalid command");
  }
  const response = await fetch(`${apiBase}/commands`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command })
  });
  return response.json();
});

ipcMain.handle("agent:api", async (_event, apiPath, options = {}) => {
  if (typeof apiPath !== "string" || !apiPath.startsWith("/")) {
    throw new Error("Invalid API path");
  }
  const response = await fetch(`${apiBase}${apiPath}`, {
    method: options.method || "GET",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    body: options.body ? JSON.stringify(options.body) : undefined
  });
  const body = await response.text();
  const data = body ? JSON.parse(body) : {};
  if (!response.ok) {
    throw new Error(data.detail || body || `API failed: ${response.status}`);
  }
  return data;
});

ipcMain.handle("screenshots:capture", async (_event, mode = "full_screen") => {
  const allowed = new Set(["full_screen", "active_window", "current_monitor", "multi_monitor", "selected_area"]);
  const captureMode = allowed.has(mode) ? mode : "full_screen";
  await captureScreenshotAssistant(captureMode === "selected_area" ? "full_screen" : captureMode);
  return { captured: true, mode: captureMode, fallback: captureMode === "selected_area" ? "full_screen" : null };
});

ipcMain.handle("files:open-folder", async (_event, folderKey) => {
  const home = os.homedir();
  const folders = {
    downloads: path.join(home, "Downloads"),
    documents: path.join(home, "Documents"),
    desktop: path.join(home, "Desktop"),
    projects: path.join(home, "Projects")
  };
  const target = folders[folderKey];
  if (!target) throw new Error("Unknown folder");
  await shell.openPath(target);
  return { opened: target };
});

ipcMain.handle("app:open-dashboard", async () => {
  await shell.openExternal(dashboardUrl);
  return { opened: true };
});

ipcMain.on("overlay:context-menu", () => {
  const menu = Menu.buildFromTemplate([
    { label: "Open Nexa Dashboard", click: () => shell.openExternal(dashboardUrl) },
    { label: "Reset Position", click: () => overlay?.setBounds(clampToDisplay({ width: 96, height: 96, x: 40, y: 80 })) },
    { type: "separator" },
    { label: "Hide", click: () => overlay?.hide() },
    { label: "Quit Nexa", click: () => app.quit() }
  ]);
  menu.popup({ window: overlay });
});

ipcMain.on("overlay:move-by", (_event, deltaX, deltaY) => {
  if (!overlay || !Number.isFinite(deltaX) || !Number.isFinite(deltaY)) return;
  const current = overlay.getBounds();
  overlay.setBounds(clampToDisplay({ ...current, x: current.x + Math.round(deltaX), y: current.y + Math.round(deltaY) }), false);
  saveBoundsSoon();
});

ipcMain.on("overlay:resize", (_event, mode) => {
  if (!overlay) return;
  const sizes = {
    bubble: [96, 96],
    radial: [640, 640],
    panel: [760, 640],
    chat: [420, 560]
  };
  const [width, height] = sizes[mode] || sizes.bubble;
  const current = overlay.getBounds();
  if (mode === "bubble") {
    const next = dockBounds ? { ...dockBounds, width, height } : { ...current, width, height };
    overlay.setBounds(clampToDisplay(next), true);
    return;
  }
  if (!dockBounds || current.width <= 128 || current.height <= 128) {
    dockBounds = { x: current.x, y: current.y, width: 96, height: 96 };
  }
  const display = screen.getDisplayMatching(current);
  const area = display.workArea;
  const nearLeft = current.x <= area.x + 24;
  const nearTop = current.y <= area.y + 24;
  const nearRight = current.x + current.width >= area.x + area.width - 24;
  const nearBottom = current.y + current.height >= area.y + area.height - 24;
  const next = {
    ...current,
    width,
    height,
    x: current.x + (nearLeft ? 28 : nearRight ? -28 : 0),
    y: current.y + (nearTop ? 28 : nearBottom ? -28 : 0)
  };
  overlay.setBounds(clampToDisplay(next), true);
});

app.whenReady().then(async () => {
  app.setName("Nexa");
  await ensureBackend();
  createOverlay();
  registerGlobalShortcuts();
  startAlertPolling();
});
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
app.on("before-quit", () => {
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill();
  }
  clearInterval(alertPollTimer);
  globalShortcut.unregisterAll();
});
