# DoContainer Personal AI Workspace

> A lightweight AI-powered personal document management system that helps users securely store, organize, search, summarize, and chat with their documents using semantic search, OCR, and Retrieval-Augmented Generation.

---

## What is DoContainer Personal?

**DoContainer Personal** is an AI-powered personal document workspace where a single user can:

- 📤 **Upload** documents (PDF, DOCX, images, and more)
- 📁 **Organize** documents into folders with tags and favorites
- 🔍 **Search** documents using hybrid semantic + keyword search
- 💬 **Chat** with their documents using Retrieval-Augmented Generation
- 📝 **Generate AI summaries** and executive overviews
- 🔁 **Detect duplicates** automatically
- 🖺 **OCR** scanned PDFs adaptively (never run on digital PDFs)

Think of it as an **AI-powered personal Google Drive** — where you can ask questions about your documents instead of browsing folders.

---

## Editions

DoContainer ships from a single codebase with three editions controlled by the `APP_MODE` environment variable.

| Edition | `APP_MODE` | Status | Description |
|---------|-----------|--------|-------------|
| **Personal** | `personal` | ✅ Default | Lightweight single-user AI workspace |
| **Team** | `team` | 🔲 Future | Shared workspace + collaboration |
| **Enterprise** | `enterprise` | 🔲 Preserved | Full RBAC, ACL, Approvals, Audit, Monitoring |

### DoContainer Personal includes:
- Document Upload & Folder Management
- Adaptive OCR (scanned PDFs only)
- Docling Parsing + Semantic Chunking
- BGE-M3 Embeddings + Qdrant Vector Search
- Hybrid Search (semantic + keyword + RRF)
- AI Chat (RAG via Gemini)
- Executive Summaries
- Duplicate Detection
- Favorites & Recent Documents

### Enterprise Edition is preserved in the codebase

All enterprise modules (Organizations, Teams, RBAC, ACL, Approvals, Audit, Monitoring, Knowledge Graph, Analytics, Notifications, Workflow Engine) remain fully implemented in the codebase. They are **disabled — not deleted** — via feature flags and clearly labeled comments:

```python
# Enterprise Feature Disabled — Approval Workflow
# Restore by setting ENABLE_APPROVAL=True (Enterprise mode).
```

To re-enable the full Enterprise Edition, set:

```env
APP_MODE=enterprise
```

---

## Table of Contents

- [What is DoContainer Personal?](#what-is-DoContainer-personal)
- [Editions](#editions)
- [Tech Stack](#tech-stack)
- [Repository Structure](#repository-structure)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
  - [1. Start Infrastructure (Docker)](#1-start-infrastructure-docker)
  - [2. Start the Backend](#2-start-the-backend)
  - [3. Start the Frontend](#3-start-the-frontend)
- [Environment Variables](#environment-variables)
- [Database Migrations](#database-migrations)
- [API Reference](#api-reference)
- [Running Tests](#running-tests)
- [What's Built (Sprint Progress)](#whats-built-sprint-progress)
- [Stopping Everything](#stopping-everything)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend API** | Python 3.12 · FastAPI · SQLAlchemy · Alembic |
| **Auth** | RS256 JWT (access + refresh tokens in HttpOnly cookies) |
| **Task Queue** | Celery · Redis |
| **Vector Search** | Qdrant (multi-vector MaxSim / ColQwen2-compatible) |
| **Keyword Search** | PostgreSQL full-text search (`tsvector` / `GIN`) |
| **Hybrid Fusion** | Reciprocal Rank Fusion (RRF) |
| **File Storage** | MinIO (S3-compatible) |
| **Malware Scan** | ClamAV |
| **PDF → PNG** | LibreOffice + pdf2image |
| **Frontend** | Next.js 16 · TypeScript · Tailwind CSS |
| **Infrastructure** | Docker Compose (dev) |

---

## Repository Structure

```
DoContainer/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py              # Auth dependency injection
│   │   │   └── v1/
│   │   │       ├── auth.py          # /auth/register, /auth/login
│   │   │       └── search.py        # POST /search
│   │   ├── core/
│   │   │   ├── config.py            # Settings (pydantic-settings)
│   │   │   ├── db.py                # SQLAlchemy session
│   │   │   ├── qdrant.py            # Qdrant client + collection init + search
│   │   │   ├── s3.py                # MinIO/S3 client
│   │   │   └── security.py          # RS256 JWT helpers
│   │   ├── models/
│   │   │   ├── base.py              # DeclarativeBase
│   │   │   └── models.py            # ORM models (User, Org, Document, SearchLog…)
│   │   ├── repositories/
│   │   │   └── base_repo.py         # Generic CRUD + FTS search repo
│   │   ├── schemas/
│   │   │   └── schemas.py           # Pydantic request/response schemas
│   │   ├── services/
│   │   │   ├── retriever.py         # MockRetriever / ColQwen2Retriever
│   │   │   ├── search_service.py    # Hybrid search + RRF
│   │   │   └── validation.py        # File type/size validation
│   │   ├── tasks/
│   │   │   ├── celery_app.py        # Celery configuration + DLQ
│   │   │   └── tasks.py             # Ingestion pipeline tasks
│   │   └── main.py                  # FastAPI app entry point
│   ├── migrations/                  # Alembic migration versions
│   ├── tests/                       # pytest test suite
│   ├── certs/                       # RSA key pair (auto-generated)
│   ├── requirements.txt
│   └── alembic.ini
├── frontend/
│   └── src/                         # Next.js app (App Router)
├── k8s/
│   ├── docker-compose.yml           # All infrastructure services
│   └── init.sql                     # PostgreSQL init script
└── certs/                           # RSA key pair (shared)
```

---

## Prerequisites

Install these before starting:

| Tool | Version | Download |
|------|---------|----------|
| Docker Desktop | Latest | https://docs.docker.com/desktop/windows/install/ |
| Python | 3.12+ | https://python.org |
| Node.js | 18+ | https://nodejs.org |
| Git | Any | https://git-scm.com |

> **Python virtual environment** is at `backend/.venv` — it must be created once using `uv` or `pip`.

---

## Quick Start

### 1. Start Infrastructure (Docker)

Start all infrastructure services based on your preferred edition:

**Personal Edition (Default)**
```powershell
# From workspace root: d:\DoContainer
docker compose -f docker-compose.personal.yml up -d
```

**Enterprise Edition**
```powershell
# From workspace root: d:\DoContainer
docker compose -f docker-compose.enterprise.yml up -d
```

Verify all containers are running:

```powershell
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Expected healthy containers:

| Container | Port | Purpose |
|-----------|------|---------|
| `DoContainer-db` | `5435` | PostgreSQL database |
| `DoContainer-redis` | `6379` | Celery broker + result backend |
| `DoContainer-qdrant` | `6333` | Vector database |
| `DoContainer-minio` | `9000` / `9001` | Object storage (MinIO console on 9001) |
| `DoContainer-clamav` | `3310` | Malware scanning daemon |

> **Port conflicts?** If Redis (6379) or MinIO (9000) are already in use by another project, the DoContainer services will reuse the existing ones automatically — the default credentials (`minioadmin`/`minioadmin`, no Redis auth) are the same.

---

### 2. Start the Backend

The backend runs **directly from your terminal** using the local Python virtual environment — not inside Docker.

#### First time only — create the virtual environment and install packages:

```powershell
cd d:\DoContainer\backend

# Create venv (using uv — recommended)
uv venv .venv

# Activate it
.venv\Scripts\Activate.ps1

# Install dependencies
uv pip install -r requirements.txt
```

#### Generate RSA key pair (first time only):

```powershell
# From d:\DoContainer\backend
mkdir certs
openssl genrsa -out certs/private_key.pem 2048
openssl rsa -in certs/private_key.pem -pubout -out certs/public_key.pem
```

Or copy from root `certs/` folder if already generated:
```powershell
Copy-Item d:\DoContainer\certs\* d:\DoContainer\backend\certs\
```

#### Run database migrations:

```powershell
# From d:\DoContainer\backend  (must be inside backend/)
$env:PYTHONPATH = "d:\DoContainer"
.venv\Scripts\python.exe -m alembic upgrade head
```

#### Start the backend server:

```powershell
# From d:\DoContainer  (workspace root — REQUIRED for imports)
$env:PYTHONPATH = "d:\DoContainer"
d:\DoContainer\backend\.venv\Scripts\uvicorn.exe backend.app.main:app --host 0.0.0.0 --port 8001 --reload
```

| URL | Description |
|-----|-------------|
| `http://localhost:8001/` | Root health check |
| `http://localhost:8001/api/v1/openapi.json` | OpenAPI spec (Swagger UI) |
| `http://localhost:8001/docs` | Swagger interactive UI |

> **`--reload`** watches for Python file changes and restarts automatically.

#### (Optional) Start the Celery worker for background ingestion tasks:

```powershell
# From d:\DoContainer  (separate terminal window)
$env:PYTHONPATH = "d:\DoContainer"
d:\DoContainer\backend\.venv\Scripts\celery.exe -A backend.app.tasks.celery_app.celery_app worker --loglevel=info -Q default,ingestion-dlq
```

---

### 3. Start the Frontend

```powershell
# From d:\DoContainer\frontend  (separate terminal window)
npm run dev
```

| URL | Description |
|-----|-------------|
| `http://localhost:3000` | Frontend app |

> **First time?** Run `npm install` inside `frontend/` if `node_modules` is missing.

---

## Environment Variables

The backend reads from `backend/.env` (created automatically from defaults if absent).
Create `backend/.env` to override any setting:

```env
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5435/DoContainer

# RSA Key Paths (relative to where uvicorn is run from — d:\DoContainer)
RSA_PRIVATE_KEY_PATH=backend/certs/private_key.pem
RSA_PUBLIC_KEY_PATH=backend/certs/public_key.pem

# S3 / MinIO
S3_ENDPOINT_URL=http://localhost:9000
S3_BUCKET_NAME=DoContainer-storage
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
AWS_REGION=us-east-1

# Celery / Redis
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Qdrant
QDRANT_URL=http://localhost:6333

# ClamAV
CLAMAV_HOST=localhost
CLAMAV_PORT=3310
```

---

## Database Migrations

Alembic manages all schema changes.

```powershell
# Apply all pending migrations  (run from d:\DoContainer\backend)
$env:PYTHONPATH = "d:\DoContainer"
.venv\Scripts\python.exe -m alembic upgrade head

# Generate a new migration after changing models.py
$env:PYTHONPATH = "d:\DoContainer"
.venv\Scripts\python.exe -m alembic revision --autogenerate -m "describe_your_change"

# Check current revision
.venv\Scripts\python.exe -m alembic current

# Rollback one step
.venv\Scripts\python.exe -m alembic downgrade -1
```

---

## API Reference

### Authentication

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| `POST` | `/api/v1/auth/register` | `{email, password, first_name, last_name}` | Register new user. Personal workspace is auto-created. Returns JWT. |
| `POST` | `/api/v1/auth/login` | `{email, password}` | Login. Returns JWT + sets HttpOnly refresh cookie. |

### Search

| Method | Endpoint | Auth | Body | Description |
|--------|----------|------|------|-------------|
| `POST` | `/api/v1/search` | Bearer JWT | `{query, folder_id?, top_k?}` | Hybrid semantic + keyword search. Returns matched pages with S3 presigned URLs. |

### Example: Register + Search

```powershell
# 1. Register (no org_name needed in Personal Edition — auto-created)
$reg = Invoke-RestMethod -Uri "http://localhost:8001/api/v1/auth/register" `
  -Method POST -ContentType "application/json" `
  -Body '{"email":"you@example.com","password":"Pass1234!","first_name":"Jane","last_name":"Doe"}'

# 2. Search
Invoke-RestMethod -Uri "http://localhost:8001/api/v1/search" `
  -Method POST -ContentType "application/json" `
  -Headers @{"Authorization"="Bearer $($reg.access_token)"} `
  -Body '{"query":"quarterly earnings report","top_k":5}'
```

---

## Running Tests

```powershell
# From d:\DoContainer  (workspace root)
$env:PYTHONPATH = "d:\DoContainer"

# Run all tests
d:\DoContainer\backend\.venv\Scripts\pytest backend\tests\ -v

# Run only Sprint 3 search tests
d:\DoContainer\backend\.venv\Scripts\pytest backend\tests\test_search.py -v

# Run with coverage report
d:\DoContainer\backend\.venv\Scripts\pytest backend\tests\ -v --tb=short
```

**Current test status: 33/33 passing ✅**

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_auth.py` | Registration + login flow | Auth endpoints |
| `test_folders.py` | Folder hierarchy + cascade delete | Folder repo |
| `test_integration.py` | Full Celery ingestion pipeline E2E | All 4 pipeline tasks |
| `test_search.py` | RRF, MockRetriever, permission isolation, HTTP validation | Search layer |
| `test_tasks.py` | Malware scan, PDF convert, page render, embed | Individual Celery tasks |
| `test_tenant.py` | Cross-tenant 403 rejection | Auth + tenant middleware |
| `test_validation.py` | File type + size validation | Validation service |

---

## What's Built (Sprint Progress)

### ✅ Sprint 1 — Foundation & Auth
- Multi-tenant data model (Organizations → Teams → Users → Roles → Permissions)
- RS256 JWT authentication (access token 15min + HttpOnly refresh 7 days)
- RBAC permission checker middleware
- Folder hierarchy with cascade delete
- File type + size validation service

### ✅ Sprint 2 — Document Ingestion Pipeline
- Celery task chain: `scan_malware` → `convert_to_pdf` → `render_pages` → `embed_and_index`
- ClamAV malware scanning with S3 quarantine routing
- LibreOffice PDF conversion (with mock fallback for dev)
- pdf2image page rendering at 200 DPI → PNG storage in MinIO
- Qdrant multi-vector indexing (128-dim, MaxSim comparator)
- Exponential backoff retry policy + Dead Letter Queue (DLQ)
- PostgreSQL status tracking: `queued → processing → completed / failed`

### ✅ Sprint 3 — AI Retrieval & Semantic Search
- `MockRetriever` (deterministic, no GPU) + `ColQwen2Retriever` stub with auto-fallback
- Qdrant `query_points` with multi-tenant payload filter (org_id + folder_id + team_ids)
- PostgreSQL FTS with `tsvector` / `plainto_tsquery` / `GIN` index + `ts_rank` ordering
- **Reciprocal Rank Fusion (RRF)** blending vision and keyword results
- `POST /api/v1/search` — authenticated, permission-gated, returns presigned S3 image URLs
- `search_logs` telemetry table capturing query, latency, result count
- 18 new unit tests covering all search layer components

### 🔲 Sprint 4 — Frontend UI (Upcoming)
- Document upload UI
- Search interface with visual page citations
- Organization + team management dashboard

---

## Stopping Everything

```powershell
# Personal Edition — stop and preserve data
docker compose -f docker-compose.personal.yml stop

# Personal Edition — stop and delete all volumes
docker compose -f docker-compose.personal.yml down -v

# Enterprise Edition — stop and preserve data
docker compose -f docker-compose.enterprise.yml stop

# Backend and Frontend — just close the terminal windows (Ctrl+C)
```
