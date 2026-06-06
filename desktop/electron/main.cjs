const { app, BrowserWindow, Menu, Tray, ipcMain, nativeImage, screen, shell } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

let overlay;
let tray;
let backendProcess;
let saveBoundsTimer;
let dockBounds;
const apiBase = process.env.NEXA_API_BASE || "http://127.0.0.1:8010/api";
const backendUrl = new URL(apiBase);

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
  const loginSettings = app.getLoginItemSettings();
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: "Nexa", enabled: false },
      { label: "Show", click: () => overlay?.show() },
      { label: "Hide", click: () => overlay?.hide() },
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
  await shell.openExternal("http://127.0.0.1:5173/");
  return { opened: true };
});

ipcMain.on("overlay:context-menu", () => {
  const menu = Menu.buildFromTemplate([
    { label: "Open Nexa Dashboard", click: () => shell.openExternal("http://127.0.0.1:5173/") },
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
});
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
app.on("before-quit", () => {
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill();
  }
});
