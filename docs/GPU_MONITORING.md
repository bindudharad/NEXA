# Nexa GPU Monitoring

Nexa monitors GPU telemetry through a background FastAPI service.

## Sources

The monitor attempts hardware sources in this order:

1. `nvidia-smi` for NVIDIA GPUs.
2. LibreHardwareMonitor WMI namespace: `root\LibreHardwareMonitor`.
3. OpenHardwareMonitor WMI namespace: `root\OpenHardwareMonitor`.
4. Windows GPU performance counters plus `Win32_VideoController` metadata.

Temperature availability depends on the installed driver and hardware telemetry provider. GPU name and usage can still be available when temperature is not exposed by Windows.

## Default Alert

Default rule:

- GPU temperature `> 50°C`
- Repeat every `5 minutes` while still above threshold
- Stop when temperature is `<= 50°C`

Alert actions:

- Desktop notification titled `Nexa GPU Alert`
- 2-second alert sound at full volume
- Event logged to `backend/logs/nexa.log` with temperature, timestamp, and GPU name

## API

- `GET /api/gpu-monitor/settings`
- `PUT /api/gpu-monitor/settings`
- `GET /api/gpu-monitor/status`
- `POST /api/gpu-monitor/test/simulate`
- `POST /api/gpu-monitor/test/clear`

Simulation examples:

```json
{ "temperature_celsius": 55 }
{ "temperature_celsius": 65 }
{ "temperature_celsius": 75 }
```

## UI

The Nexa Dashboard shows GPU name, GPU usage, GPU temperature, VRAM usage, and health status.

The Settings page includes GPU monitoring enablement, threshold, notification/sound toggles, repeat interval, and simulation controls.
