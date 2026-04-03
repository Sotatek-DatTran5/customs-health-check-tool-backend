# CHC Backend — Project Overview (PDR)

**Customs Health Check Backend** — FastAPI multi-tenant backend for E-Customs Health Check processing.

> Created: 2026-04-02

---

## 1. Business Context

CHC Backend is the server-side component of a customs/health-check document processing platform. Organizations (tenants) onboard to the platform, and their end-users submit Excel-based customs declarations. Experts within each organization review and process submissions with AI assistance, then deliver annotated results back to users.

**Core value proposition:**
- Reduce manual review time via AI analysis
- Centralized multi-tenant management
- Secure, auditable document processing pipeline
- Automated result delivery via email with secure download links

---

## 2. Actors & Permissions

| Actor | Scope | Responsibilities |
|---|---|---|
| `super_admin` | System-wide | Manage tenants and tenant_admins |
| `tenant_admin` | Per-tenant | Manage users/experts within tenant; full CHC access |
| `expert` | Per-tenant | Process files, review AI results, publish to users |
| `user` | Per-tenant | Submit files, receive results |

### Admin Site Page Access (by Role)

| Page | super_admin | tenant_admin | expert |
|---|---|---|---|
| Dashboard | ✓ | ✓ | ✓ |
| Tenants | ✓ | — | — |
| Users | — | ✓ | — |
| CHC Health Check | — | ✓ | ✓ |
| Settings | ✓ | ✓ | ✓ |

---

## 3. Modules

### 3.1 E-Customs Health Check (File Upload)

Users upload one or more Excel files (`.xlsx`, `.xls`) per submission. Files are validated by extension and MIME type. No file size limit is enforced server-side yet.

**Flow:**
1. User selects files → `POST /submissions` (type = `file_upload`)
2. System generates display_id: `{TENANT_CODE}-{nnn}` (e.g., `ACME-001`)
3. Files stored to S3: `{tenant_id}/{user_id}/{submission_id}/{filename}`
4. Upload confirmation email sent to user (async)
5. Submission appears in expert's queue

### 3.2 Batch Dataset

Same as E-Customs Health Check but allows higher-volume batch uploads. Uses the same `/submissions` endpoint with `type = batch_dataset`.

### 3.3 Manual Input

Users fill a structured form instead of uploading a file. System generates a file from the input and submits it as a `manual_input` type submission.

**Fields:** commodity_name, description, function, structure_components, material_composition, technical_specification, additional_notes (optional)

**Endpoint:** `POST /submissions/manual` *(not yet implemented)*

### 3.4 Admin Site

Reachable at `admin.{BASE_DOMAIN}`. Provides:
- **Dashboard** — Aggregated stats (role-dependent data scope)
- **Tenants** — CRUD for super_admin
- **Users** — CRUD for tenant_admin
- **CHC Health Check** — File processing workflow
- **Settings** — Profile, password change, email config

---

## 4. Business Flow (End-to-End)

```
User                     Expert/Admin              Celery Worker
  │                            │                         │
  │── POST /submissions ────────►│                         │
  │                            │── S3 upload ─────────────►│
  │                            │── Email confirm ──────────►│
  │◄── 202 Accepted ───────────│                         │
  │                            │── GET /submissions ──────►│
  │                            │◄── list ─────────────────│
  │                            │── POST /files/{id}/analyze►
  │                            │◄── {task_id} ────────────│
  │                            │                    ┌──────┴──────┐
  │                            │                    │ S3 download │
  │                            │                    │ AI API call │
  │                            │                    │ S3 upload   │
  │                            │                    │ Update DB   │
  │                            │                    └─────────────┘
  │                            │── PUT /files/{id}/result  │
  │                            │── POST /files/{id}/publish│
  │◄── Email (presigned URL) ───│                         │
```

**AI Analysis:**
- Triggered per file (not per submission)
- Runs asynchronously via Celery
- No automatic retry on failure — expert re-triggers manually
- Typical duration: 7–15 minutes

**Result Publishing:**
- Expert edits result or accepts AI output
- System generates presigned S3 URL (7-day validity)
- Email sent to user with download link
- File `delivery_status` updated to `sent`

---

## 5. File Access Model

| Actor | Access Method | Expiry |
|---|---|---|
| Expert/Admin | Backend proxy stream from S3 | No expiry (on-demand) |
| User (result) | Presigned URL in email | 7 days |

---

## 6. Email Triggers

All emails are sent asynchronously (Celery tasks). Plain text format.

| Trigger | Condition | Recipient |
|---|---|---|
| Upload confirmation | User successfully submits | User |
| Result available | Expert publishes result | User |
| Reset password | Admin requests reset | Target user/expert |
| Account created | Admin creates user/expert | New user/expert |

**Email provider:** AWS SES by default. Tenant can override with custom SMTP in Settings.

---

## 7. Data Scope by Role

### super_admin
- All tenants, all users, all submissions system-wide
- Dashboard: total tenants, active tenants, system-wide user/CHC counts

### tenant_admin
- All users/experts within own tenant
- All submissions within own tenant
- Dashboard: tenant-scoped user counts, submission breakdown

### expert
- Submissions within own tenant (created by any user)
- Dashboard: tenant-scoped submission counts and statuses

### user
- Own submissions only
- No dashboard access

---

## 8. Multi-Tenancy Model

**DNS:** Wildcard `*.chc.com` → single backend server

**Middleware flow:**
1. Read `Host` header
2. If `Host == ADMIN_DOMAIN` → skip tenant middleware (admin site)
3. Else → extract subdomain (e.g., `acme` from `acme.chc.com`)
4. Query `tenants` table for matching active subdomain
5. Inject `tenant_id` into `request.state`
6. All DB queries scoped by `tenant_id`

**Tenant isolation:** All submission/user queries include `tenant_id` filter.

---

## 9. Database Schema Summary

| Table | Purpose |
|---|---|
| `tenants` | Tenant orgs with subdomain |
| `users` | Users/experts with role and tenant FK |
| `password_reset_tokens` | Password reset tokens (plain text, hashed soon) |
| `submissions` | Submission header (type, display_id, timestamps) |
| `submission_files` | Individual files with AI/delivery status |
| `analysis_jobs` | Celery job tracking per file |

*Planned: `tenant_email_config`, `email_logs`, `system_config`*

---

## 10. Key Technical Decisions

| Decision | Rationale |
|---|---|
| Wildcard DNS + middleware | Single deploy, zero per-tenant infrastructure |
| JWT + Redis blacklist | Stateless auth with instant revocation on logout |
| Celery for AI + email | Non-blocking I/O, retry-safe jobs |
| S3 presigned URLs | No backend involvement in large file downloads |
| Soft delete on Tenant/User | Audit trail, data recovery |
| Per-file AI, not per-submission | Granular retry, parallel processing |
| Advisory lock for display_id | Avoid race conditions on sequential IDs |
