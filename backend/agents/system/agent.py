import os
import subprocess
from pathlib import Path

import psutil


class SystemAgent:
    app_aliases = {
        "chrome": ["chrome.exe"],
        "google chrome": ["chrome.exe"],
        "vs code": ["code"],
        "vscode": ["code"],
        "cursor": ["cursor"],
        "notepad": ["notepad.exe"],
    }

    def execute(self, action: str, params: dict) -> dict:
        return getattr(self, action)(**params)

    def launch_app(self, name: str) -> dict:
        command = self.app_aliases.get(name.lower(), [name])
        subprocess.Popen(command, shell=False)
        return {"launched": name}

    def shutdown(self) -> dict:
        subprocess.Popen(["shutdown", "/s", "/t", "0"], shell=False)
        return {"scheduled": "shutdown"}

    def restart(self) -> dict:
        subprocess.Popen(["shutdown", "/r", "/t", "0"], shell=False)
        return {"scheduled": "restart"}

    def sleep(self) -> dict:
        subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], shell=False)
        return {"scheduled": "sleep"}

    def lock(self) -> dict:
        subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"], shell=False)
        return {"locked": True}

    def kill_process(self, name: str) -> dict:
        killed = []
        for proc in psutil.process_iter(["pid", "name"]):
            if proc.info["name"] and proc.info["name"].lower() == name.lower():
                proc.kill()
                killed.append(proc.info["pid"])
        return {"killed": killed}

    def status(self) -> dict:
        battery = psutil.sensors_battery()
        return {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "ram_percent": psutil.virtual_memory().percent,
            "battery_percent": battery.percent if battery else None,
            "battery_plugged": battery.power_plugged if battery else None,
            "cwd": str(Path.cwd()),
            "user": os.getlogin() if hasattr(os, "getlogin") else "",
        }
