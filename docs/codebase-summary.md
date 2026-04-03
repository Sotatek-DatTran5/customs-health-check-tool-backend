# CHC Backend — Codebase Summary

> Created: 2026-04-02

---

## Directory Structure

```
chc-backend/
├── app/
│   ├── main.py                    # FastAPI app, router registration
│   ├── core/                      # Shared infrastructure
│   │   ├── config.py              # Pydantic BaseSettings, .env vars
│   │   ├── database.py            # SQLAlchemy engine, SessionLocal, Base
│   │   ├── redis.py               # Redis client (singleton)
│   │   ├── security.py            # JWT encode/decode, bcrypt hash/verify, blacklist
│   │   ├── middleware.py          # Tenant subdomain resolution middleware
│   │   └── dependencies.py        # FastAPI deps: get_current_user, require_roles
│   ├── models/                    # SQLAlchemy ORM models
│   │   ├── tenant.py              # Tenant model
│   │   ├── user.py                # User model + UserRole enum
│   │   ├── submission.py           # Submission, SubmissionFile, AnalysisJob + enums
│   │   └── password_reset_token.py # PasswordResetToken model
│   ├── auth/                      # Authentication module
│   │   ├── router.py              # /auth/login, /logout, /reset-password, /change-password
│   │   └── service.py             # Auth business logic
│   ├── tenants/                   # Tenant management (super_admin only)
│   │   ├── router.py, service.py, repository.py, schemas.py
│   ├── users/                     # User/expert management (tenant_admin only)
│   │   ├── router.py, service.py, repository.py, schemas.py
│   ├── submissions/               # Core CHC processing module
│   │   ├── router.py              # All submission endpoints
│   │   ├── service.py             # Upload, AI trigger, publish, result URL
│   │   ├── repository.py           # DB queries for submissions/files/jobs
│   │   ├── schemas.py             # Pydantic request/response models
│   │   └── tasks.py               # Celery task: run_ai_analysis (stub)
│   └── dashboard/                  # Dashboard stats
│       ├── router.py, service.py, schemas.py
├── worker.py                      # Celery app entry point
├── alembic/                       # DB migrations (not yet generated)
├── .env.example
├── docker-compose.yml
└── miêu tả dự án.txt             # Business spec (Vietnamese)
```

---

## Module Descriptions

### `app/core/` — Infrastructure

| File | Responsibility |
|---|---|
| `config.py` | All settings from environment variables via `pydantic_settings.BaseSettings`. Values: DB URL, Redis URL, AWS keys, JWT secret, domain config. |
| `database.py` | SQLAlchemy `engine`, `SessionLocal`, `get_db` dependency, `Base` declarative class. |
| `redis.py` | Singleton `redis_client` from URL. Used for token blacklist. |
| `security.py` | `hash_password`, `verify_password` (bcrypt); `create_access_token`, `decode_access_token` (JWT HS256); `blacklist_token`, `is_token_blacklisted` (Redis). |
| `middleware.py` | `tenant_middleware`: extracts subdomain from Host header, queries active tenant, injects `request.state.tenant_id`. Skips admin domain. |
| `dependencies.py` | `get_current_user`: bearer token → JWT decode → Redis blacklist check → DB user lookup. `require_roles(*roles)`: returns a `checker` dependency that enforces role. |

### `app/models/` — Database Models

All models extend `app.core.database.Base` and use SQLAlchemy 2.0 `Mapped` + `mapped_column` style.

| Model | Table | Key Fields |
|---|---|---|
| `Tenant` | `tenants` | id, name, tenant_code (unique), subdomain (unique), description, is_active |
| `User` | `users` | id, tenant_id (FK, nullable), email (unique), username (unique, nullable), password_hash, full_name, role (UserRole enum), is_active, is_first_login, last_login_at |
| `PasswordResetToken` | `password_reset_tokens` | id, user_id (FK), token (unique), expires_at, used_at |
| `Submission` | `submissions` | id, tenant_id (FK), user_id (FK), display_id (unique per tenant), type (SubmissionType), submitted_at |
| `SubmissionFile` | `submission_files` | id, submission_id (FK), original_filename, s3_key, ai_status, ai_s3_key, expert_s3_key, reviewed_by, notes, delivery_status, published_at |
| `AnalysisJob` | `analysis_jobs` | id, submission_file_id (FK), triggered_by (FK), celery_task_id, status, started_at, completed_at, error_message |

**Enums in `submission.py`:**
- `UserRole`: `super_admin`, `tenant_admin`, `expert`, `user`
- `AIStatus`: `not_started`, `running`, `completed`, `failed`
- `DeliveryStatus`: `not_sent`, `sent`, `failed`
- `SubmissionType`: `file_upload`, `batch_dataset`, `manual_input`

### `app/auth/`

- `POST /auth/login` — Validate credentials → return JWT
- `POST /auth/logout` — Add token to Redis blacklist
- `POST /auth/reset-password` — Reset with token from email link
- `POST /auth/change-password` — Change password for logged-in user (requires current password)

### `app/tenants/` (super_admin only)

- `GET /tenants` — List all tenants
- `POST /tenants` — Create tenant + initial tenant_admin account
- `GET /tenants/{tenant_id}` — Get tenant detail
- `PUT /tenants/{tenant_id}` — Update tenant
- `DELETE /tenants/{tenant_id}` — Soft delete (is_active = false)

### `app/users/` (tenant_admin only)

- `GET /users` — List users/experts in tenant
- `POST /users` — Create user/expert (generates temp password, sends email)
- `PUT /users/{user_id}` — Update full_name, is_active
- `DELETE /users/{user_id}` — Soft delete
- `POST /users/{user_id}/reset-password` — Request password reset email

### `app/submissions/`

**User-facing (authenticated user):**
- `POST /submissions` — Upload files, create submission
- `GET /submissions/my` — List own submissions
- `GET /submissions/my/{id}` — Get own submission detail
- `GET /submissions/my/{id}/files/{file_id}/result` — Get presigned download URL

**Admin/expert-facing (expert or tenant_admin):**
- `GET /submissions` — List all submissions in tenant
- `GET /submissions/{id}` — Get submission detail
- `GET /submissions/{id}/files/{file_id}/download` — Stream original file from S3
- `POST /submissions/{id}/files/{file_id}/analyze` — Trigger AI analysis
- `POST /submissions/{id}/analyze-all` — Trigger AI on all files in submission
- `PUT /submissions/{id}/files/{file_id}/result` — Expert upload edited result + notes
- `POST /submissions/{id}/files/{file_id}/publish` — Publish result, send email to user

### `app/dashboard/`

- `GET /dashboard/stats` — Returns `DashboardStats` (role-dependent scope):
  - super_admin: system-wide counts
  - tenant_admin: tenant-scoped counts
  - expert: tenant-scoped submission counts

---

## Layered Architecture Per Module

Each functional module follows a **Router → Service → Repository** pattern:

```
Router (FastAPI endpoint)
  └─► Service (business logic, orchestration)
        └─► Repository (SQLAlchemy queries)
```

Schemas (Pydantic models) are defined separately in `schemas.py`.

---

## Key Implementation Notes

### Tenant Isolation
All repository queries filter by `tenant_id`. The `tenant_id` is injected by middleware into `request.state` and accessed via `current_user.tenant_id` in services.

### JWT Auth Flow
1. Login → `create_access_token({"user_id": user.id})`
2. Every request → `Authorization: Bearer <token>` header
3. `get_current_user` dependency → decode → Redis blacklist check → return `User`
4. Logout → `blacklist_token(token, remaining_ttl)` in Redis

### Celery Task (stub)
`app/submissions/tasks.py::run_ai_analysis`:
- Input: `submission_file_id`, `job_id`
- Steps: download from S3 → call AI API → upload result to S3 → update DB
- On error: set `ai_status = failed`, save `error_message`
- No auto-retry; expert re-triggers manually

### S3 Integration (stubs)
- Upload: `s3_key = {tenant_id}/{user_id}/{submission_id}/{filename}`
- Result key: `expert_s3_key` takes priority over `ai_s3_key`
- Presigned URL: generated on-demand for user downloads (7-day expiry)
