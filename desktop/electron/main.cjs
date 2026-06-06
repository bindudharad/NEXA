const { app, BrowserWindow, Menu, Tray, ipcMain, nativeImage } = require("electron");
const { spawn } = require("child_process");
const path = require("path");

let overlay;
let tray;
let backendProcess;
const apiBase = process.env.NEXA_API_BASE || "http://127.0.0.1:8010/api";
const backendUrl = new URL(apiBase);

function createOverlay() {
  overlay = new BrowserWindow({
    title: "Nexa",
    width: 320,
    height: 420,
    minWidth: 72,
    minHeight: 72,
    x: 40,
    y: 80,
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
  overlay.loadFile(path.join(__dirname, "overlay.html"));
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
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: "Nexa", enabled: false },
      { label: "Show", click: () => overlay?.show() },
      { label: "Hide", click: () => overlay?.hide() },
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

ipcMain.on("overlay:resize", (_event, expanded) => {
  if (!overlay) return;
  overlay.setSize(expanded ? 320 : 72, expanded ? 420 : 72, true);
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
