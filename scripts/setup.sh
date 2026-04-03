#!/bin/bash
set -e

echo "=== CHC Backend Setup ==="

# 1. Tạo file .env nếu chưa có
if [ ! -f .env ]; then
    cp .env.example .env
    echo "[OK] Tạo file .env từ .env.example — nhớ điền các giá trị thật vào"
else
    echo "[SKIP] File .env đã tồn tại"
fi

# 2. Cài dependencies bằng uv
echo ""
echo "--- Cài dependencies ---"
uv sync

# 3. Build Docker images
echo ""
echo "--- Build Docker images ---"
docker compose build

# 4. Khởi động infrastructure services trước
echo ""
echo "--- Khởi động postgres, redis, localstack, mailhog ---"
docker compose up -d postgres redis localstack mailhog

# 5. Chờ postgres sẵn sàng
echo "--- Chờ postgres khởi động..."
sleep 5

# 6. Chạy migration
echo ""
echo "--- Chạy Alembic migration ---"
uv run alembic upgrade head

# 7. Init LocalStack bucket
echo ""
echo "--- Init LocalStack S3 bucket ---"
./scripts/setup-local.sh

echo ""
echo "=== Setup hoàn tất ==="
echo "Chạy ./scripts/start.sh để khởi động app + worker"
echo "MailHog UI: http://localhost:8025"
