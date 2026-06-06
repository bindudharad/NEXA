const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("nexa", {
  command: (command) => ipcRenderer.invoke("agent:command", command),
  api: (path, options) => ipcRenderer.invoke("agent:api", path, options),
  openFolder: (folderKey) => ipcRenderer.invoke("files:open-folder", folderKey),
  dashboard: () => ipcRenderer.invoke("app:open-dashboard"),
  contextMenu: () => ipcRenderer.send("overlay:context-menu"),
  moveBy: (deltaX, deltaY) => ipcRenderer.send("overlay:move-by", deltaX, deltaY),
  resize: (mode) => ipcRenderer.send("overlay:resize", mode)
});
