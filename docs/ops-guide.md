# CHC Backend — Operations Guide

> Huong dan cau hinh va van hanh cho DevOps / Admin.
> Last updated: 2026-04-14

---

## 1. Tao Super Admin

Super admin duoc tao bang script seed. Chay mot lan sau khi deploy lan dau.

### Chay script

```bash
# Trong container (production)
docker compose exec app uv run python scripts/seed.py

# Chay truc tiep (local dev)
uv run python scripts/seed.py
```

### Ket qua

```
[OK] Super admin created: admin@chc.com / Admin@123
# Hoac neu da ton tai:
[SKIP] Super admin already exists: admin@chc.com
```

### Thong tin mac dinh

| Field    | Gia tri       |
|----------|---------------|
| Email    | admin@chc.com |
| Password | Admin@123     |
| Role     | super_admin   |

> **Luu y bao mat:** Doi password ngay sau khi deploy production lan dau qua Admin Portal → Settings.

### Doi password sau khi tao

```bash
curl -X POST https://api.chc-service.click/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@chc.com","password":"Admin@123"}'

# Lay access_token roi goi:
curl -X POST https://api.chc-service.click/auth/change-password \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "current_password": "Admin@123",
    "new_password": "NewStrongPassword@2026",
    "confirm_new_password": "NewStrongPassword@2026"
  }'
```

---

## 2. Cau hinh Email

Backend ho tro 2 phuong thuc gui email. **Priority: SES > SMTP.**

| Phuong thuc | Khi nao dung |
|-------------|-------------|
| AWS SES     | Production (khuyen dung) |
| SMTP/Gmail  | Dev hoac fallback |

---

### 2.1. Dung AWS SES (Production)

#### Buoc 1 — Verify domain hoac email trong AWS SES

1. Vao **AWS Console → SES → Verified identities**
2. Click **Create identity**
3. Chon **Domain** (khuyen dung) hoac **Email address**
4. Them DNS records vao domain (SES se cung cap TXT/CNAME records)
5. Cho trang thai chuyen sang **Verified**

> Neu dang o **SES Sandbox** (mac dinh), chi gui duoc toi email da verify. De gui cho bat ky ai, can **request production access**:
> AWS Console → SES → Account dashboard → Request production access.

#### Buoc 2 — Tao IAM user co quyen SES

1. Vao **IAM → Users → Create user**
2. Gan policy: `AmazonSESFullAccess` (hoac custom policy chi cho `ses:SendEmail`)
3. Tao **Access Key** cho user nay

IAM policy toi thieu:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "ses:SendEmail",
      "Resource": "*"
    }
  ]
}
```

#### Buoc 3 — Cap nhat `.env`

```env
# AWS credentials (co the dung chung voi S3 neu IAM user co ca 2 quyen)
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=ap-southeast-1   # Region SES da verify domain

# Bat SES: set email nay = email/domain da verify trong SES
SES_SENDER_EMAIL=noreply@yourdomain.com

# Tat SMTP (de trong)
SMTP_HOST=
```

> **Quan trong:** `SES_SENDER_EMAIL` phai la email thuoc domain da verify trong SES.
> `AWS_REGION` phai trung voi region da setup SES (vi du `us-east-1`, `ap-southeast-1`).

#### Kiem tra SES hoat dong

```bash
# Test gui email truc tiep bang AWS CLI
aws ses send-email \
  --from "noreply@yourdomain.com" \
  --to "test@example.com" \
  --subject "SES Test" \
  --text "Hello from SES" \
  --region ap-southeast-1
```

---

### 2.2. Dung Gmail SMTP (Dev / Fallback)

#### Buoc 1 — Tao App Password Gmail

1. Vao Google Account → **Security → 2-Step Verification** (phai bat)
2. Vao **App passwords → Create**
3. Chon app: **Mail**, device: **Other** → Nhap ten → **Generate**
4. Luu password 16 ky tu (hien 1 lan duy nhat)

#### Buoc 2 — Cap nhat `.env`

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your.email@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx   # App password 16 ky tu
SMTP_FROM=your.email@gmail.com

# Tat SES (de trong)
SES_SENDER_EMAIL=
```

---

### 2.3. Logic uu tien email

```
SES_SENDER_EMAIL co gia tri?
  → Dung AWS SES

SMTP_HOST co gia tri?
  → Dung SMTP

Khong co gi?
  → Log email ra console (chi dung dev)
```

Code xu ly o [app/core/email.py](../app/core/email.py).

---

## 3. Cau hinh .env day du (Production)

```env
# ── App ──
SECRET_KEY=<random 64 chars>          # openssl rand -hex 32
ACCESS_TOKEN_EXPIRE_MINUTES=1440      # 24h
REFRESH_TOKEN_EXPIRE_MINUTES=10080    # 7 ngay
PASSWORD_RESET_EXPIRE_MINUTES=60

# ── Database ──
DATABASE_URL=postgresql://user:password@postgres:5432/chc

# ── Redis ──
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1

# ── AWS S3 ──
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=ap-southeast-2
S3_BUCKET_NAME=chc-files-sotatek

# ── Email: chon 1 trong 2 ──
# Option A: AWS SES (khuyen dung)
SES_SENDER_EMAIL=noreply@yourdomain.com

# Option B: Gmail SMTP
# SMTP_HOST=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USERNAME=your@gmail.com
# SMTP_PASSWORD=app-password-16-chars
# SMTP_FROM=your@gmail.com

# ── AI Service ──
AI_API_URL=https://api.chc-consulting.sotatek.works
AI_API_USERNAME=...
AI_API_PASSWORD=...

# ── Domain ──
ADMIN_DOMAIN=api.chc-service.click
BASE_DOMAIN=chc-service.click

# ── Security ──
MAX_LOGIN_ATTEMPTS=5
LOGIN_LOCKOUT_MINUTES=15
MAX_UPLOAD_SIZE_MB=50
WEBHOOK_SECRET=<random string>
```

---

## 4. Deploy moi tu dau

```bash
# 1. Clone repo
git clone <repo-url>
cd chc-backend

# 2. Tao .env
cp .env.example .env
# Edit .env voi gia tri production

# 3. Deploy (build + migrate + seed)
./scripts/deploy.sh
```

`deploy.sh` tu dong:
- Build Docker image
- Chay migration: `alembic upgrade head`
- Chay seed: tao super admin

---

## 5. Update code (Deploy moi)

```bash
git pull
docker compose up -d --build
# Migration se chay tu dong trong deploy.sh
# Hoac chay thu cong:
docker compose exec app uv run alembic upgrade head
```

> **Luu y:** `scripts/start.sh` chi start container hien co, **khong rebuild**. Dung `docker compose up -d --build` khi co code moi.
