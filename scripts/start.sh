#!/bin/bash
set -e

echo "=== Khởi động CHC Backend ==="

# Kiểm tra file .env tồn tại
if [ ! -f .env ]; then
    echo "[ERROR] Không tìm thấy file .env — chạy ./scripts/setup.sh trước"
    exit 1
fi

docker compose up -d

echo ""
echo "=== Server đã khởi động ==="
echo "API:  http://localhost:8329"
echo "Docs: http://localhost:8329/docs"
echo "MailHog UI: http://localhost:8025"
echo ""
echo "Chạy ./scripts/status.sh để kiểm tra trạng thái"
