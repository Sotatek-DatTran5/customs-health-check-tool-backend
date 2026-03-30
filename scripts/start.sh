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
echo "API:  http://localhost:8000"
echo "Docs: http://localhost:8000/docs"
echo ""
echo "Chạy ./scripts/status.sh để kiểm tra trạng thái"
