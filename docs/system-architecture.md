# CHC Backend — System Architecture

> Created: 2026-04-02

---

## 1. High-Level Architecture

```
                        ┌──────────────────────────────────────────┐
                        │               Internet                    │
                        └──────────────────┬───────────────────────┘
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    │                      │                       │
              admin.chc.com          acme.chc.com           other.chc.com
              (admin site)           (user site)            (user site)
                    │                      │                       │
                    └──────────────────────┼───────────────────────┘
                                           │
                        ┌──────────────────▼──────────────────────┐
                        │         FastAPI Backend (app)             │
                        │  ┌────────────────────────────────────┐  │
                        │  │    Tenant Subdomain Middleware     │  │
                        │  │  (Host → tenant_id via request.state) │
                        │  └────────────────────────────────────┘  │
                        │  ┌────────────────────────────────────┐  │
                        │  │    JWT Auth Middleware              │  │
                        │  │  (Bearer token → Redis blacklist check) │
                        │  └────────────────────────────────────┘  │
                        │  ┌────────────────────────────────────┐  │
                        │  │        Router Layer                │  │
                        │  │  /auth /tenants /users /submissions │  │
                        │  │  /dashboard                         │  │
                        │  └────────────────────────────────────┘  │
                        └───────────────┬──────────────────────────┘
                                        │
              ┌──────────────────────────┼──────────────────────────┐
              │                          │                          │
        ┌─────▼──────┐           ┌────────▼──────┐           ┌──────▼──────┐
        │ PostgreSQL  │           │     Redis      │           │   AWS S3    │
        │  (primary)  │           │  (cache/queue) │           │  (files)    │
        └─────────────┘           └────┬───┬──────┘           └──────┬──────┘
                                        │   │                        │
                               ┌────────▼   ▼────────┐                │
                               │   Celery Worker     │                │
                               │  (async tasks)      │                │
                               │  - AI analysis      │                │
                               │  - Email sending    │                │
                               └────────┬─────────────┘                │
                                        │                              │
                               ┌────────▼────────────┐        ┌────────▼────────┐
                               │     AWS SES         │        │    AI API       │
                               │  (email delivery)   │        │  (external)     │
                               └─────────────────────┘        └─────────────────┘
```

---

## 2. Component Descriptions

### FastAPI Backend (`app/`)

Single Python/FastAPI application handles all HTTP traffic:
- **Tenant Middleware** — Resolves subdomain → tenant, skips admin domain
- **JWT Auth** — Stateless token auth with Redis blacklist revocation
- **Router Layer** — Module-separated endpoints
- **Service Layer** — Business logic orchestration
- **Repository Layer** — SQLAlchemy DB queries

### PostgreSQL

Primary data store. Schema versioned with Alembic (migrations not yet generated).

### Redis

Dual purpose:
1. **Token blacklist** — Keys: `blacklist:{token}`, TTL = remaining token lifetime
2. **Celery broker** — Queue for async tasks

### Celery Worker

Processes long-running tasks asynchronously:
- AI file analysis (calls external AI API)
- Email sending (AWS SES or tenant SMTP)

### AWS S3

Object storage for all files:
- Original uploads: `{tenant_id}/{user_id}/{submission_id}/{filename}`
- AI results: stored by AI API, key saved to `ai_s3_key`
- Expert edited results: `{tenant_id}/results/{submission_id}/{file_id}/{filename}`

### AWS SES

Default email sender. Tenant admins can override with custom SMTP via Settings.

---

## 3. Data Flow

### 3.1 User Submits Files

```
User → POST /submissions (with files)
  → service.upload()
    → repository.count_by_tenant()       [get next display_id]
    → repository.create_submission()    [save submission to DB]
    → S3 upload                         [TODO]
    → repository.create_file()         [save file records]
    → Celery: send_upload_confirmation  [TODO]
  → SubmissionResponse
```

### 3.2 Expert Triggers AI Analysis

```
Expert → POST /submissions/{id}/files/{file_id}/analyze
  → service.trigger_ai()
    → validate submission + file ownership
    → repository.create_analysis_job()  [create job record]
    → repository.update_file_ai_status() [set to running]
    → Celery: run_ai_analysis.delay()  [enqueue task]
  → {task_id}
```

### 3.3 Celery Worker Processes AI Task

```
Celery Worker → run_ai_analysis(submission_file_id, job_id)
  → S3 download (original file)         [TODO]
  → Call AI API                         [TODO]
  → S3 upload (result file)             [TODO]
  → Update submission_file.ai_s3_key   [TODO]
  → Update submission_file.ai_status = completed
  → Update analysis_job.status = success
```

### 3.4 Expert Publishes Result

```
Expert → POST /submissions/{id}/files/{file_id}/publish
  → service.publish()
    → validate result exists (expert_s3_key or ai_s3_key)
    → Generate presigned URL (7 days)   [TODO]
    → Celery: send_result_email         [TODO]
    → repository.publish_file()
      → submission_file.delivery_status = sent
      → submission_file.published_at = now
```

### 3.5 User Downloads Result

```
User → GET /submissions/my/{id}/files/{file_id}/result
  → service.get_result_url()
    → verify ownership + published
    → Generate presigned URL            [TODO]
  → {url: presigned_url}
```

---

## 4. Multi-Tenant Isolation

```
Request: Host = acme.chc.com

tenant_middleware:
  1. host = "acme.chc.com"
  2. subdomain = "acme"
  3. query: SELECT * FROM tenants WHERE subdomain='acme' AND is_active=true
  4. if not found → 404
  5. request.state.tenant_id = tenant.id

All subsequent DB queries use current_user.tenant_id:
  - service.get_tenant_submissions(db, current_user.tenant_id)
  - repository.get_files_by_submission(db, submission_id, tenant_id)
```

**Admin site** (`admin.chc.com`) bypasses tenant middleware. Super_admin operates system-wide; tenant_admin/expert operate within `current_user.tenant_id`.

---

## 5. Security Model

### Authentication
- JWT HS256 tokens, 24-hour expiry (`ACCESS_TOKEN_EXPIRE_MINUTES`)
- Token payload: `{"user_id": <id>, "exp": <expiry>}`
- Tokens blacklisted on logout in Redis with TTL = remaining lifetime

### Authorization
- Role-based via `require_roles(*roles)` dependency
- `tenant_id` scope enforced in all service/repository methods
- No trust of `tenant_id` from client — always derived from `current_user`

### File Security
- S3 keys are internal; never exposed to users
- User downloads via presigned URLs (7-day, auto-expiring)
- Expert/Admin download via backend proxy stream (no expiry)

### Secrets
- AWS credentials via environment variables
- Database password via environment variable
- `SECRET_KEY` must be changed from dev default in production

---

## 6. Deployment

```
docker compose up --build
```

**Containers:**
| Service | Description |
|---|---|
| `app` | FastAPI + Uvicorn |
| `worker` | Celery worker (consumes Redis queue) |
| `postgres` | PostgreSQL database |
| `redis` | Redis (broker + cache) |

**Restart policy:** `always` — all services restart on server boot.

---

## 7. Incomplete / Stub Components

| Component | Status | Location |
|---|---|---|
| S3 upload (user files) | TODO | `submissions/service.py:upload()` |
| S3 download (admin stream) | TODO | `submissions/service.py:download_file()` |
| Presigned URL generation | TODO | `submissions/service.py:get_result_url()` |
| AI API integration | TODO | `submissions/tasks.py:run_ai_analysis()` |
| Email sending (Celery) | TODO | `submissions/tasks.py` |
| Manual input endpoint | TODO | `submissions/router.py` |
| Tenant SMTP config | TODO | `settings/email-config` |
| Alembic migrations | TODO | `alembic/` |
