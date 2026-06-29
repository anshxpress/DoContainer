# DoContainer — Enterprise Multimodal Document Intelligence

> **AI-powered document search platform** — upload PDFs, Office files, and images; get back semantically matched pages with visual citations, powered by multi-vector embeddings and hybrid retrieval.

---

## Table of Contents

- [Project Overview](#project-overview)
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

## Project Overview

**DoContainer** is an enterprise-grade document intelligence platform that transforms traditional document storage into an intelligent, secure, and searchable organizational knowledge base. Instead of relying on filenames, folders, or exact keyword searches, DoContainer understands the semantic meaning, structure, and visual content of documents, allowing employees to find information using natural language while respecting enterprise security policies.

The platform is designed for organizations that manage thousands or millions of documents across multiple departments such as Finance, Human Resources, Legal, Engineering, Operations, Research, and Sales. Every uploaded document is automatically processed, indexed, and enriched using AI so that employees can retrieve the right information in seconds without manually browsing complex folder structures.

### Problem Statement

Large organizations face significant challenges managing enterprise documents:

- Millions of files distributed across departments.
- Deep folder hierarchies that are difficult to navigate.
- Duplicate documents and inconsistent file naming.
- Scanned PDFs that cannot be searched effectively.
- Knowledge locked inside reports, contracts, presentations, and manuals.
- Employees spending valuable time searching instead of working.
- Sensitive documents requiring strict access control.

Traditional document management systems rely on filenames and metadata, making it difficult to discover information when users do not know where a document is stored.

DoContainer solves this by converting every document into an intelligent knowledge asset.

### Solution

DoContainer combines document parsing, OCR, multimodal AI, semantic retrieval, and enterprise-grade security into a single platform.

Every uploaded document is automatically:

- Validated and secured
- Parsed into structured content
- OCR processed when required
- Converted into semantic and visual embeddings
- Indexed for fast retrieval
- Enriched with AI-generated metadata
- Protected by Role-Based Access Control (RBAC)

Users can search using natural language instead of remembering filenames or folder locations.

**Example queries:**

- *"Show the latest product specification for Project Phoenix."*
- *"Find all invoices from ABC Corporation."*
- *"Where is the employee leave policy?"*
- *"Show the contract signed with XYZ Company."*
- *"Find documents discussing transformer efficiency."*

DoContainer retrieves only the most relevant documents that the user is authorized to access and generates grounded AI answers with citations.

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
docscope/
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

Start all infrastructure services (PostgreSQL, Redis, Qdrant, MinIO, ClamAV):

```powershell
# From workspace root: d:\docscope
docker compose -f k8s\docker-compose.yml up -d
```

Verify all containers are running:

```powershell
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Expected healthy containers:

| Container | Port | Purpose |
|-----------|------|---------|
| `docscope-db` | `5435` | PostgreSQL database |
| `docscope-redis` | `6379` | Celery broker + result backend |
| `docscope-qdrant` | `6333` | Vector database |
| `docscope-minio` | `9000` / `9001` | Object storage (MinIO console on 9001) |
| `docscope-clamav` | `3310` | Malware scanning daemon |

> **Port conflicts?** If Redis (6379) or MinIO (9000) are already in use by another project, the docscope services will reuse the existing ones automatically — the default credentials (`minioadmin`/`minioadmin`, no Redis auth) are the same.

---

### 2. Start the Backend

The backend runs **directly from your terminal** using the local Python virtual environment — not inside Docker.

#### First time only — create the virtual environment and install packages:

```powershell
cd d:\docscope\backend

# Create venv (using uv — recommended)
uv venv .venv

# Activate it
.venv\Scripts\Activate.ps1

# Install dependencies
uv pip install -r requirements.txt
```

#### Generate RSA key pair (first time only):

```powershell
# From d:\docscope\backend
mkdir certs
openssl genrsa -out certs/private_key.pem 2048
openssl rsa -in certs/private_key.pem -pubout -out certs/public_key.pem
```

Or copy from root `certs/` folder if already generated:
```powershell
Copy-Item d:\docscope\certs\* d:\docscope\backend\certs\
```

#### Run database migrations:

```powershell
# From d:\docscope\backend  (must be inside backend/)
$env:PYTHONPATH = "d:\docscope"
.venv\Scripts\python.exe -m alembic upgrade head
```

#### Start the backend server:

```powershell
# From d:\docscope  (workspace root — REQUIRED for imports)
$env:PYTHONPATH = "d:\docscope"
d:\docscope\backend\.venv\Scripts\uvicorn.exe backend.app.main:app --host 0.0.0.0 --port 8001 --reload
```

| URL | Description |
|-----|-------------|
| `http://localhost:8001/` | Root health check |
| `http://localhost:8001/api/v1/openapi.json` | OpenAPI spec (Swagger UI) |
| `http://localhost:8001/docs` | Swagger interactive UI |

> **`--reload`** watches for Python file changes and restarts automatically.

#### (Optional) Start the Celery worker for background ingestion tasks:

```powershell
# From d:\docscope  (separate terminal window)
$env:PYTHONPATH = "d:\docscope"
d:\docscope\backend\.venv\Scripts\celery.exe -A backend.app.tasks.celery_app.celery_app worker --loglevel=info -Q default,ingestion-dlq
```

---

### 3. Start the Frontend

```powershell
# From d:\docscope\frontend  (separate terminal window)
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
DATABASE_URL=postgresql://postgres:postgres@localhost:5435/docscope

# RSA Key Paths (relative to where uvicorn is run from — d:\docscope)
RSA_PRIVATE_KEY_PATH=backend/certs/private_key.pem
RSA_PUBLIC_KEY_PATH=backend/certs/public_key.pem

# S3 / MinIO
S3_ENDPOINT_URL=http://localhost:9000
S3_BUCKET_NAME=docscope-storage
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
# Apply all pending migrations  (run from d:\docscope\backend)
$env:PYTHONPATH = "d:\docscope"
.venv\Scripts\python.exe -m alembic upgrade head

# Generate a new migration after changing models.py
$env:PYTHONPATH = "d:\docscope"
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
| `POST` | `/api/v1/auth/register` | `{email, password, first_name, last_name, org_name}` | Register new user + org. Returns JWT. |
| `POST` | `/api/v1/auth/login` | `{email, password}` | Login. Returns JWT + sets HttpOnly refresh cookie. |

### Search

| Method | Endpoint | Auth | Body | Description |
|--------|----------|------|------|-------------|
| `POST` | `/api/v1/search` | Bearer JWT | `{query, folder_id?, top_k?}` | Hybrid semantic + keyword search. Returns matched pages with S3 presigned URLs. |

### Example: Register + Search

```powershell
# 1. Register
$reg = Invoke-RestMethod -Uri "http://localhost:8001/api/v1/auth/register" `
  -Method POST -ContentType "application/json" `
  -Body '{"email":"you@example.com","password":"Pass1234!","org_name":"My Org"}'

# 2. Search
Invoke-RestMethod -Uri "http://localhost:8001/api/v1/search" `
  -Method POST -ContentType "application/json" `
  -Headers @{"Authorization"="Bearer $($reg.access_token)"} `
  -Body '{"query":"quarterly earnings report","top_k":5}'
```

---

## Running Tests

```powershell
# From d:\docscope  (workspace root)
$env:PYTHONPATH = "d:\docscope"

# Run all tests
d:\docscope\backend\.venv\Scripts\pytest backend\tests\ -v

# Run only Sprint 3 search tests
d:\docscope\backend\.venv\Scripts\pytest backend\tests\test_search.py -v

# Run with coverage report
d:\docscope\backend\.venv\Scripts\pytest backend\tests\ -v --tb=short
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
# Stop Docker services (data is preserved in volumes)
docker compose -f k8s\docker-compose.yml stop

# Stop Docker services AND delete all data volumes
docker compose -f k8s\docker-compose.yml down -v

# Backend and Frontend — just close the terminal windows (Ctrl+C)
```