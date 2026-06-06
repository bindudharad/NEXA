# Install Nexa

## Prerequisites

- Windows 10 or 11
- Python 3.10+
- Node.js 20+
- npm

## Backend

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
python -m playwright install chromium
python -m backend.run
```

If port `8010` is already in use:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8010
$env:VITE_API_BASE="http://127.0.0.1:8010/api"
npm --prefix frontend run dev
```

## Frontend

```powershell
npm --prefix frontend install
npm --prefix frontend run dev
```

## Desktop Overlay

```powershell
npm --prefix desktop install
npm --prefix desktop run dev
```

## Environment

Optional `.env` values:

```dotenv
NEXA_OPENAI_API_KEY=...
NEXA_OLLAMA_BASE_URL=http://localhost:11434
NEXA_DATABASE_URL=sqlite:///./nexa.db
```
