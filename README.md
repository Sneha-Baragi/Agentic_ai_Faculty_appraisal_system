# Faculty Appraisal Management System — Agentic AI

Topic 8 of the Agentic AI Worklets project.

This repository implements a **governed multi-agent appraisal workflow**. Phase 1 is infrastructure only: schema, configuration, JWT stub, a deterministic DEMO scoring engine, and a compile-safe LangGraph skeleton.

**Scoring disclaimer:** DEMO/TEST weightages are used. They are **not** official UGC or institutional API values.

## Phase 1 scope

- PostgreSQL + Alembic models
- FastAPI `/health` and `/api/v1/auth/login` + `/me`
- Deterministic `scoring.engine` (no LLM)
- LangGraph stub graph with parallel collector nodes and a **placeholder** human gate
- React login + empty Faculty / Reviewer shells

**Not in Phase 1:** MinIO/object storage, evidence upload, real LLM calls, persisted LangGraph interrupt, healing, publish, rollback UI.

The human gate must later become a **persisted LangGraph interrupt/checkpoint**. The current node is compile-safe only.

## Demo accounts (after seed)

| Role | Email | Password |
|------|--------|----------|
| Faculty | faculty@demo.local | faculty-demo |
| HoD | hod@demo.local | hod-demo |
| Admin | admin@demo.local | admin-demo |

## Commands

Run from the repository root `E:\Faculty-Appraisal-Agent` unless noted.

### 1. Environment file

```powershell
Copy-Item .env.example .env
```

### 2. Start PostgreSQL

```powershell
docker compose up -d db
```

### 3. Backend virtualenv and dependencies

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 4. Migrations

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head
```

### 5. Seed the database

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m app.seed
```

### 6. Start the API

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health check: `http://localhost:8000/health`

### 7. Start the frontend

```powershell
cd frontend
npm install
npm run dev
```

UI: `http://localhost:5173`

### 8. Run all tests

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest -q
```

### Optional: API + database via Compose (migrates and seeds on start)

```powershell
docker compose up --build
```

Frontend is still `npm run dev` in `frontend` (not in Compose).
