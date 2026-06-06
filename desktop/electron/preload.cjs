const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("nexa", {
  command: (command) => ipcRenderer.invoke("agent:command", command),
  resize: (expanded) => ipcRenderer.send("overlay:resize", expanded)
});
