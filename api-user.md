# CHC Backend — User Portal API Documentation

> Tài liệu API chi tiết dành cho FE team tích hợp **User Portal** (trang người dùng cuối).

---

## Mục lục

1. [Thông tin chung](#1-thông-tin-chung)
2. [Authentication](#2-authentication)
3. [Onboarding & Account](#3-onboarding--account)
4. [Requests — Tạo đơn](#4-requests--tạo-đơn)
5. [Requests — Xem & Quản lý](#5-requests--xem--quản-lý)
6. [Dashboard](#6-dashboard)
7. [Settings](#7-settings)
8. [Enums & Constants](#8-enums--constants)
9. [Error Handling](#9-error-handling)

---

## 1. Thông tin chung

### Base URL

```
Development:  http://localhost:8329
Production:   https://{subdomain}.chc.com
```

### Authentication

Tất cả API (trừ `/auth/login`, `/auth/reset-password`) yêu cầu JWT Bearer token trong header:

```
Authorization: Bearer <access_token>
```

### Content-Type

- JSON endpoints: `Content-Type: application/json`
- File upload endpoints: `Content-Type: multipart/form-data`

### Multi-tenant

Backend sử dụng subdomain để xác định tenant. FE cần gửi request từ đúng subdomain (ví dụ `acme.chc.com`) hoặc pass header `X-Tenant` nếu dev local.

---

## 2. Authentication

### 2.1. POST `/auth/login`

Đăng nhập, nhận access token + refresh token.

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

**Lưu ý quan trọng:**
- `is_first_login = true` → FE phải redirect user sang trang **Onboarding** trước khi cho phép làm gì khác.
- `refresh_token` chỉ trả về khi login, không trả về khi refresh.
- Tài khoản bị khoá sau **5 lần** đăng nhập sai liên tiếp (khoá **15 phút**).

**Error codes:**
- `401` — Sai email/password
- `423` — Tài khoản tạm khoá (quá nhiều lần sai)

---

### 2.2. POST `/auth/refresh`

Làm mới access token khi hết hạn.

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

**Cách tích hợp:** FE nên có interceptor — khi nhận `401` từ bất kỳ API nào, tự động gọi `/auth/refresh` rồi retry request gốc. Nếu refresh cũng lỗi → redirect về login.

**Token lifetime:**
- Access token: **24 giờ** (1440 phút)
- Refresh token: **7 ngày** (10080 phút)

---

### 2.3. POST `/auth/logout`

Đăng xuất — blacklist access token hiện tại.

**Headers:** `Authorization: Bearer <access_token>` (bắt buộc)

**Response `200`:**

```json
{
  "message": "Logged out"
}
```

---

### 2.4. POST `/auth/reset-password`

Đặt lại mật khẩu bằng token (nhận từ email reset password).

**Request Body:**

```json
{
  "token": "reset-token-from-email",
  "new_password": "newStrongPassword123"
}
```

**Response `200`:**

```json
{
  "message": "Password reset successful"
}
```

**Lưu ý:** Token reset hết hạn sau **60 phút**.

---

### 2.5. POST `/auth/change-password`

User đổi mật khẩu (đang đăng nhập).

**Headers:** `Authorization: Bearer <access_token>`

**Request Body:**

```json
{
  "current_password": "oldPassword123",
  "new_password": "newPassword456",
  "confirm_new_password": "newPassword456"
}
```

**Response `200`:**

```json
{
  "message": "Password changed successfully"
}
```

**Error:** `400` nếu `current_password` sai hoặc `new_password` ≠ `confirm_new_password`.

---

## 3. Onboarding & Account

### 3.1. POST `/users/onboarding`

**BRD F-U01**: User đăng nhập lần đầu phải điền thông tin công ty.

**Điều kiện:** User có `is_first_login = true`.

**Headers:** `Authorization: Bearer <access_token>`

**Request Body:**

```json
{
  "company_name": "Công ty TNHH ABC",
  "tax_code": "0123456789",
  "company_address": "123 Nguyễn Huệ, Q1, TP.HCM",
  "contact_person": "Nguyễn Văn A",
  "phone": "0912345678",
  "contact_email": "contact@abc.com",
  "industry": "Xuất nhập khẩu",
  "company_type": "TNHH"
}
```

| Field | Type | Required | Ghi chú |
|-------|------|----------|---------|
| `company_name` | string | ✅ | Tên công ty |
| `tax_code` | string | ✅ | MST: 10 hoặc 13 chữ số |
| `company_address` | string | ✅ | Địa chỉ |
| `contact_person` | string | ✅ | Người liên hệ |
| `phone` | string | ✅ | Số điện thoại |
| `contact_email` | email | ✅ | Email liên hệ |
| `industry` | string | ✅ | Ngành nghề |
| `company_type` | string | ✅ | Loại hình: `TNHH`, `Cổ phần`, `DNTN` |

**Response `200`:** [UserResponse](#user-response)

Sau khi onboarding thành công, `is_first_login` chuyển thành `false`.

---

### 3.2. PUT `/users/locale`

Đổi ngôn ngữ hiển thị.

**Request Body:**

```json
{
  "locale": "en"
}
```

**Giá trị hợp lệ:** `vi` (Tiếng Việt), `en` (English), `ko` (한국어), `zh` (中文)

**Response `200`:** [UserResponse](#user-response)

---

## 4. Requests — Tạo đơn

> **Quan trọng:** Tất cả endpoint tạo đơn yêu cầu user đã hoàn thành onboarding (`is_first_login = false`). Nếu chưa → `403`.
>
> Nếu Report Service (AI) đang bảo trì → trả `503` với message `"Hệ thống AI đang bảo trì, vui lòng thử lại sau."`. FE nên hiển thị thông báo này cho user.

### 4.1. POST `/requests/chc`

**BRD F-U03**: Tạo đơn CHC — upload file ECUS + chọn modules phân tích.

**Content-Type:** `multipart/form-data`

**Form fields:**

| Field | Type | Required | Ghi chú |
|-------|------|----------|---------|
| `files` | File[] | ✅ | File ECUS (Excel). Có thể upload nhiều file. Max **50MB** mỗi file. |
| `chc_modules` | string[] | ✅ | Danh sách module cần phân tích (xem bảng bên dưới) |

**CHC Modules:**

| Giá trị | Mô tả |
|---------|--------|
| `item_code_generator` | Tạo mã hàng hoá |
| `tariff_classification` | Phân loại thuế quan |
| `customs_valuation` | Trị giá hải quan |
| `non_tariff_measures` | Biện pháp phi thuế quan |
| `exim_statistics` | Thống kê XNK |

**Ví dụ HTML form:**

```html
<form enctype="multipart/form-data">
  <input type="file" name="files" multiple accept=".xlsx,.xls" />
  <select name="chc_modules" multiple>
    <option value="tariff_classification">Phân loại thuế quan</option>
    <option value="customs_valuation">Trị giá hải quan</option>
    <!-- ... -->
  </select>
</form>
```

**Ví dụ JavaScript (fetch):**

```javascript
const formData = new FormData();
formData.append('files', ecusFile);
formData.append('chc_modules', 'tariff_classification');
formData.append('chc_modules', 'customs_valuation');

const res = await fetch('/requests/chc', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${token}` },
  body: formData,
});
```

**Response `200`:** [RequestResponse](#request-response)

---

### 4.2. POST `/requests/etariff/manual`

**BRD F-U05**: Tạo đơn E-Tariff Manual — nhập form thông tin sản phẩm.

**Content-Type:** `application/json`

**Request Body:**

```json
{
  "commodity_name": "Bột mì",
  "scientific_name": "Triticum aestivum",
  "description": "Bột mì trắng dùng làm bánh mì",
  "function": "Nguyên liệu sản xuất bánh mì và bánh ngọt",
  "material_composition": "100% bột mì tinh luyện",
  "structure_components": "Dạng bột mịn, màu trắng",
  "technical_specification": "Độ ẩm < 14%, Protein > 11%",
  "additional_info": [
    { "label": "Xuất xứ", "value": "Úc" },
    { "label": "Đóng gói", "value": "Bao 25kg" }
  ]
}
```

| Field | Type | Required | Ghi chú |
|-------|------|----------|---------|
| `commodity_name` | string | ✅ | Tên hàng hoá |
| `scientific_name` | string | ❌ | Tên khoa học |
| `description` | string | ✅ | Mô tả chi tiết |
| `function` | string | ✅ | Công dụng/chức năng |
| `material_composition` | string | ✅ | Thành phần nguyên liệu |
| `structure_components` | string | ❌ | Cấu trúc/thành phần |
| `technical_specification` | string | ❌ | Thông số kỹ thuật |
| `additional_info` | array | ❌ | Thông tin bổ sung dạng `[{label, value}]` |

**Response `200`:** [RequestResponse](#request-response)

**Lưu ý:** Mỗi tenant có **daily limit** cho E-Tariff (mặc định 10 đơn/ngày). Nếu hết → trả `429`.

---

### 4.3. POST `/requests/etariff/batch`

**BRD F-U06**: Tạo đơn E-Tariff Batch — upload file Excel chứa nhiều sản phẩm.

**Content-Type:** `multipart/form-data`

**Form fields:**

| Field | Type | Required | Ghi chú |
|-------|------|----------|---------|
| `files` | File[] | ✅ | File Excel (.xlsx). Max **50MB** mỗi file. |

**Ví dụ JavaScript:**

```javascript
const formData = new FormData();
formData.append('files', batchExcelFile);

const res = await fetch('/requests/etariff/batch', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${token}` },
  body: formData,
});
```

**Response `200`:** [RequestResponse](#request-response)

---

## 5. Requests — Xem & Quản lý

### 5.1. GET `/requests/my`

**BRD F-U02**: Lấy danh sách đơn của user hiện tại.

**Query Parameters (tất cả optional):**

| Param | Type | Ví dụ | Ghi chú |
|-------|------|-------|---------|
| `status` | string | `pending` | Filter theo trạng thái |
| `type` | string | `chc` | Filter theo loại đơn |

**Ví dụ:**

```
GET /requests/my?status=pending&type=etariff_manual
```

**Response `200`:** `RequestResponse[]`

```json
[
  {
    "id": 1,
    "display_id": "ACME-001",
    "type": "chc",
    "status": "pending",
    "chc_modules": ["tariff_classification", "customs_valuation"],
    "assigned_expert_id": null,
    "assigned_expert_name": null,
    "submitted_at": "2025-01-15T10:30:00Z",
    "completed_at": null,
    "delivered_at": null,
    "cancelled_at": null,
    "admin_notes": null,
    "files": [
      {
        "id": 1,
        "request_id": 1,
        "original_filename": "ECUS_2025.xlsx",
        "file_size": 102400,
        "ai_status": "completed",
        "ai_task_id": "task-abc-123",
        "ai_result_data": { "hs_code": "1101.00.10", "description": "..." },
        "expert_s3_key": null,
        "expert_pdf_s3_key": null,
        "notes": null,
        "created_at": "2025-01-15T10:30:00Z"
      }
    ],
    "user_name": "Nguyễn Văn A",
    "user_email": "user@abc.com"
  }
]
```

---

### 5.2. GET `/requests/my/{request_id}`

Xem chi tiết một đơn.

**Response `200`:** [RequestResponse](#request-response)

**Error:** `404` nếu đơn không tồn tại hoặc không thuộc user hiện tại.

---

### 5.3. POST `/requests/my/{request_id}/cancel`

**BRD F-U04**: User huỷ đơn.

**Request Body (optional):**

```json
{
  "reason": "Không cần nữa"
}
```

**Response `200`:** [RequestResponse](#request-response) (status = `cancelled`)

**Error:** `400` nếu đơn đã ở trạng thái `delivered` hoặc `cancelled`.

---

### 5.4. GET `/requests/my/{request_id}/files/{file_id}/result`

**BRD F-U02**: Download kết quả phân tích (Excel/PDF).

**Response `200`:**

```json
{
  "download_url": "https://s3.amazonaws.com/chc-files/...",
  "filename": "result_ECUS_2025.xlsx"
}
```

**Lưu ý:** `download_url` là pre-signed S3 URL, có thời hạn (thường 1 giờ). FE nên mở URL này trong tab mới hoặc dùng `window.open()`.

**Error:** `404` nếu chưa có kết quả.

---

### 5.5. POST `/requests/my/{request_id}/retry`

**AC6**: Retry đơn E-Tariff khi AI xử lý thất bại.

**Không cần body.**

**Response `200`:** [RequestResponse](#request-response) (status reset, AI sẽ chạy lại)

**Error:** `400` nếu đơn không phải E-Tariff hoặc không ở trạng thái failed.

---

## 6. Dashboard

### 6.1. GET `/dashboard/stats`

**BRD F-U02**: Thống kê cá nhân của user.

**Response `200`:**

```json
{
  "total_users": 0,
  "total_requests": 15,
  "requests_pending": 2,
  "requests_processing": 3,
  "requests_completed": 5,
  "requests_delivered": 4,
  "requests_cancelled": 1,
  "total_tenants": null,
  "active_tenants": null,
  "requests_today": 1,
  "requests_this_week": 5,
  "requests_this_month": 10
}
```

**Lưu ý:** Với role `user`, `total_users` và các field tenant sẽ là `0`/`null`. Chỉ admin mới thấy đầy đủ.

---

## 7. Settings

### 7.1. GET `/settings/profile`

Lấy thông tin profile hiện tại.

**Response `200`:**

```json
{
  "full_name": "Nguyễn Văn A",
  "email": "user@abc.com",
  "role": "user",
  "username": null,
  "locale": "vi",
  "company_name": "Công ty TNHH ABC",
  "tax_code": "0123456789",
  "company_address": "123 Nguyễn Huệ, Q1, TP.HCM",
  "contact_person": "Nguyễn Văn A",
  "phone": "0912345678",
  "contact_email": "contact@abc.com",
  "industry": "Xuất nhập khẩu",
  "company_type": "TNHH",
  "is_first_login": false
}
```

---

### 7.2. PUT `/settings/profile`

**BRD F-U07**: Cập nhật thông tin cá nhân/công ty.

**Request Body (chỉ gửi field cần update):**

```json
{
  "full_name": "Nguyễn Văn B",
  "company_name": "Công ty CP XYZ",
  "phone": "0987654321"
}
```

| Field | Type | Ghi chú |
|-------|------|---------|
| `full_name` | string | Họ tên |
| `username` | string | Username |
| `company_name` | string | Tên công ty |
| `tax_code` | string | Mã số thuế |
| `company_address` | string | Địa chỉ |
| `contact_person` | string | Người liên hệ |
| `phone` | string | SĐT |
| `contact_email` | string | Email liên hệ |
| `industry` | string | Ngành nghề |
| `company_type` | string | Loại hình DN |

**Response `200`:** ProfileResponse (giống GET `/settings/profile`)

---

## 8. Enums & Constants

### Request Status (Vòng đời đơn hàng)

```
pending → processing → completed → delivered
                                  ↘ cancelled (user huỷ)
```

| Giá trị | Mô tả | Icon gợi ý |
|---------|--------|------------|
| `pending` | Chờ admin xử lý | 🟡 |
| `processing` | Đang xử lý (đã assign expert) | 🔵 |
| `completed` | Expert đã xong, chờ admin duyệt | 🟠 |
| `delivered` | Đã giao kết quả | 🟢 |
| `cancelled` | Đã huỷ | 🔴 |

### Request Type

| Giá trị | Mô tả |
|---------|--------|
| `chc` | Custom Health Check (upload file ECUS) |
| `etariff_manual` | E-Tariff thủ công (nhập form) |
| `etariff_batch` | E-Tariff batch (upload Excel) |

### CHC Modules

| Giá trị | Tiếng Việt |
|---------|-----------|
| `item_code_generator` | Tạo mã hàng hoá |
| `tariff_classification` | Phân loại thuế quan |
| `customs_valuation` | Trị giá hải quan |
| `non_tariff_measures` | Biện pháp phi thuế quan |
| `exim_statistics` | Thống kê XNK |

### User Roles

| Giá trị | Mô tả |
|---------|--------|
| `user` | Người dùng cuối |
| `expert` | Chuyên gia (xử lý đơn) |
| `tenant_admin` | Admin tenant |
| `super_admin` | Super admin (quản lý tất cả) |

### Locale

| Giá trị | Ngôn ngữ |
|---------|---------|
| `vi` | Tiếng Việt (mặc định) |
| `en` | English |
| `ko` | 한국어 |
| `zh` | 中文 |

---

## 9. Error Handling

### Cấu trúc lỗi chung

```json
{
  "detail": "Mô tả lỗi bằng tiếng Việt hoặc Anh"
}
```

### HTTP Status Codes

| Code | Ý nghĩa | Khi nào |
|------|---------|---------|
| `200` | Thành công | — |
| `400` | Bad Request | Dữ liệu không hợp lệ |
| `401` | Unauthorized | Token hết hạn hoặc không hợp lệ |
| `403` | Forbidden | Không có quyền (chưa onboarding, sai role) |
| `404` | Not Found | Đơn không tồn tại |
| `422` | Validation Error | Thiếu field bắt buộc, sai format |
| `423` | Locked | Tài khoản bị khoá (quá nhiều lần sai mật khẩu) |
| `429` | Too Many Requests | Vượt E-Tariff daily limit |
| `503` | Service Unavailable | Report Service (AI) đang bảo trì |

### Validation Error (422) format

```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```

---

## Schema Reference

### <a id="request-response"></a>RequestResponse

```typescript
interface RequestResponse {
  id: number;
  display_id: string;        // e.g. "ACME-001"
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
  file_size: number | null;   // bytes
  ai_status: "not_started" | "running" | "completed" | "failed";
  ai_task_id: string | null;
  ai_result_data: object | null;  // Structured JSON from AI
  expert_s3_key: string | null;
  expert_pdf_s3_key: string | null;
  notes: string | null;
  created_at: string;          // ISO 8601
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

---

## Luồng tích hợp gợi ý cho FE

### 1. Login Flow

```
User nhập email/password
  → POST /auth/login
  → Lưu access_token + refresh_token vào localStorage/cookie
  → Check is_first_login:
      true  → Redirect /onboarding
      false → Redirect /dashboard
```

### 2. Token Refresh Flow (Axios interceptor)

```javascript
// axios interceptor
axios.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401 && !error.config._retry) {
      error.config._retry = true;
      const { data } = await axios.post('/auth/refresh', {
        refresh_token: getRefreshToken(),
      });
      setAccessToken(data.access_token);
      error.config.headers.Authorization = `Bearer ${data.access_token}`;
      return axios(error.config);
    }
    return Promise.reject(error);
  }
);
```

### 3. Tạo đơn E-Tariff Manual

```
User điền form sản phẩm
  → POST /requests/etariff/manual
  → Nếu 503 → Hiển thị "AI đang bảo trì"
  → Nếu 429 → Hiển thị "Hết giới hạn hôm nay"
  → Nếu 200 → Hiển thị "Đã tạo đơn {display_id}"
  → Redirect danh sách đơn
```

### 4. Polling trạng thái đơn E-Tariff

E-Tariff được AI xử lý tự động. FE nên poll trạng thái:

```javascript
// Poll mỗi 10s cho đến khi status thay đổi
const pollRequest = async (requestId) => {
  const interval = setInterval(async () => {
    const { data } = await axios.get(`/requests/my/${requestId}`);
    if (data.status === 'delivered') {
      clearInterval(interval);
      // Hiển thị nút download
    } else if (data.status === 'cancelled') {
      clearInterval(interval);
      // Hiển thị thông báo
    }
  }, 10000);
};
```

### 5. Download kết quả

```javascript
const downloadResult = async (requestId, fileId) => {
  const { data } = await axios.get(
    `/requests/my/${requestId}/files/${fileId}/result`
  );
  window.open(data.download_url, '_blank');
};
```
