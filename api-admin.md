# CHC Backend — Admin Portal API Documentation

> Tai lieu API chi tiet danh cho FE team tich hop **Admin Portal** (trang quan tri).
> Bao gom ca cac API server-to-server (webhook).
> BRD v8 — Last updated: 2026-04-13

---

## Muc luc

1. [Thong tin chung](#1-thong-tin-chung)
2. [Role & Permission](#2-role--permission)
3. [Request Management](#3-request-management)
4. [User Management](#4-user-management)
5. [Admin Management (Super Admin)](#5-admin-management-super-admin)
6. [Tenant Management (Super Admin)](#6-tenant-management-super-admin)
7. [Expert Management](#7-expert-management)
8. [Dashboard](#8-dashboard)
9. [Settings](#9-settings)
10. [Webhook — Server-to-Server](#10-webhook--server-to-server)
11. [Health Check](#11-health-check)
12. [Error Handling](#12-error-handling)

---

## 1. Thong tin chung

### Base URL

```
Development:  http://localhost:8329
Production:   https://admin.chc-service.click
```

### Authentication

Giong User Portal — tat ca API yeu cau JWT Bearer token:

```
Authorization: Bearer <access_token>
```

Xem chi tiet login/refresh/logout/forgot-password trong [api-user.md](./api-user.md#2-authentication).

---

## 2. Role & Permission

### Ma tran quyen

| Endpoint | super_admin | tenant_admin | expert |
|----------|:-----------:|:------------:|:------:|
| **Requests** — List/Detail | All | Tenant | Assigned |
| **Requests** — Assign expert | Yes | Yes | No |
| **Requests** — Reassign expert (v8) | Yes | Yes | No |
| **Requests** — Upload result | No | No | Yes |
| **Requests** — Approve/Deliver | Yes | Yes | No |
| **Users** — CRUD | Yes | Tenant | No |
| **Admins** — CRUD | Yes | No | No |
| **Tenants** — CRUD | Yes | No | No |
| **Experts** — CRUD | Yes | Yes | No |
| **Dashboard** — Stats | All | Tenant | No |
| **Dashboard** — E-Tariff Usage (v8) | All | Tenant | No |
| **Dashboard** — Satisfaction (v8) | All | Tenant | No |
| **Dashboard** — SLA Overdue (v8) | All | Tenant | No |
| **Settings** — Email config | No | Yes | No |

---

## 3. Request Management

### 3.1. GET `/requests`

Danh sach request. Ket qua tuy theo role:
- **super_admin**: Tat ca request cross-tenant
- **tenant_admin**: Request trong tenant minh
- **expert**: Chi request duoc assign cho minh

**Query Parameters:**

| Param | Type | Vi du |
|-------|------|-------|
| `status` | string | `pending_assignment` |
| `type` | string | `chc` |
| `search` | string | `ACME` |
| `expert_id` | int | `5` |

**Response `200`:** `RequestResponse[]`

---

### 3.2. GET `/requests/{request_id}`

Chi tiet request. Permission check theo role.

**Response `200`:** [RequestResponse](#request-response)

---

### 3.3. GET `/requests/{request_id}/files/{file_id}/download`

Download file goc (ECUS upload). Tra ve streaming response.

---

### 3.4. POST `/requests/{request_id}/assign`

Admin assign expert cho request.

**Roles:** `super_admin`, `tenant_admin`

**Cho phep khi status:** `pending`, `pending_assignment` (BRD v8)

**Request Body:**

```json
{
  "expert_id": 5
}
```

**Side effects:**
- Status -> `processing`
- Email thong bao gui cho Expert

**Error:**
- `404` — Request khong ton tai
- `400` — Request khong o trang thai cho phep

---

### 3.5. POST `/requests/{request_id}/reassign` (BRD v8)

Admin chuyen doi Expert khi request dang processing.

**Roles:** `super_admin`, `tenant_admin`

**Cho phep khi status:** `processing`

**Request Body:**

```json
{
  "expert_id": 8,
  "reason": "Expert cu ban, chuyen cho nguoi khac"
}
```

| Field | Type | Required | Ghi chu |
|-------|------|----------|---------|
| `expert_id` | int | Yes | ID expert moi |
| `reason` | string | No | Ly do chuyen (luu vao internal_note) |

**Response `200`:** [RequestResponse](#request-response)

**Side effects:**
- Expert cu nhan email "ban da duoc go khoi don X"
- Expert moi nhan email "ban duoc chuyen giao don X"

**Error:**
- `400` — Khong o trang thai `processing` hoac expert trung

---

### 3.6. POST `/requests/{request_id}/files/{file_id}/upload-result`

Expert upload ket qua phan tich. Status chuyen -> `completed`.

**Roles:** `expert` only

**Content-Type:** `multipart/form-data`

| Field | Type | Required |
|-------|------|----------|
| `excel_file` | File | No |
| `pdf_file` | File | No |
| `notes` | string | No |

**It nhat 1 file phai co.**

**Response `200`:** [RequestResponse](#request-response)

---

### 3.7. POST `/requests/{request_id}/approve`

Admin duyet ket qua -> giao cho user. Status: `completed -> delivered`.

**Roles:** `super_admin`, `tenant_admin`

**Request Body (optional):** `{ "notes": "Da xac nhan ket qua chinh xac" }`

**Response `200`:** [RequestResponse](#request-response)

**Side effects:**
- Status -> `delivered`
- Luu `approved_by` + `approved_at` (BRD v8)
- Email thong bao gui cho User

---

## 4. User Management

### 4.1. GET `/users`

Danh sach user trong tenant.

**Roles:** `super_admin` (all), `tenant_admin` (tenant)

**Response `200`:** `UserResponse[]`

---

### 4.2. POST `/users`

Tao user moi trong tenant.

**Request Body:**

```json
{
  "email": "newuser@abc.com",
  "full_name": "Tran Thi B",
  "password": null,
  "role": "user"
}
```

Neu `password = null` -> backend auto-gen va gui email.

---

### 4.3. PUT `/users/{user_id}`

Cap nhat thong tin user. Chi gui field can update.

---

### 4.4. DELETE `/users/{user_id}`

Vo hieu hoa user (soft delete).

---

### 4.5. POST `/users/{user_id}/reset-password`

Admin gui email reset password cho user.

---

## 5. Admin Management (Super Admin)

### 5.1. GET `/users/admins/{tenant_id}`

Danh sach admin cua mot tenant. Super admin only.

### 5.2. POST `/users/admins`

Tao admin cho tenant. Super admin only.

```json
{
  "email": "admin@tenant.com",
  "full_name": "Admin Nguyen",
  "tenant_id": 1
}
```

---

## 6. Tenant Management (Super Admin)

### 6.1. GET `/tenants`

Danh sach tat ca tenant.

**Response `200`:** `TenantResponse[]`

---

### 6.2. POST `/tenants`

Tao tenant moi + tu dong tao admin.

**Request Body:**

```json
{
  "name": "BETA Corp",
  "tenant_code": "BETA",
  "subdomain": "beta",
  "description": "Cong ty BETA",
  "is_active": true,
  "admin_email": "admin@beta.com",
  "admin_full_name": "Admin Beta",
  "primary_color": "#059669",
  "display_name": "BETA",
  "footer_text": "BETA Corp - All rights reserved",
  "tagline": "Giai phap xuat nhap khau",
  "owner_name": "Nguyen Van A",
  "owner_email": "owner@beta.com",
  "owner_phone": "0912345678",
  "etariff_daily_limit": 20
}
```

| Field | Type | Required | Ghi chu |
|-------|------|----------|---------|
| `name` | string | Yes | Ten tenant |
| `tenant_code` | string | Yes | Ma tenant (unique) |
| `subdomain` | string | No | **BRD v8**: Auto-gen tu tenant_code neu bo trong |
| `description` | string | No | Mo ta |
| `is_active` | boolean | No | Mac dinh `true` |
| `admin_email` | email | Yes | Email admin dau tien |
| `admin_full_name` | string | Yes | Ten admin |
| `primary_color` | string | No | Ma mau branding (hex) |
| `display_name` | string | No | Ten hien thi |
| `footer_text` | string | No | **BRD v8**: Text footer |
| `tagline` | string | No | **BRD v8**: Tagline |
| `owner_name` | string | No | **BRD v8**: Ten chu so huu (hien khi tenant disabled) |
| `owner_email` | string | No | **BRD v8**: Email chu so huu |
| `owner_phone` | string | No | **BRD v8**: SĐT chu so huu |
| `etariff_daily_limit` | int | No | Mac dinh `10` |

---

### 6.3. GET `/tenants/{tenant_id}`

Chi tiet tenant.

---

### 6.4. PUT `/tenants/{tenant_id}`

Cap nhat tenant. Chi gui field can update.

**Cac field moi BRD v8:** `fallback_email_domain`, `footer_text`, `tagline`, `owner_name`, `owner_email`, `owner_phone`

---

### 6.5. DELETE `/tenants/{tenant_id}`

Vo hieu hoa tenant (soft delete). Khi tenant disabled, user truy cap subdomain se thay trang lien he chu so huu (xem [api-user.md#tenant-disabled](./api-user.md#tenant-disabled)).

---

### 6.6. POST `/tenants/{tenant_id}/logo`

Upload logo cho tenant.

---

## 7. Expert Management

### 7.1. GET `/tenants/experts/all`

Danh sach tat ca expert (cross-tenant).

### 7.2. POST `/tenants/experts`

Tao expert moi.

```json
{
  "email": "expert2@chc.com",
  "full_name": "Chuyen gia Le"
}
```

---

## 8. Dashboard

### 8.1. GET `/dashboard/stats`

Thong ke tong quan.

**Response `200`:**

```json
{
  "total_users": 150,
  "total_requests": 500,
  "requests_pending": 20,
  "requests_ai_processing": 5,
  "requests_pending_assignment": 8,
  "requests_processing": 35,
  "requests_completed": 100,
  "requests_delivered": 330,
  "requests_cancelled": 15,
  "total_tenants": 10,
  "active_tenants": 8,
  "requests_today": 12,
  "requests_this_week": 45,
  "requests_this_month": 150
}
```

**BRD v8 moi:** `requests_ai_processing`, `requests_pending_assignment`

---

### 8.2. GET `/dashboard/recent-tenants`

Super Admin only. `?limit=10`

### 8.3. GET `/dashboard/recent-users`

`?limit=10`

### 8.4. GET `/dashboard/recent-requests`

`?limit=10`

### 8.5. GET `/dashboard/role-distribution`

---

### 8.6. GET `/dashboard/etariff-usage` (BRD v8)

Bieu do E-Tariff usage theo ngay/tuan/thang.

**Query:** `?period=day` (day | week | month)

**Response `200`:**

```json
[
  { "period": "2026-04-10", "row_count": 150, "request_count": 3 },
  { "period": "2026-04-11", "row_count": 200, "request_count": 5 },
  { "period": "2026-04-12", "row_count": 0, "request_count": 0 }
]
```

| period format | Khi |
|--------------|------|
| `2026-04-13` | day |
| `2026-W15` | week |
| `2026-04` | month |

---

### 8.7. GET `/dashboard/satisfaction-score` (BRD v8)

Diem hai long trung binh + breakdown.

**Response `200`:**

```json
{
  "average_rating": 4.2,
  "total_rated": 45,
  "rating_breakdown": {
    "1": 1,
    "2": 2,
    "3": 5,
    "4": 15,
    "5": 22
  }
}
```

---

### 8.8. GET `/dashboard/sla-overdue` (BRD v8)

So request vuot SLA (dang processing qua lau).

**Response `200`:**

```json
{
  "warning_count": 3,
  "breach_count": 1
}
```

| Field | Mo ta |
|-------|-------|
| `warning_count` | Processing > 48h (canh bao) |
| `breach_count` | Processing > 72h (vi pham) |

**Luu y:** Backend co Celery beat task chay moi gio, tu gui email canh bao cho admin + expert khi vuot SLA.

---

## 9. Settings

### 9.1. GET `/settings/email-config`

Lay cau hinh SMTP email cua tenant. `tenant_admin` only.

### 9.2. PUT `/settings/email-config`

Cap nhat cau hinh SMTP email.

---

## 10. Webhook — Server-to-Server

### POST `/requests/webhook/ai-result`

Report Service goi khi AI task hoan thanh. Khong dung JWT, dung webhook secret.

**Headers:** `X-Webhook-Secret: <webhook_secret>`

**Request Body:**

```json
{
  "task_id": "task-abc-123",
  "status": "SUCCESS",
  "result": {
    "object_name": "results/task-abc-123/output.xlsx",
    "hs_code": "1101.00.10"
  },
  "error": null
}
```

**BRD v8 — Status transitions khi AI xong:**
- **CHC**: `ai_processing -> pending_assignment` (WP Draft ready, Admin can assign Expert)
- **E-Tariff**: `ai_processing -> delivered` (auto-deliver, khong can admin approve)

**Side effects:**
- CHC: GUI email "WP Draft Ready" cho admin
- E-Tariff: Gui email "Ket qua da san sang" cho user

---

## 11. Health Check

### GET `/health`

Kiem tra backend con song. Khong can auth.

**Response `200`:** `{ "status": "ok" }`

---

## 12. Error Handling

| Code | Y nghia |
|------|---------|
| `200` | Thanh cong |
| `400` | Logic khong hop le |
| `401` | Token het han/invalid |
| `403` | Khong du quyen, tenant disabled |
| `404` | Resource khong ton tai |
| `422` | Validation error |
| `429` | Vuot E-Tariff daily limit |
| `503` | Report Service dang down |

---

## Schema Reference

### <a id="request-response"></a>RequestResponse

```typescript
interface RequestResponse {
  id: number;
  display_id: string;
  type: "chc" | "etariff_manual" | "etariff_batch";
  status: string;              // 7 internal statuses
  user_facing_status: string;  // 5 mapped statuses
  chc_modules: string[] | null;
  assigned_expert_id: number | null;
  assigned_expert_name: string | null;
  submitted_at: string;
  completed_at: string | null;
  delivered_at: string | null;
  cancelled_at: string | null;
  admin_notes: string | null;
  has_downloaded: boolean;
  has_rated: boolean;
  rating: number | null;       // 1-5
  pricing_tier: string | null; // "Goi Co ban" | "Goi Toan dien" (CHC only)
  files: RequestFileResponse[];
  user_name: string | null;
  user_email: string | null;
}
```

### <a id="user-response"></a>UserResponse

```typescript
interface UserResponse {
  id: number;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  is_first_login: boolean;
  locale: string;
  company_name: string | null;
  tax_code: string | null;
  phone: string | null;
  result_email: string | null; // BRD v8
  last_login_at: string | null;
  tenant_id: number | null;
  created_at: string | null;
}
```

### <a id="tenant-response"></a>TenantResponse

```typescript
interface TenantResponse {
  id: number;
  name: string;
  tenant_code: string;
  subdomain: string;
  description: string | null;
  is_active: boolean;
  logo_s3_key: string | null;
  favicon_s3_key: string | null;    // BRD v8
  primary_color: string | null;
  display_name: string | null;
  custom_email_domain: string | null;
  fallback_email_domain: string | null; // BRD v8
  footer_text: string | null;       // BRD v8
  tagline: string | null;           // BRD v8
  owner_name: string | null;        // BRD v8
  owner_email: string | null;       // BRD v8
  owner_phone: string | null;       // BRD v8
  etariff_daily_limit: number;
  created_at: string;
}
```

---

## Luong tich hop cho FE Admin

### 1. Request Lifecycle (BRD v8)

```
User tao don (presigned URL hoac direct upload)
  -> status: pending -> ai_processing (tu dong)

AI hoan thanh:
  - CHC: ai_processing -> pending_assignment
    -> Admin thay trong list, assign Expert
  - E-Tariff: ai_processing -> delivered (tu dong)

Admin assign expert
  -> POST /requests/{id}/assign
  -> status: pending_assignment -> processing
  -> Expert nhan email

(Optional) Admin doi expert
  -> POST /requests/{id}/reassign
  -> Email thong bao ca 2 expert

Expert xu ly + upload ket qua
  -> POST /requests/{id}/files/{fid}/upload-result
  -> status: processing -> completed

Admin review + approve
  -> POST /requests/{id}/approve
  -> status: completed -> delivered
  -> User nhan email
```

### 2. Dashboard data loading (BRD v8)

```javascript
const [stats, recentRequests, etariffUsage, satisfaction, sla] =
  await Promise.all([
    api.get('/dashboard/stats'),
    api.get('/dashboard/recent-requests?limit=10'),
    api.get('/dashboard/etariff-usage?period=day'),
    api.get('/dashboard/satisfaction-score'),
    api.get('/dashboard/sla-overdue'),
  ]);

// Hien thi SLA alert neu co breach
if (sla.data.breach_count > 0) {
  showAlert(`${sla.data.breach_count} don vi pham SLA (>72h)`);
}
```

### 3. Tao tenant voi owner info (BRD v8)

```javascript
await api.post('/tenants', {
  name: 'ACME Corp',
  tenant_code: 'ACME',
  admin_email: 'admin@acme.com',
  admin_full_name: 'Admin ACME',
  // BRD v8 fields
  owner_name: 'Nguyen Van A',
  owner_email: 'owner@acme.com',
  owner_phone: '0912345678',
  footer_text: 'ACME Corp - Since 2020',
  tagline: 'Giai phap XNK hang dau',
});
```
