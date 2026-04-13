# BRD v8 Upgrade — Design Document

**Date:** 2026-04-13
**Scope:** Full implementation of BRD v8 changes
**Estimate:** ~10-15 dev days

---

## Decisions Log

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | Implementation scope | All-in, single batch | User preference — avoid partial states |
| 2 | Auth Backend↔Tool | Keep account auth, disable auto-rotate pwd | Simplest, no code change on backend |
| 3 | Upload flow | Presigned URL (3-step) | Scale-ready, offload file transfer from backend |
| 4 | User-facing status | Backend returns `user_facing_status` field | FE doesn't need internal logic |
| 5 | E-Tariff batch quota | Backend counts rows (openpyxl `max_row`) | Lightweight, keep quota logic in backend |
| 6 | SLA monitoring | Celery periodic task (hourly scan) | Need auto-email on breach |
| 7 | Rating trigger | Backend tracks `has_downloaded`, returns `show_rating_popup` | Cross-device accuracy |
| 8 | Expert CRUD permission | tenant_admin keeps full CRUD | BRD error — confirmed by user |
| 9 | Re-assignment | Overwrite expert, no history table | YAGNI — notify both experts |
| 10 | Tenant disable behavior | JSON error response, FE renders page | SPA architecture |
| 11 | Forgot password | Add `POST /auth/forgot-password` (public) | BRD v8 requirement, self-service |

---

## Prerequisites — Report Service (Tool)

### P1. Disable Auto-Rotate Password

Report Service có cơ chế tự đổi password định kỳ (`AUTH_TOKEN_VERSION=7`). Cần tắt để CHC Backend không bị mất kết nối.

**File:** `consulting-chc-tool-be/` — tìm và disable scheduled password rotation task/script.

### P2. Webhook Callback Support

Report Service cần hỗ trợ nhận `callback_url` trong request body và POST kết quả về khi task hoàn thành. Hiện đã có — verify vẫn hoạt động đúng.

### P3. Row Count in Response

Khi xử lý batch, Report Service nên trả `row_count` trong callback/poll response để Backend verify với số rows đã đếm.

---

## Phase 1: Database Schema Changes

### 1.1 Request Status Enum (5 → 7)

```python
class RequestStatus(str, enum.Enum):
    pending = "pending"                    # User vừa tạo
    ai_processing = "ai_processing"        # NEW — đang gọi Tool API
    pending_assignment = "pending_assignment"  # NEW — AI xong, chờ Admin assign
    processing = "processing"              # Admin đã assign Expert
    completed = "completed"                # Expert upload xong, chờ approve
    delivered = "delivered"                # Admin duyệt, gửi User
    cancelled = "cancelled"                # User huỷ
```

User-facing mapping (5 status):

| Internal | User-facing |
|----------|------------|
| pending | Chờ xử lý |
| ai_processing | Đang xử lý |
| pending_assignment | Đang xử lý |
| processing | Đang xử lý |
| completed | Hoàn thành |
| delivered | Đã giao |
| cancelled | Đã huỷ |

### 1.2 Request Model — New Fields

```python
# AI processing timestamps
ai_processing_started_at: DateTime | None
ai_completed_at: DateTime | None

# WP Draft (AI output, separate from expert result)
ai_draft_s3_key: str | None

# Approval audit trail
approved_by: int | None  # FK → users.id
approved_at: DateTime | None

# Internal note (when assigning)
internal_note: str | None

# Rating
has_downloaded: bool = False
has_rated: bool = False
rating: int | None          # 1-5
rating_comment: str | None
rated_at: DateTime | None
```

### 1.3 User Model — New Field

```python
result_email: str | None  # Email nhận kết quả CHC (onboarding)
```

### 1.4 Tenant Model — New Fields

```python
favicon_s3_key: str | None
footer_text: str | None
tagline: str | None
owner_name: str | None
owner_email: str | None
owner_phone: str | None
fallback_email_domain: str | None
```

### 1.5 New Table: `etariff_usage_logs`

```python
class ETariffUsageLog(Base):
    __tablename__ = "etariff_usage_logs"

    id: int (PK)
    user_id: int (FK → users.id)
    tenant_id: int (FK → tenants.id)
    request_id: int (FK → requests.id)
    mode: str  # "manual" | "batch"
    row_count: int  # 1 for manual, N for batch
    query_summary: str | None  # commodity_name or filename
    created_at: DateTime
```

---

## Phase 2: Presigned URL Upload Flow

### New Endpoints

```
POST /requests/presigned-url
  Body: { filename, file_size, request_type: "chc"|"etariff_batch", chc_modules?: [...] }
  → Create Request record (status: pending)
  → Generate S3 presigned PUT URL (expires 15min)
  → Response: { request_id, file_id, upload_url, expires_at }

POST /requests/{request_id}/confirm-upload
  → Download file from S3
  → Validate format (.xlsx, .xlsb)
  → Count rows (batch mode: check quota)
  → Start AI processing (status: pending → ai_processing)
  → Response: { request_id, status, row_count?, quota_remaining? }
```

### Flow

```
FE → POST /requests/presigned-url → { upload_url, request_id }
FE → PUT upload_url (file → S3 direct)
FE → POST /requests/{id}/confirm-upload → { status: "ai_processing" }
```

### E-Tariff Manual (unchanged)

Manual mode stays as JSON body — no file upload needed.

---

## Phase 3: Status Flow Changes

### Status Transitions

```
CHC:
  pending → ai_processing (confirm-upload triggers Tool)
  ai_processing → pending_assignment (Tool callback: WP Draft ready)
  pending_assignment → processing (Admin assigns Expert)
  processing → completed (Expert uploads WP Final)
  completed → delivered (Admin approves)
  any(pending..processing) → cancelled (User cancels)

E-Tariff:
  pending → ai_processing (confirm-upload or manual submit triggers Tool)
  ai_processing → delivered (Tool callback: auto-deliver)
  pending → cancelled (User cancels)
  ai_processing → cancelled (User cancels)
```

### Cancel Rules (v6.0)

- Allowed: `pending`, `ai_processing`, `pending_assignment`, `processing`
- NOT allowed: `completed`, `delivered`, `cancelled`

---

## Phase 4: New Endpoints

### Auth

```
POST /auth/forgot-password
  Body: { email }
  → Find user, generate reset token, send email
  → Always return 200 (no email enumeration)
```

### Requests — Rating

```
POST /requests/my/{request_id}/rate
  Body: { rating: 1-5, comment?: string }
  → Set has_rated, rating, rating_comment, rated_at

GET /requests/my/{request_id}/files/{file_id}/result
  → Existing endpoint, add: set has_downloaded = true on first call
  → Response: add show_rating_popup: true if has_downloaded && !has_rated
```

### Requests — Re-assignment

```
POST /requests/{request_id}/reassign
  Body: { expert_id }
  → Overwrite assigned_expert_id
  → Email notify old expert (removed) + new expert (assigned)
  → Only allowed when status = processing
```

### Dashboard — New Stats

```
GET /dashboard/etariff-usage?period=day|week|month
  → Bar chart data from etariff_usage_logs

GET /dashboard/satisfaction-score
  → Average rating, count rated

GET /dashboard/sla-overdue
  → Count requests in processing > 2 days, > 3 days
```

### Tenant — Disable Check

```
Middleware: if tenant.is_active == false
  → Return 403 { error: "tenant_disabled", owner_name, owner_email, owner_phone }
  → Block login for users in disabled tenant
```

---

## Phase 5: Email Templates (4 new)

| # | Template | Trigger |
|---|----------|---------|
| 1 | WP Draft Ready | AI completes WP Draft → notify Admin |
| 2 | SLA Warning | Request in processing > 2 days → Admin + Expert |
| 3 | SLA Breach | Request in processing > 3 days → Admin |
| 4 | Re-assignment | Expert changed → notify old + new expert |

---

## Phase 6: Logic Changes

### 6.1 File Format

- Accept: `.xlsx`, `.xlsb`
- Reject: `.xls` (removed)

### 6.2 Onboarding — New Field

Add `result_email` to OnboardingRequest schema.

### 6.3 Tenant Schema Updates

- TenantCreate: add `subdomain` (optional, auto-gen from tenant_code if empty)
- TenantCreate/Update: add `favicon`, `footer_text`, `tagline`, `owner_*` fields

### 6.4 Pricing Tier Display

Backend returns tier info per request:
- 1-2 modules = "Gói Cơ bản"
- 3-5 modules = "Gói Toàn diện"

Add `pricing_tier` field to RequestResponse for CHC requests.

### 6.5 SLA Periodic Task

```python
# Celery beat: every hour
@celery_app.task
def check_sla_compliance():
    # Find requests in processing > 48h → send warning email
    # Find requests in processing > 72h → send breach email
```

### 6.6 E-Tariff Batch Row Counting

At confirm-upload step:
1. Download file from S3
2. Open with openpyxl (read_only=True)
3. Count data rows (exclude header)
4. Check against tenant daily limit
5. Log to etariff_usage_logs
6. If rows > remaining: return warning with counts
7. Process min(rows, remaining)

---

## Migration Strategy

1. Alembic migration for all schema changes (single migration)
2. Existing requests keep old status values — no data migration needed (new statuses only for new requests)
3. New fields are all nullable — backward compatible
4. Deploy: migrate → restart → verify

---

## Files to Modify

| File | Changes |
|------|---------|
| `app/models/request.py` | Status enum, new fields, ETariffUsageLog model |
| `app/models/user.py` | Add result_email |
| `app/models/tenant.py` | Add favicon, footer, owner fields |
| `app/requests/router.py` | Presigned URL, confirm, rate, reassign endpoints |
| `app/requests/service.py` | New flows, cancel rules, quota logic, rating |
| `app/requests/schemas.py` | New schemas, user_facing_status |
| `app/auth/router.py` | forgot-password endpoint |
| `app/auth/service.py` | forgot_password logic |
| `app/core/report_client.py` | Update for new status handling |
| `app/core/email_service.py` | 4 new templates |
| `app/core/middleware.py` | Tenant disable check |
| `app/core/storage.py` | Presigned URL generation |
| `app/dashboard/router.py` | New stats endpoints |
| `app/dashboard/service.py` | ETariff usage, satisfaction, SLA queries |
| `app/dashboard/schemas.py` | New response schemas |
| `app/tenants/schemas.py` | New fields |
| `app/tenants/router.py` | Favicon upload |
| `app/users/schemas.py` | result_email in onboarding |
| `app/settings/router.py` | No change |
| `worker.py` | SLA periodic task registration |
| `alembic/versions/` | New migration |
