# CHC Backend — User Portal API Documentation

> Tài liệu API chi tiết dành cho FE team tích hợp **User Portal** (trang nguoi dung cuoi).
> BRD v8 — Last updated: 2026-04-13

---

## Muc luc

1. [Thong tin chung](#1-thong-tin-chung)
2. [Authentication](#2-authentication)
3. [Onboarding & Account](#3-onboarding--account)
4. [Requests — Tao don (Presigned URL)](#4-requests--tao-don-presigned-url)
5. [Requests — Tao don (Legacy)](#5-requests--tao-don-legacy)
6. [Requests — Xem & Quan ly](#6-requests--xem--quan-ly)
7. [Dashboard](#7-dashboard)
8. [Settings](#8-settings)
9. [Enums & Constants](#9-enums--constants)
10. [Error Handling](#10-error-handling)

---

## 1. Thong tin chung

### Base URL

```
Development:  http://localhost:8329
Production:   https://{subdomain}.chc-service.click
```

### Authentication

Tat ca API (tru `/auth/login`, `/auth/reset-password`, `/auth/forgot-password`) yeu cau JWT Bearer token trong header:

```
Authorization: Bearer <access_token>
```

### Content-Type

- JSON endpoints: `Content-Type: application/json`
- File upload endpoints: `Content-Type: multipart/form-data`

### Multi-tenant

Backend su dung subdomain de xac dinh tenant. FE can gui request tu dung subdomain (vi du `acme.chc-service.click`).

### Tenant Disabled

Khi tenant bi vo hieu hoa, tat ca request tu subdomain do se tra ve:

```json
// HTTP 403
{
  "error": "tenant_disabled",
  "message": "Tenant nay da bi vo hieu hoa.",
  "tenant_name": "ACME Corp",
  "owner_name": "Nguyen Van A",
  "owner_email": "owner@acme.com",
  "owner_phone": "0912345678"
}
```

FE nen render trang lien he chu so huu tu response nay.

---

## 2. Authentication

### 2.1. POST `/auth/login`

Dang nhap, nhan access token + refresh token.

**Request Body:**

```json
{
  "email": "user@example.com",
  "password": "yourpassword"
}
```

**Response `200`:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "is_first_login": true,
  "token_type": "bearer"
}
```

**Luu y quan trong:**
- `is_first_login = true` -> FE phai redirect user sang trang **Onboarding** truoc khi cho phep lam gi khac.
- `refresh_token` chi tra ve khi login, khong tra ve khi refresh.
- Tai khoan bi khoa sau **5 lan** dang nhap sai lien tiep (khoa **15 phut**).

**Error codes:**
- `401` — Sai email/password
- `403` — Tai khoan bi vo hieu hoa
- `423` — Tai khoan tam khoa (qua nhieu lan sai)

---

### 2.2. POST `/auth/refresh`

Lam moi access token khi het han.

**Request Body:**

```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Response `200`:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": null,
  "is_first_login": false,
  "token_type": "bearer"
}
```

**Token lifetime:**
- Access token: **24 gio**
- Refresh token: **7 ngay**

---

### 2.3. POST `/auth/logout`

Dang xuat — blacklist access token hien tai.

**Headers:** `Authorization: Bearer <access_token>`

**Response `200`:** `{ "message": "Logged out" }`

---

### 2.4. POST `/auth/forgot-password` (BRD v8)

Tu phuc hoi mat khau — gui link reset qua email. **Khong can dang nhap.**

**Request Body:**

```json
{
  "email": "user@example.com"
}
```

**Response `200`:**

```json
{
  "message": "Neu email ton tai trong he thong, chung toi da gui link dat lai mat khau."
}
```

**Luu y:** Luon tra `200` du email co ton tai hay khong (chong email enumeration). FE hien thong bao thanh cong trong moi truong hop.

---

### 2.5. POST `/auth/reset-password`

Dat lai mat khau bang token (nhan tu email reset password).

**Request Body:**

```json
{
  "token": "reset-token-from-email",
  "new_password": "newStrongPassword123"
}
```

**Response `200`:** `{ "message": "Password reset successful" }`

**Token het han sau 60 phut.**

---

### 2.6. POST `/auth/change-password`

User doi mat khau (dang dang nhap).

**Request Body:**

```json
{
  "current_password": "oldPassword123",
  "new_password": "newPassword456",
  "confirm_new_password": "newPassword456"
}
```

**Response `200`:** `{ "message": "Password changed successfully" }`

---

## 3. Onboarding & Account

### 3.1. POST `/users/onboarding`

**BRD F-U01**: User dang nhap lan dau phai dien thong tin cong ty.

**Dieu kien:** User co `is_first_login = true`.

**Request Body:**

```json
{
  "company_name": "Cong ty TNHH ABC",
  "tax_code": "0123456789",
  "company_address": "123 Nguyen Hue, Q1, TP.HCM",
  "contact_person": "Nguyen Van A",
  "phone": "0912345678",
  "contact_email": "contact@abc.com",
  "result_email": "ketqua@abc.com",
  "industry": "Xuat nhap khau",
  "company_type": "TNHH"
}
```

| Field | Type | Required | Ghi chu |
|-------|------|----------|---------|
| `company_name` | string | Yes | Ten cong ty |
| `tax_code` | string | Yes | MST: 10 hoac 13 chu so |
| `company_address` | string | Yes | Dia chi |
| `contact_person` | string | Yes | Nguoi lien he |
| `phone` | string | Yes | So dien thoai |
| `contact_email` | email | Yes | Email lien he |
| `result_email` | email | No | **BRD v8**: Email nhan ket qua CHC (neu khac contact_email) |
| `industry` | string | Yes | Nganh nghe |
| `company_type` | string | Yes | Loai hinh: `TNHH`, `Co phan`, `DNTN` |

**Response `200`:** [UserResponse](#user-response)

---

### 3.2. PUT `/users/locale`

Doi ngon ngu hien thi. Gia tri hop le: `vi`, `en`, `ko`, `zh`

**Request Body:** `{ "locale": "en" }`

**Response `200`:** [UserResponse](#user-response)

---

## 4. Requests — Tao don (Presigned URL)

> **BRD v8 — Flow moi (khuyen dung):** Upload file qua S3 presigned URL de giam tai cho backend.
>
> Luong 3 buoc: Request URL -> Upload S3 -> Confirm

### 4.1. POST `/requests/presigned-url`

**Buoc 1:** Tao don + nhan presigned upload URL.

**Request Body:**

```json
{
  "filename": "ECUS_2025.xlsx",
  "file_size": 102400,
  "request_type": "chc",
  "chc_modules": ["tariff_classification", "customs_valuation"]
}
```

| Field | Type | Required | Ghi chu |
|-------|------|----------|---------|
| `filename` | string | Yes | Ten file (chi `.xlsx`, `.xlsb`) |
| `file_size` | int | Yes | Kich thuoc file (bytes). Max **50MB** |
| `request_type` | string | Yes | `chc` hoac `etariff_batch` |
| `chc_modules` | string[] | CHC only | Bat buoc khi `request_type = chc` |

**Response `200`:**

```json
{
  "request_id": 42,
  "file_id": 67,
  "display_id": "ACME-001",
  "upload_url": "https://s3.amazonaws.com/chc-files/...?X-Amz-Signature=...",
  "s3_key": "1/requests/42/ECUS_2025.xlsx",
  "expires_in": 900
}
```

**Error:** `503` neu AI dang bao tri, `429` neu het quota E-Tariff.

---

### 4.2. Upload file truc tiep len S3

**Buoc 2:** FE dung `upload_url` de PUT file truc tiep len S3 (khong qua backend).

```javascript
await fetch(uploadUrl, {
  method: 'PUT',
  headers: {
    'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  },
  body: file, // File object
});
```

**Luu y:**
- `Content-Type` phai dung nhu khi request presigned URL
- Khong can `Authorization` header (presigned URL da co chu ky)
- URL het han sau **15 phut** (`expires_in: 900`)

---

### 4.3. POST `/requests/{request_id}/confirm-upload`

**Buoc 3:** Xac nhan upload thanh cong -> backend validate file, bat dau AI.

**Khong can body.**

**Response `200`:**

```json
{
  "request_id": 42,
  "display_id": "ACME-001",
  "status": "ai_processing",
  "row_count": 150,
  "quota_remaining": 850,
  "warning": null
}
```

| Field | Khi nao co | Ghi chu |
|-------|-----------|---------|
| `row_count` | E-Tariff batch | So dong du lieu trong file (tru header) |
| `quota_remaining` | E-Tariff batch | So luot con lai trong ngay |
| `warning` | Khi rows > quota | VD: "File co 150 dong nhung ban chi con 50 luot" |

**Side effects:**
- Status chuyen tu `pending` -> `ai_processing`
- Celery task goi Report Service
- Email xac nhan gui cho user + admin

---

### Flow tich hop Presigned URL

```javascript
// Buoc 1: Lay presigned URL
const { data: presigned } = await api.post('/requests/presigned-url', {
  filename: file.name,
  file_size: file.size,
  request_type: 'chc',
  chc_modules: ['tariff_classification'],
});

// Buoc 2: Upload file truc tiep len S3
await fetch(presigned.upload_url, {
  method: 'PUT',
  headers: { 'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' },
  body: file,
});

// Buoc 3: Xac nhan
const { data: result } = await api.post(`/requests/${presigned.request_id}/confirm-upload`);
console.log(result.status); // "ai_processing"
```

---

## 5. Requests — Tao don (Legacy)

> Cac endpoint cu (upload file truc tiep qua backend). Van hoat dong nhung **khuyen dung presigned URL** o Section 4.

### 5.1. POST `/requests/chc`

Upload file ECUS + chon modules. `multipart/form-data`.

| Field | Type | Required |
|-------|------|----------|
| `files` | File[] | Yes |
| `chc_modules` | string[] | Yes |

**File formats:** `.xlsx`, `.xlsb` (BRD v8: da bo `.xls`)

---

### 5.2. POST `/requests/etariff/manual`

E-Tariff Manual — nhap form JSON. Khong can file upload.

**Request Body:**

```json
{
  "commodity_name": "Bot mi",
  "description": "Bot mi trang dung lam banh mi",
  "function": "Nguyen lieu san xuat banh",
  "material_composition": "100% bot mi tinh luyen"
}
```

---

### 5.3. POST `/requests/etariff/batch`

E-Tariff Batch — upload file Excel. `multipart/form-data`.

---

## 6. Requests — Xem & Quan ly

### 6.1. GET `/requests/my`

Danh sach don cua user hien tai.

**Query Parameters:** `?status=pending&type=chc`

**Response `200`:** `RequestResponse[]`

---

### 6.2. GET `/requests/my/{request_id}`

Chi tiet mot don.

**Response `200`:** [RequestResponse](#request-response)

---

### 6.3. POST `/requests/my/{request_id}/cancel`

Huy don. Chi duoc huy khi status la: `pending`, `ai_processing`, `pending_assignment`, `processing`.

**Request Body (optional):** `{ "reason": "Khong can nua" }`

**Response `200`:** [RequestResponse](#request-response) (status = `cancelled`)

**Error:** `400` neu don da `completed`, `delivered`, hoac `cancelled`.

---

### 6.4. GET `/requests/my/{request_id}/files/{file_id}/result`

Download ket qua phan tich (Excel/PDF).

**Response `200`:**

```json
{
  "url": "https://s3.amazonaws.com/chc-files/...",
  "filename": "result_ECUS_2025.xlsx",
  "show_rating_popup": true
}
```

| Field | Ghi chu |
|-------|---------|
| `url` | Pre-signed S3 URL (7 ngay) |
| `show_rating_popup` | **BRD v8**: `true` khi user da download nhung chua danh gia. FE nen hien popup rating |

**Luu y:** Lan download dau tien se set `has_downloaded = true` tren request.

---

### 6.5. POST `/requests/my/{request_id}/retry`

Retry don E-Tariff khi AI xu ly that bai.

**Response `200`:** [RequestResponse](#request-response)

---

### 6.6. POST `/requests/my/{request_id}/rate` (BRD v8)

User danh gia request da delivered (1-5 sao).

**Request Body:**

```json
{
  "rating": 5,
  "comment": "Ket qua rat chinh xac, cam on!"
}
```

| Field | Type | Required | Ghi chu |
|-------|------|----------|---------|
| `rating` | int | Yes | 1-5 sao |
| `comment` | string | No | Nhan xet |

**Response `200`:** [RequestResponse](#request-response) (has_rated = true)

**Error:**
- `400` neu don chua `delivered` hoac da rated roi

**Luong goi y:**
1. User download ket qua -> `show_rating_popup = true`
2. FE hien popup rating
3. User submit -> `POST /requests/my/{id}/rate`
4. Popup dong, `has_rated = true`

---

## 7. Dashboard

### 7.1. GET `/dashboard/stats`

Thong ke ca nhan cua user.

**Response `200`:**

```json
{
  "total_users": 0,
  "total_requests": 15,
  "requests_pending": 2,
  "requests_ai_processing": 1,
  "requests_pending_assignment": 0,
  "requests_processing": 3,
  "requests_completed": 4,
  "requests_delivered": 4,
  "requests_cancelled": 1,
  "total_tenants": null,
  "active_tenants": null,
  "requests_today": 1,
  "requests_this_week": 5,
  "requests_this_month": 10
}
```

---

## 8. Settings

### 8.1. GET `/settings/profile`

Lay thong tin profile hien tai.

**Response `200`:** Bao gom cac field tu [UserResponse](#user-response) + company info.

---

### 8.2. PUT `/settings/profile`

Cap nhat thong tin ca nhan/cong ty. Chi gui field can update.

---

## 9. Enums & Constants

### Request Status (Vong doi don hang — BRD v8)

```
pending -> ai_processing -> pending_assignment -> processing -> completed -> delivered
                                                                           -> cancelled
```

**Internal status (7 trang thai):**

| Gia tri | Mo ta |
|---------|--------|
| `pending` | Vua tao don, chua xu ly |
| `ai_processing` | Dang goi AI (Report Service) |
| `pending_assignment` | AI xong, cho Admin assign Expert |
| `processing` | Admin da assign Expert |
| `completed` | Expert da xong, cho Admin duyet |
| `delivered` | Da giao ket qua |
| `cancelled` | Da huy |

**User-facing status (5 trang thai):** Backend tra field `user_facing_status` da map san:

| user_facing_status | Hien thi | Cac internal status |
|-------------------|----------|-------------------|
| `pending` | Cho xu ly | pending |
| `processing` | Dang xu ly | ai_processing, pending_assignment, processing |
| `completed` | Hoan thanh | completed |
| `delivered` | Da giao | delivered |
| `cancelled` | Da huy | cancelled |

**FE nen dung `user_facing_status` de hien thi, dung `status` khi can logic cu the.**

### Request Type

| Gia tri | Mo ta |
|---------|--------|
| `chc` | Custom Health Check |
| `etariff_manual` | E-Tariff thu cong (nhap form) |
| `etariff_batch` | E-Tariff batch (upload Excel) |

### CHC Modules

| Gia tri | Tieng Viet |
|---------|-----------|
| `item_code_generator` | Tao ma hang hoa |
| `tariff_classification` | Phan loai thue quan |
| `customs_valuation` | Tri gia hai quan |
| `non_tariff_measures` | Bien phap phi thue quan |
| `exim_statistics` | Thong ke XNK |

### Pricing Tier (BRD v8)

| So modules | Tier |
|-----------|------|
| 1-2 | Goi Co ban |
| 3-5 | Goi Toan dien |

Backend tu tinh va tra field `pricing_tier` trong `RequestResponse` cho don CHC.

### File Formats

**Chap nhan:** `.xlsx`, `.xlsb`
**Tu choi:** `.xls` (da bo tu BRD v8)
**Max size:** 50MB

### Locale

| Gia tri | Ngon ngu |
|---------|---------|
| `vi` | Tieng Viet (mac dinh) |
| `en` | English |
| `ko` | Korean |
| `zh` | Chinese |

---

## 10. Error Handling

### HTTP Status Codes

| Code | Y nghia | Khi nao |
|------|---------|---------|
| `200` | Thanh cong | — |
| `400` | Bad Request | Du lieu khong hop le |
| `401` | Unauthorized | Token het han hoac khong hop le |
| `403` | Forbidden | Chua onboarding, sai role, tenant disabled |
| `404` | Not Found | Don khong ton tai |
| `422` | Validation Error | Thieu field bat buoc, sai format |
| `423` | Locked | Tai khoan bi khoa |
| `429` | Too Many Requests | Vuot E-Tariff daily limit |
| `503` | Service Unavailable | Report Service (AI) dang bao tri |

### Error format

```json
{ "detail": "Mo ta loi" }
```

---

## Schema Reference

### <a id="request-response"></a>RequestResponse

```typescript
interface RequestResponse {
  id: number;
  display_id: string;        // "ACME-001"
  type: "chc" | "etariff_manual" | "etariff_batch";
  status: string;            // Internal: 7 values
  user_facing_status: string; // Mapped: 5 values (pending/processing/completed/delivered/cancelled)
  chc_modules: string[] | null;
  assigned_expert_id: number | null;
  assigned_expert_name: string | null;
  submitted_at: string;
  completed_at: string | null;
  delivered_at: string | null;
  cancelled_at: string | null;
  admin_notes: string | null;
  has_downloaded: boolean;    // BRD v8: true after first download
  has_rated: boolean;         // BRD v8: true after rating
  rating: number | null;      // BRD v8: 1-5
  pricing_tier: string | null; // BRD v8: "Goi Co ban" | "Goi Toan dien" (CHC only)
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
  result_email: string | null; // BRD v8
  last_login_at: string | null;
  tenant_id: number | null;
  created_at: string | null;
}
```

---

## Luong tich hop goi y cho FE

### 1. Login Flow

```
User nhap email/password
  -> POST /auth/login
  -> Luu access_token + refresh_token
  -> Check is_first_login:
      true  -> Redirect /onboarding
      false -> Redirect /dashboard
```

### 2. Quen mat khau (BRD v8)

```
User click "Quen mat khau?"
  -> Nhap email
  -> POST /auth/forgot-password
  -> Hien "Da gui link reset" (luon, du email co ton tai hay khong)
  -> User check email -> click link
  -> Redirect /auth/reset-password?token=xxx
  -> Nhap mat khau moi -> POST /auth/reset-password
```

### 3. Tao don CHC (Presigned URL)

```javascript
// 1. Request presigned URL
const { data } = await api.post('/requests/presigned-url', {
  filename: file.name,
  file_size: file.size,
  request_type: 'chc',
  chc_modules: selectedModules,
});

// 2. Upload to S3
await fetch(data.upload_url, {
  method: 'PUT',
  headers: { 'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' },
  body: file,
});

// 3. Confirm
const { data: result } = await api.post(`/requests/${data.request_id}/confirm-upload`);
// result.status === "ai_processing"
// -> Redirect to request detail, poll for status change
```

### 4. Polling trang thai don

```javascript
const pollRequest = async (requestId) => {
  const interval = setInterval(async () => {
    const { data } = await api.get(`/requests/my/${requestId}`);
    if (data.user_facing_status === 'delivered') {
      clearInterval(interval);
      // Show download button
    }
  }, 10000);
};
```

### 5. Download + Rating

```javascript
// Download
const { data } = await api.get(`/requests/my/${requestId}/files/${fileId}/result`);
window.open(data.url, '_blank');

// Check if should show rating
if (data.show_rating_popup) {
  showRatingDialog();
}

// Submit rating
await api.post(`/requests/my/${requestId}/rate`, {
  rating: 5,
  comment: 'Rat tot!',
});
```
