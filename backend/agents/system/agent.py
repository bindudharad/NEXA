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
        disk = psutil.disk_usage(str(Path.home().anchor or Path.cwd()))
        temperatures = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
        temperature_values = [
            item.current
            for entries in temperatures.values()
            for item in entries
            if item.current is not None
        ]
        network = psutil.net_io_counters()
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory().percent
        disk_percent = disk.percent
        health_score = max(0, min(100, round(100 - ((cpu * 0.35) + (ram * 0.35) + (disk_percent * 0.2)))))
        process_names = {
            (proc.info.get("name") or "").lower()
            for proc in psutil.process_iter(["name"])
        }
        downloads = Path.home() / "Downloads"
        download_active = False
        if downloads.exists():
            download_active = any(
                item.suffix.lower() in {".crdownload", ".part", ".tmp"}
                for item in downloads.iterdir()
                if item.is_file()
            )
        return {
            "cpu_percent": cpu,
            "ram_percent": ram,
            "disk_percent": disk_percent,
            "gpu_percent": None,
            "temperature_celsius": round(max(temperature_values), 1) if temperature_values else None,
            "network_bytes_sent": network.bytes_sent,
            "network_bytes_recv": network.bytes_recv,
            "process_count": len(psutil.pids()),
            "health_score": health_score,
            "battery_percent": battery.percent if battery else None,
            "battery_plugged": battery.power_plugged if battery else None,
            "battery_secs_left": battery.secsleft if battery else None,
            "context": {
                "vscode_open": "code.exe" in process_names,
                "cursor_open": "cursor.exe" in process_names,
                "chrome_open": "chrome.exe" in process_names,
                "spotify_open": "spotify.exe" in process_names,
                "downloads_active": download_active,
                "git_active": "git.exe" in process_names,
                "system_attention": cpu >= 80 or ram >= 85 or disk_percent >= 90,
            },
            "cwd": str(Path.cwd()),
            "user": os.getlogin() if hasattr(os, "getlogin") else "",
        }
