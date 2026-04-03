# CHC Backend

**Customs Health Check Backend** — A FastAPI-based multi-tenant backend for E-Customs Health Check processing.

> Created: 2026-04-02

---

## Overview

CHC Backend powers a platform where users submit customs/health-check documents (Excel files), which are then processed via AI analysis and reviewed by experts before results are delivered to users.

**Key capabilities:**
- Multi-tenant isolation via wildcard DNS subdomain middleware
- File upload + async AI analysis (Celery + Redis)
- JWT authentication with Redis token blacklist
- AWS S3 storage (presigned URLs for result delivery)
- AWS SES email notifications (async, per-tenant SMTP fallback)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Python 3.11+ / FastAPI |
| ORM | SQLAlchemy 2.0 (declarative, mapped columns) |
| Database | PostgreSQL |
| Task Queue | Celery + Redis |
| Cache / Auth | Redis (token blacklist) |
| Storage | AWS S3 (presigned URLs) |
| Email | AWS SES (+ per-tenant SMTP override) |
| Auth | JWT (python-jose) + bcrypt |
| Package Manager | uv |
| Deployment | Docker Compose |

---

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL
- Redis
- AWS credentials (optional for dev mode)

### 1. Clone & Install

```bash
git clone <repo-url>
cd chc-backend
uv sync
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your database, Redis, and AWS credentials
```

Key environment variables:

```env
DATABASE_URL=postgresql://user:pass@localhost:5432/chc
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
SECRET_KEY=<generate-a-secure-key>
AWS_ACCESS_KEY_ID=<your-key>
AWS_SECRET_ACCESS_KEY=<your-secret>
S3_BUCKET_NAME=chc-uploads
SES_SENDER_EMAIL=noreply@chc.com
ADMIN_DOMAIN=admin.chc.com
BASE_DOMAIN=chc.com
```

### 3. Run Migrations

```bash
alembic upgrade head
```

### 4. Start Services

```bash
# Backend (development)
uvicorn app.main:app --reload --port 8000

# Celery worker (separate terminal)
celery -A worker worker --loglevel=info
```

### 5. Docker Compose (Production)

```bash
docker compose up --build
```

Services: `app`, `worker`, `postgres`, `redis`

---

## Project Structure

```
chc-backend/
├── app/
│   ├── main.py                  # FastAPI app entry, router registration
│   ├── core/                    # Shared infrastructure
│   │   ├── config.py            # Pydantic Settings (.env)
│   │   ├── database.py          # SQLAlchemy engine, SessionLocal, Base
│   │   ├── redis.py             # Redis client
│   │   ├── security.py          # JWT, bcrypt
│   │   ├── middleware.py         # Tenant subdomain middleware
│   │   └── dependencies.py       # get_current_user, require_roles
│   ├── models/                  # SQLAlchemy ORM models
│   │   ├── tenant.py
│   │   ├── user.py              # User + UserRole enum
│   │   ├── submission.py         # Submission, SubmissionFile, AnalysisJob, enums
│   │   └── password_reset_token.py
│   ├── auth/                    # Login, logout, password reset/change
│   ├── tenants/                  # Tenant CRUD (super_admin only)
│   ├── users/                   # User/expert CRUD within tenant
│   ├── submissions/             # File upload, AI analysis, result publish
│   │   ├── router.py, service.py, repository.py, schemas.py
│   │   └── tasks.py             # Celery task (stub)
│   └── dashboard/              # Aggregated stats by role
├── worker.py                    # Celery app entry point
├── alembic/                    # Database migrations
├── .env.example
├── docker-compose.yml
└── miêu tả dự án.txt           # Business spec (source of truth)
```

---

## API Routes

| Prefix | Module | Access |
|---|---|---|
| `/auth` | auth | Public + authenticated |
| `/dashboard/stats` | dashboard | super_admin, tenant_admin, expert |
| `/tenants` | tenants | super_admin only |
| `/users` | users | tenant_admin only |
| `/submissions` | submissions | Mixed (see below) |

**Submission routes:**
- `POST /submissions` — Upload files (authenticated user)
- `GET /submissions/my` — User's own submissions
- `GET /submissions` — Admin: list tenant submissions
- `POST /{id}/files/{file_id}/analyze` — Trigger AI analysis
- `POST /{id}/analyze-all` — Trigger AI on all files
- `PUT /{id}/files/{file_id}/result` — Expert upload edited result
- `POST /{id}/files/{file_id}/publish` — Publish result to user

---

## Actor Roles

| Role | Description |
|---|---|
| `super_admin` | System-wide: manages tenants and tenant_admins |
| `tenant_admin` | Per-tenant: manages users, experts; full CHC access |
| `expert` | Per-tenant: processes files, reviews AI results |
| `user` | Per-tenant: uploads files, receives results |

---

## TODO / Incomplete Areas

- [ ] S3 file upload/download (stub in `service.py`)
- [ ] AI API integration (stub task in `tasks.py`)
- [ ] AWS SES email sending (stub)
- [ ] Manual input endpoint (`POST /submissions/manual`)
- [ ] Recent dashboard endpoints (`/recent-tenants`, `/recent-users`, `/recent-submissions`)
- [ ] Tenant email config model and router (`/settings/email-config`)
- [ ] Password reset token hashing (stored plain)
- [ ] PostgreSQL advisory lock for submission display_id sequence
- [ ] Alembic migrations (not yet generated)

---

## References

- Business specification: `miêu tả dự án.txt`
- Project overview: `docs/project-overview-pdr.md`
- Code standards: `docs/code-standards.md`
- System architecture: `docs/system-architecture.md`
- Project roadmap: `docs/project-roadmap.md`
