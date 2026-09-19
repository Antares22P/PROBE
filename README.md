# PROBE V1

**Autonomous Web Application Testing Platform**

PROBE autonomously explores web applications, detects problems, collects evidence, reproduces issues, and uses an LLM to analyze findings.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React, TypeScript, Vite, Tailwind CSS, shadcn/ui |
| Backend | Python, FastAPI, Pydantic, SQLAlchemy, SQLite |
| Browser | Playwright for Python |
| Python env | uv |
| Frontend pkg | pnpm |
| Realtime | SSE |
| AI | AIProvider abstraction (Gemini — future) |

---

## Architecture

```
Frontend (React)
    ↓
FastAPI
    ↓
PROBE Core (Orchestrator, Actions, State, Observations)
    ↓
TestDriver Interface (platform-neutral ABC)
    ↓
WebTestDriver → Playwright
```

Future mobile:
```
TestDriver
├── WebTestDriver → Playwright
├── AndroidTestDriver → Appium/ADB
└── IOSTestDriver → Appium
```

> PROBE Core NEVER imports Playwright directly.

---

## Quick Start

### Backend

```bash
cd probe/backend
uv sync
uv run playwright install chromium
uv run uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd probe/frontend
pnpm install
pnpm dev
```

Open: http://localhost:5173

---

## API

| Method | Endpoint | Description |
|---|---|---|
| GET | /api/health | Health check |
| POST | /api/tests | Create test |
| GET | /api/tests | List tests |
| GET | /api/tests/{id} | Get test |
| POST | /api/tests/{id}/start | Start test |
| POST | /api/tests/{id}/cancel | Cancel test |

---

## Running Tests

```bash
cd probe/backend
uv run pytest tests/ -v
```
