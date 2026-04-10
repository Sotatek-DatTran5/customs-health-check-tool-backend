# CHC Backend — Admin Portal API Documentation

> Tài liệu API chi tiết dành cho FE team tích hợp **Admin Portal** (trang quản trị).
> Bao gồm cả các API server-to-server (webhook).

---

## Mục lục

1. [Thông tin chung](#1-thông-tin-chung)
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

## 1. Thông tin chung

### Base URL

```
Development:  http://localhost:8329
Production:   https://admin.chc.com
```

### Authentication

Giống User Portal — tất cả API yêu cầu JWT Bearer token:

```
Authorization: Bearer <access_token>
```

Xem chi tiết login/refresh/logout trong [api-user.md](./api-user.md#2-authentication).

### Admin Roles

Admin Portal phục vụ 3 role:

| Role | Quyền |
|------|-------|
| `super_admin` | Quản lý **tất cả** tenant, user, admin, request |
| `tenant_admin` | Quản lý user, request **trong tenant mình** |
| `expert` | Xem/xử lý request **được assign** |

---

## 2. Role & Permission

### Ma trận quyền

| Endpoint | super_admin | tenant_admin | expert |
|----------|:-----------:|:------------:|:------:|
| **Requests** — List/Detail | ✅ (all) | ✅ (tenant) | ✅ (assigned) |
| **Requests** — Assign expert | ✅ | ✅ | ❌ |
| **Requests** — Upload result | ❌ | ❌ | ✅ |
| **Requests** — Approve/Deliver | ✅ | ✅ | ❌ |
| **Users** — CRUD | ✅ | ✅ (tenant) | ❌ |
| **Admins** — CRUD | ✅ | ❌ | ❌ |
| **Tenants** — CRUD | ✅ | ❌ | ❌ |
| **Experts** — CRUD | ✅ | ✅ | ❌ |
| **Dashboard** — Stats | ✅ (all) | ✅ (tenant) | ❌ |
| **Dashboard** — Recent | ✅ (all) | ✅ (tenant) | ❌ |
| **Settings** — Email config | ❌ | ✅ | ❌ |

---

## 3. Request Management

### 3.1. GET `/requests`

**BRD F-A03**: Danh sách request. Kết quả tuỳ theo role:
- **super_admin**: Tất cả request cross-tenant
- **tenant_admin**: Request trong tenant mình
- **expert**: Chỉ request được assign cho mình

**Query Parameters (tất cả optional):**

| Param | Type | Ví dụ | Ghi chú |
|-------|------|-------|---------|
| `status` | string | `pending` | Filter trạng thái |
| `type` | string | `chc` | Filter loại đơn |
| `search` | string | `ACME` | Tìm theo display_id, user name |
| `expert_id` | int | `5` | Filter theo expert (admin only) |

**Response `200`:** `RequestResponse[]`

```json
[
  {
    "id": 1,
    "display_id": "ACME-001",
    "type": "chc",
    "status": "pending",
    "chc_modules": ["tariff_classification"],
    "assigned_expert_id": null,
    "assigned_expert_name": null,
    "submitted_at": "2025-01-15T10:30:00Z",
    "completed_at": null,
    "delivered_at": null,
    "cancelled_at": null,
    "admin_notes": null,
    "files": [...],
    "user_name": "Nguyễn Văn A",
    "user_email": "user@abc.com"
  }
]
```

---

### 3.2. GET `/requests/{request_id}`

Chi tiết request. Permission check theo role (xem ma trận ở trên).

**Response `200`:** [RequestResponse](#request-response)

---

### 3.3. GET `/requests/{request_id}/files/{file_id}/download`

Download file gốc (ECUS upload) hoặc kết quả.

**Response `200`:**

```json
{
  "download_url": "https://s3.amazonaws.com/...",
  "filename": "ECUS_2025.xlsx"
}
```

---

### 3.4. POST `/requests/{request_id}/assign`

**BRD F-A03**: Admin assign expert cho request. Status chuyển `pending → processing`.

**Roles:** `super_admin`, `tenant_admin`

**Request Body:**

```json
{
  "expert_id": 5
}
```

**Response `200`:**

```json
{
  "message": "Expert assigned",
  "request_id": 1,
  "expert_id": 5
}
```

**Side effects:**
- Request status → `processing`
- Email thông báo gửi cho Expert

**Error:**
- `404` — Request không tồn tại
- `400` — Request đã có expert hoặc đã cancelled

---

### 3.5. POST `/requests/{request_id}/files/{file_id}/upload-result`

**BRD F-A03**: Expert upload kết quả phân tích. Status chuyển → `completed`.

**Roles:** `expert` only

**Content-Type:** `multipart/form-data`

**Form fields:**

| Field | Type | Required | Ghi chú |
|-------|------|----------|---------|
| `excel_file` | File | ❌ | File Excel kết quả |
| `pdf_file` | File | ❌ | File PDF báo cáo |
| `notes` | string | ❌ | Ghi chú của expert |

**Lưu ý:** Ít nhất 1 trong `excel_file` hoặc `pdf_file` phải có.

**Ví dụ JavaScript:**

```javascript
const formData = new FormData();
formData.append('excel_file', excelFile);
formData.append('pdf_file', pdfFile);
formData.append('notes', 'Đã phân loại xong, HS code chính xác');

const res = await fetch(`/requests/${requestId}/files/${fileId}/upload-result`, {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${token}` },
  body: formData,
});
```

**Response `200`:** [RequestResponse](#request-response) (status = `completed`)

---

### 3.6. POST `/requests/{request_id}/approve`

**BRD F-A03**: Admin duyệt kết quả → giao cho user. Status chuyển `completed → delivered`.

**Roles:** `super_admin`, `tenant_admin`

**Request Body (optional):**

```json
{
  "notes": "Đã xác nhận kết quả chính xác"
}
```

**Response `200`:** [RequestResponse](#request-response) (status = `delivered`)

**Side effects:**
- Request status → `delivered`
- Email thông báo gửi cho User ("Kết quả đã sẵn sàng")

---

## 4. User Management

### 4.1. GET `/users`

**BRD F-A04**: Danh sách user trong tenant.

**Roles:** `super_admin`, `tenant_admin`

- `super_admin`: Xem all users
- `tenant_admin`: Chỉ xem user trong tenant mình

**Response `200`:** `UserResponse[]`

```json
[
  {
    "id": 1,
    "email": "user@abc.com",
    "full_name": "Nguyễn Văn A",
    "role": "user",
    "is_active": true,
    "is_first_login": false,
    "locale": "vi",
    "company_name": "Công ty TNHH ABC",
    "tax_code": "0123456789",
    "phone": "0912345678",
    "last_login_at": "2025-01-15T08:00:00Z",
    "tenant_id": 1,
    "created_at": "2025-01-01T00:00:00Z"
  }
]
```

---

### 4.2. POST `/users`

**BRD F-A04**: Tạo user mới trong tenant.

**Roles:** `super_admin`, `tenant_admin`

**Request Body:**

```json
{
  "email": "newuser@abc.com",
  "full_name": "Trần Thị B",
  "password": null,
  "role": "user"
}
```

| Field | Type | Required | Ghi chú |
|-------|------|----------|---------|
| `email` | email | ✅ | Email đăng nhập |
| `full_name` | string | ✅ | Họ tên |
| `password` | string | ❌ | Nếu `null` → auto-gen password, gửi email |
| `role` | string | ❌ | Mặc định `user`. Giá trị: `user` |

**Response `201`:** [UserResponse](#user-response)

**Side effects:**
- Nếu không set password → backend tự tạo random password và gửi email cho user mới.

---

### 4.3. PUT `/users/{user_id}`

Cập nhật thông tin user.

**Request Body (chỉ gửi field cần update):**

```json
{
  "full_name": "Nguyễn Văn C",
  "is_active": false,
  "phone": "0999888777",
  "contact_email": "new@email.com"
}
```

| Field | Type | Ghi chú |
|-------|------|---------|
| `full_name` | string | Họ tên |
| `is_active` | boolean | Kích hoạt/vô hiệu hoá |
| `phone` | string | SĐT |
| `contact_email` | string | Email liên hệ |

**Response `200`:** [UserResponse](#user-response)

---

### 4.4. DELETE `/users/{user_id}`

Vô hiệu hoá user (soft delete — set `is_active = false`).

**Response `200`:**

```json
{
  "message": "User deactivated"
}
```

---

### 4.5. POST `/users/{user_id}/reset-password`

Admin gửi email reset password cho user.

**Response `200`:**

```json
{
  "message": "Reset password email sent"
}
```

**Side effects:** Gửi email chứa link reset password cho user.

---

## 5. Admin Management (Super Admin)

### 5.1. GET `/users/admins/{tenant_id}`

**BRD F-A07**: Danh sách admin của một tenant.

**Roles:** `super_admin` only

**Response `200`:** `UserResponse[]` (chỉ user có role `tenant_admin` trong tenant đó)

---

### 5.2. POST `/users/admins`

**BRD F-A07**: Tạo admin cho tenant.

**Roles:** `super_admin` only

**Request Body:**

```json
{
  "email": "admin@tenant.com",
  "full_name": "Admin Nguyễn",
  "tenant_id": 1
}
```

| Field | Type | Required | Ghi chú |
|-------|------|----------|---------|
| `email` | email | ✅ | Email admin |
| `full_name` | string | ✅ | Họ tên |
| `tenant_id` | int | ✅ | ID tenant |

**Response `201`:** [UserResponse](#user-response) (role = `tenant_admin`)

**Side effects:** Gửi email welcome + credentials cho admin mới.

---

## 6. Tenant Management (Super Admin)

### 6.1. GET `/tenants`

Danh sách tất cả tenant.

**Roles:** `super_admin` only

**Response `200`:** `TenantResponse[]`

```json
[
  {
    "id": 1,
    "name": "ACME Corp",
    "tenant_code": "ACME",
    "subdomain": "acme",
    "description": "Công ty XNK ACME",
    "is_active": true,
    "logo_s3_key": "tenants/1/logo.png",
    "primary_color": "#1E40AF",
    "display_name": "ACME",
    "custom_email_domain": null,
    "etariff_daily_limit": 10,
    "created_at": "2025-01-01T00:00:00Z"
  }
]
```

---

### 6.2. POST `/tenants`

**BRD F-A06**: Tạo tenant mới + tự động tạo admin cho tenant.

**Roles:** `super_admin` only

**Request Body:**

```json
{
  "name": "BETA Corp",
  "tenant_code": "BETA",
  "description": "Công ty BETA",
  "is_active": true,
  "admin_email": "admin@beta.com",
  "admin_full_name": "Admin Beta",
  "primary_color": "#059669",
  "display_name": "BETA",
  "etariff_daily_limit": 20
}
```

| Field | Type | Required | Ghi chú |
|-------|------|----------|---------|
| `name` | string | ✅ | Tên tenant |
| `tenant_code` | string | ✅ | Mã tenant (unique, dùng trong display_id) |
| `description` | string | ❌ | Mô tả |
| `is_active` | boolean | ❌ | Mặc định `true` |
| `admin_email` | email | ✅ | Email admin đầu tiên |
| `admin_full_name` | string | ✅ | Tên admin |
| `primary_color` | string | ❌ | Mã màu branding (hex) |
| `display_name` | string | ❌ | Tên hiển thị |
| `etariff_daily_limit` | int | ❌ | Giới hạn E-Tariff/ngày, mặc định `10` |

**Response `201`:** [TenantResponse](#tenant-response)

**Side effects:**
- Tạo tenant mới
- Tạo `tenant_admin` user tự động
- Gửi email welcome + credentials cho admin

**Lưu ý:**
- `tenant_code` sẽ được dùng làm prefix cho display_id của request (vd: `BETA-001`)
- `subdomain` tự động sinh từ `tenant_code` (lowercase)

---

### 6.3. GET `/tenants/{tenant_id}`

Xem chi tiết tenant.

**Response `200`:** [TenantResponse](#tenant-response)

---

### 6.4. PUT `/tenants/{tenant_id}`

Cập nhật tenant.

**Request Body (chỉ gửi field cần update):**

```json
{
  "name": "BETA Corp Updated",
  "description": "Mô tả mới",
  "is_active": false,
  "primary_color": "#DC2626",
  "display_name": "BETA v2",
  "custom_email_domain": "beta.com",
  "etariff_daily_limit": 50
}
```

**Response `200`:** [TenantResponse](#tenant-response)

---

### 6.5. DELETE `/tenants/{tenant_id}`

Vô hiệu hoá tenant (soft delete).

**Response `200`:**

```json
{
  "message": "Tenant deactivated"
}
```

---

### 6.6. POST `/tenants/{tenant_id}/logo`

Upload logo cho tenant (lưu S3).

**Content-Type:** `multipart/form-data`

| Field | Type | Required |
|-------|------|----------|
| `logo` | File | ✅ |

**Response `200`:** [TenantResponse](#tenant-response) (có `logo_s3_key` mới)

---

## 7. Expert Management

### 7.1. GET `/tenants/experts/all`

**BRD F-A05**: Danh sách tất cả expert (cross-tenant).

**Roles:** `super_admin`, `tenant_admin`

**Response `200`:** `ExpertResponse[]`

```json
[
  {
    "id": 5,
    "email": "expert@chc.com",
    "full_name": "Chuyên gia Trần",
    "is_active": true,
    "created_at": "2025-01-01T00:00:00Z"
  }
]
```

---

### 7.2. POST `/tenants/experts`

**BRD F-A05**: Tạo expert mới (cross-tenant — không thuộc tenant nào).

**Roles:** `super_admin`, `tenant_admin`

**Request Body:**

```json
{
  "email": "expert2@chc.com",
  "full_name": "Chuyên gia Lê"
}
```

**Response `201`:** [ExpertResponse](#expert-response)

**Side effects:** Gửi email welcome + credentials cho expert mới.

---

## 8. Dashboard

### 8.1. GET `/dashboard/stats`

**BRD F-A02**: Thống kê tổng quan.

**Roles:** `super_admin`, `tenant_admin` (expert → 403)

**Response `200`:**

```json
{
  "total_users": 150,
  "total_requests": 500,
  "requests_pending": 20,
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

**Lưu ý:**
- `super_admin`: thấy all data + `total_tenants`/`active_tenants`
- `tenant_admin`: chỉ thấy data trong tenant mình, `total_tenants = null`

---

### 8.2. GET `/dashboard/recent-tenants`

Tenant mới nhất (Super Admin only).

**Query:** `?limit=10` (1-50, mặc định 10)

**Response `200`:**

```json
[
  {
    "id": 1,
    "name": "ACME Corp",
    "tenant_code": "ACME",
    "is_active": true,
    "created_at": "2025-01-15T00:00:00Z"
  }
]
```

---

### 8.3. GET `/dashboard/recent-users`

User mới nhất.

**Roles:** `super_admin`, `tenant_admin`

**Query:** `?limit=10`

**Response `200`:**

```json
[
  {
    "id": 1,
    "full_name": "Nguyễn Văn A",
    "email": "user@abc.com",
    "role": "user",
    "created_at": "2025-01-15T00:00:00Z"
  }
]
```

---

### 8.4. GET `/dashboard/recent-requests`

Request mới nhất.

**Roles:** `super_admin`, `tenant_admin`

**Query:** `?limit=10`

**Response `200`:**

```json
[
  {
    "id": 1,
    "display_id": "ACME-001",
    "type": "chc",
    "status": "pending",
    "submitted_at": "2025-01-15T10:30:00Z",
    "uploaded_by": "Nguyễn Văn A"
  }
]
```

---

### 8.5. GET `/dashboard/role-distribution`

Phân bổ user theo role.

**Roles:** `super_admin`, `tenant_admin`

**Response `200`:**

```json
{
  "super_admin": 2,
  "tenant_admin": 5,
  "expert": 8,
  "user": 135
}
```

---

## 9. Settings

### 9.1. GET `/settings/email-config`

Lấy cấu hình SMTP email của tenant.

**Roles:** `tenant_admin` only

**Response `200`:**

```json
{
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 587,
  "sender_email": "noreply@acme.com",
  "sender_name": "ACME CHC",
  "smtp_username": "noreply@acme.com",
  "smtp_password": "****",
  "is_enabled": true
}
```

**Response `null`** nếu chưa cấu hình.

---

### 9.2. PUT `/settings/email-config`

Cập nhật cấu hình SMTP email.

**Roles:** `tenant_admin` only

**Request Body:**

```json
{
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 587,
  "sender_email": "noreply@acme.com",
  "sender_name": "ACME CHC",
  "smtp_username": "noreply@acme.com",
  "smtp_password": "app-password-here",
  "is_enabled": true
}
```

| Field | Type | Required | Ghi chú |
|-------|------|----------|---------|
| `smtp_host` | string | ✅ | SMTP server |
| `smtp_port` | int | ✅ | Port (587 cho TLS, 465 cho SSL) |
| `sender_email` | string | ✅ | Email gửi |
| `sender_name` | string | ✅ | Tên hiển thị |
| `smtp_username` | string | ✅ | Username SMTP |
| `smtp_password` | string | ✅ | Password/App password |
| `is_enabled` | boolean | ❌ | Bật/tắt, mặc định `false` |

**Response `200`:** EmailConfigResponse

---

## 10. Webhook — Server-to-Server

### POST `/requests/webhook/ai-result`

Endpoint nội bộ — **Report Service** gọi khi AI task hoàn thành. **Không dùng JWT**, dùng webhook secret.

**Headers:**

```
X-Webhook-Secret: <webhook_secret>
Content-Type: application/json
```

**Request Body:**

```json
{
  "task_id": "task-abc-123",
  "status": "completed",
  "result": {
    "hs_code": "1101.00.10",
    "classification": "Bột mì",
    "output_s3_key": "results/task-abc-123/output.xlsx"
  },
  "error": null
}
```

| Field | Type | Required | Ghi chú |
|-------|------|----------|---------|
| `task_id` | string | ✅ | ID task từ Report Service |
| `status` | string | ✅ | `completed` hoặc `failed` |
| `result` | object | ❌ | Kết quả AI (khi status=completed) |
| `error` | string | ❌ | Thông tin lỗi (khi status=failed) |

**Response `200`:**

```json
{
  "status": "ok",
  "task_id": "task-abc-123"
}
```

**Lưu ý:**
- Nếu `WEBHOOK_SECRET` được set trong `.env`, header `X-Webhook-Secret` phải khớp → nếu không → `403`.
- Nếu không set `WEBHOOK_SECRET` → bypass check (dev mode).
- Khi AI xong, E-Tariff request sẽ **tự động chuyển sang `delivered`** (không cần admin approve).
- CHC request vẫn cần expert review + admin approve.

---

## 11. Health Check

### GET `/health`

Kiểm tra backend còn sống không. Không cần auth.

**Response `200`:**

```json
{
  "status": "ok"
}
```

---

## 12. Error Handling

### HTTP Status Codes

| Code | Ý nghĩa | Khi nào |
|------|---------|---------|
| `200` | Thành công | — |
| `400` | Bad Request | Logic không hợp lệ (assign đơn đã cancelled, v.v.) |
| `401` | Unauthorized | Token hết hạn/invalid |
| `403` | Forbidden | Không đủ quyền (sai role, sai tenant, webhook secret sai) |
| `404` | Not Found | Resource không tồn tại |
| `422` | Validation Error | Thiếu field, sai format |
| `503` | Service Unavailable | Report Service đang down |

### Error format

```json
{
  "detail": "Mô tả lỗi"
}
```

---

## Schema Reference

### <a id="request-response"></a>RequestResponse

```typescript
interface RequestResponse {
  id: number;
  display_id: string;        // "ACME-001"
  type: "chc" | "etariff_manual" | "etariff_batch";
  status: "pending" | "processing" | "completed" | "delivered" | "cancelled";
  chc_modules: string[] | null;
  assigned_expert_id: number | null;
  assigned_expert_name: string | null;
  submitted_at: string;       // ISO 8601
  completed_at: string | null;
  delivered_at: string | null;
  cancelled_at: string | null;
  admin_notes: string | null;
  files: RequestFileResponse[];
  user_name: string | null;
  user_email: string | null;
}

interface RequestFileResponse {
  id: number;
  request_id: number;
  original_filename: string;
  file_size: number | null;
  ai_status: "not_started" | "running" | "completed" | "failed";
  ai_task_id: string | null;
  ai_result_data: object | null;
  expert_s3_key: string | null;
  expert_pdf_s3_key: string | null;
  notes: string | null;
  created_at: string;
}
```

### <a id="user-response"></a>UserResponse

```typescript
interface UserResponse {
  id: number;
  email: string;
  full_name: string;
  role: "user" | "expert" | "tenant_admin" | "super_admin";
  is_active: boolean;
  is_first_login: boolean;
  locale: string;
  company_name: string | null;
  tax_code: string | null;
  phone: string | null;
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
  primary_color: string | null;
  display_name: string | null;
  custom_email_domain: string | null;
  etariff_daily_limit: number;  // default 10
  created_at: string;
}
```

### <a id="expert-response"></a>ExpertResponse

```typescript
interface ExpertResponse {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
  created_at: string | null;
}
```

---

## Luồng tích hợp cho FE Admin

### 1. Request Lifecycle (Admin view)

```
User tạo đơn
  → status: pending
  → Admin thấy trong list

Admin assign expert
  → POST /requests/{id}/assign
  → status: pending → processing
  → Expert nhận email thông báo

Expert xử lý + upload kết quả
  → POST /requests/{id}/files/{fid}/upload-result
  → status: processing → completed

Admin review + approve
  → POST /requests/{id}/approve
  → status: completed → delivered
  → User nhận email "kết quả đã sẵn sàng"
```

**Ngoại lệ — E-Tariff auto-deliver:**
- Đơn E-Tariff (manual/batch) được AI xử lý tự động
- Khi AI xong → webhook callback → status tự chuyển `delivered`
- Không cần admin assign expert hay approve

### 2. Tạo tenant + admin

```
Super Admin tạo tenant
  → POST /tenants (kèm admin_email, admin_full_name)
  → Backend tự tạo tenant + tenant_admin user
  → Email gửi cho admin mới (credentials)
  → FE refresh list
```

### 3. Dashboard data loading

```javascript
// Load all dashboard data in parallel
const [stats, recentTenants, recentUsers, recentRequests, roleDist] =
  await Promise.all([
    api.get('/dashboard/stats'),
    api.get('/dashboard/recent-tenants?limit=5'),
    api.get('/dashboard/recent-users?limit=10'),
    api.get('/dashboard/recent-requests?limit=10'),
    api.get('/dashboard/role-distribution'),
  ]);
```

### 4. Expert workflow

```
Expert đăng nhập
  → GET /requests (chỉ thấy request assigned cho mình)
  → Click vào request → GET /requests/{id}
  → Download file gốc → GET /requests/{id}/files/{fid}/download
  → Phân tích offline
  → Upload kết quả → POST /requests/{id}/files/{fid}/upload-result
  → Done, chờ admin approve
```
