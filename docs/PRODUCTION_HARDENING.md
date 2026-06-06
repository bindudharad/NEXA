# Production Hardening

Before distributing Nexa:

- Sign Electron builds.
- Restrict file operations to user-approved folders.
- Add per-action permissions and audit history.
- Run the backend as a Windows service.
- Add encrypted storage for API keys and secrets.
- Add OAuth or local Windows Hello unlock for destructive actions.
- Enable recurring automation polling as a managed background worker.
- Add vector memory behind the existing memory interface.
