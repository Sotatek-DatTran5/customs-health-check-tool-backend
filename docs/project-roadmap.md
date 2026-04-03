# CHC Backend — Project Roadmap

> Created: 2026-04-02
> Based on: `miêu tả dự án.txt` (business specification)

---

## 1. Project Phases

### Phase 1 — Foundation ✅ Complete
**Goal:** Core multi-tenant backend with auth, tenant/user management, and basic submission flow.

| # | Task | Status | Notes |
|---|---|---|---|
| 1.1 | Project scaffolding (FastAPI, SQLAlchemy, Redis) | ✅ | Done |
| 1.2 | Tenant subdomain middleware | ✅ | Done |
| 1.3 | JWT auth + Redis blacklist | ✅ | Done |
| 1.4 | Tenant CRUD (super_admin) | ✅ | Done |
| 1.5 | User/expert CRUD (tenant_admin) | ✅ | Done |
| 1.6 | Submission upload (file API) | ✅ | Done |
| 1.7 | Celery worker setup | ✅ | Done |
| 1.8 | Dashboard stats endpoint | ✅ | Done |

### Phase 1.5 — Local Dev Infra ✅ Complete (2026-04-03)
**Goal:** Fake S3 (LocalStack) + fake SMTP (MailHog) for local dev without changing FE/BE interface.

| # | Task | Status | Notes |
|---|---|---|---|
| 1.5.1 | LocalStack + MailHog in docker-compose | ✅ | Done |
| 1.5.2 | `app/core/storage.py` (S3 client) | ✅ | LocalStack or real AWS via `AWS_ENDPOINT_URL` |
| 1.5.3 | `app/core/email.py` (SMTP client) | ✅ | MailHog or real SMTP via `SMTP_HOST` |
| 1.5.4 | `app/core/config.py` updated env vars | ✅ | `AWS_ENDPOINT_URL`, `S3_BUCKET_NAME`, SMTP fields |
| 1.5.5 | `.env.example` updated | ✅ | Dev defaults for LocalStack + MailHog |
| 1.5.6 | `scripts/setup-local.sh` bucket init | ✅ | `aws --endpoint-url` + health check |
| 1.5.7 | `app/submissions/service.py` wired | ✅ | All TODOs replaced with real storage/email calls |
| 1.5.8 | `app/submissions/tasks.py` wired | ✅ | `storage` imported; AI stub TODOs preserved for Phase 3 |

### Phase 2 — S3 & Email Integration ✅ Phase 1.5 Done
**Goal:** Local dev with LocalStack (S3) + MailHog (SMTP) — FE/BE interface unchanged.

| # | Task | Status | Notes |
|---|---|---|---|
| 2.1 | S3 client + LocalStack (dev) / real AWS (prod) | ✅ Done | `app/core/storage.py`; endpoint via `AWS_ENDPOINT_URL` |
| 2.2 | S3 presigned URL for user result download | ✅ Done | `storage.generate_presigned_url()`, 7-day expiry |
| 2.3 | S3 stream download for expert/admin | ✅ Done | `storage.download_file_stream()` → `StreamingResponse` |
| 2.4 | SMTP client + MailHog (dev) / real SMTP (prod) | ✅ Done | `app/core/email.py`; host via `SMTP_HOST` |
| 2.5 | Upload confirmation email | ✅ Done | `upload()` + `create_manual_submission()` call `email.send_email()` |
| 2.6 | Result published email | ✅ Done | `publish()` sends presigned URL to user |
| 2.7 | LocalStack bucket init script | ✅ Done | `scripts/setup-local.sh` |
| 2.8 | AWS SES (prod) | 🟡 Planned | Leave `SES_SENDER_EMAIL` empty → uses SMTP |
| 2.9 | Per-tenant SMTP override | 🟡 Planned | Settings → email-config (Schema TD-SET-005) |

### Phase 3 — AI Analysis Integration 🟡 Planned
**Goal:** Connect external AI API to Celery analysis pipeline.

| # | Task | Status | Notes |
|---|---|---|---|
| 3.1 | AI API client | 🟡 TODO | Configurable endpoint + API key |
| 3.2 | `run_ai_analysis` Celery task | 🟡 TODO | S3 download → AI call → S3 upload |
| 3.3 | Job status polling endpoint | 🟡 TODO | Expert checks AI progress |
| 3.4 | AI result file handling | 🟡 TODO | Save ai_s3_key on completion |
| 3.5 | Error handling + expert retry | 🟡 TODO | No auto-retry |

### Phase 4 — Manual Input & Extended User Flow 🟡 Planned
**Goal:** Full input modality coverage.

| # | Task | Status | Notes |
|---|---|---|---|
| 4.1 | `POST /submissions/manual` endpoint | 🟡 TODO | Create file from structured form |
| 4.2 | File generation from form data | 🟡 TODO | Convert structured input to Excel |
| 4.3 | Batch Dataset type submission | 🟡 TODO | Same flow as file_upload, type = batch_dataset |

### Phase 5 — Dashboard & Admin Polish 🟡 Planned
**Goal:** Complete admin site backend coverage.

| # | Task | Status | Notes |
|---|---|---|---|
| 5.1 | `GET /dashboard/recent-tenants` | 🟡 TODO | super_admin only |
| 5.2 | `GET /dashboard/recent-users` | 🟡 TODO | Role-scoped |
| 5.3 | `GET /dashboard/recent-submissions` | 🟡 TODO | Role-scoped |
| 5.4 | `GET /dashboard/role-distribution` | 🟡 TODO | Counts per role |
| 5.5 | Submission list filters | 🟡 TODO | date range, status filters |

### Phase 6 — Production Hardening 🟡 Planned
**Goal:** Production-ready deployment and observability.

| # | Task | Status | Notes |
|---|---|---|---|
| 6.1 | Alembic migrations setup | 🟡 TODO | |
| 6.2 | PostgreSQL advisory lock for display_id | 🟡 TODO | Avoid race condition on sequence |
| 6.3 | Password reset token hashing | 🟡 TODO | Currently plain text |
| 6.4 | `email_logs` table + logging | 🟡 TODO | Track delivery status |
| 6.5 | `system_config` table | 🟡 TODO | Dynamic configuration |
| 6.6 | Health check endpoint | 🟡 TODO | `/health` for load balancer |
| 6.7 | Rate limiting | 🟡 TODO | Upload, auth endpoints |
| 6.8 | CI/CD pipeline | 🟡 TODO | GitHub Actions |

---

## 2. Current Status Summary

| Category | Status |
|---|---|
| Auth (login/logout/reset/change) | ✅ Complete |
| Tenant management | ✅ Complete |
| User/expert management | ✅ Complete |
| Submission upload API | ✅ Complete |
| AI trigger API | ✅ Complete (task stub) |
| Celery worker setup | ✅ Complete |
| Dashboard stats | ✅ Complete |
| S3 file storage | ✅ Complete (LocalStack dev / AWS prod) |
| Presigned URL generation | ✅ Complete |
| SMTP email (dev) | ✅ Complete (MailHog) |
| Upload confirmation email | ✅ Complete |
| Result published email | ✅ Complete |
| Manual input endpoint | ✅ Complete |
| AWS SES (prod) | 🟡 Planned |
| Per-tenant SMTP | 🟡 Planned |
| AI API integration | 🟡 Planned |
| Alembic migrations | 🟡 Planned |
| Recent dashboard endpoints | 🟡 Planned |

---

## 3. Milestones

| Milestone | Contents | Target |
|---|---|---|
| **M1: Alpha** | Phases 1–2; basic upload → expert → user flow working end-to-end | TBD |
| **M2: Beta** | Phase 3; AI analysis integrated | TBD |
| **M3: Feature Complete** | Phases 4–5; all endpoints implemented | TBD |
| **M4: Production** | Phase 6; migrations, hardening, CI/CD | TBD |

---

## 4. Known Risks & Open Questions

| ID | Question | Impact | Owner |
|---|---|---|---|
| Q1 | Will the AI API handle `.xlsx` and `.xls` files directly, or need pre-processing? | Affects `tasks.py` design | Backend |
| Q2 | What is the max file size expected? Is there a practical limit? | S3 + backend memory | Backend |
| Q3 | Should presigned URLs be generated once on publish and cached, or on-demand per request? | Performance + complexity | Backend |
| Q4 | Do we need sub-user roles within `expert` (e.g., reviewer vs. analyst)? | Permissions scope | Product |
| Q5 | Should `super_admin` have a tenant-scoped view, or always system-wide? | Dashboard design | Product |
| Q6 | Is the current Celery broker (Redis) sufficient, or will this need RabbitMQ for reliability at scale? | Deployment config | DevOps |

---

## 5. Dependency Map

```
Phase 1 (Foundation)
  └── Phase 2 (S3 + Email)
        └── Phase 3 (AI Analysis)
              └── Phase 4 (Manual Input)     ← independent of 2+3
                    └── Phase 5 (Dashboard)
                          └── Phase 6 (Hardening)
```

Phase 4 (Manual Input) can be developed in parallel with Phases 2–3 since it shares endpoints but not implementation details.
