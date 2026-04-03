#!/bin/bash
set -e

echo "=== LocalStack S3 Setup ==="

# Wait for LocalStack to be ready
echo "Waiting for LocalStack..."
for i in $(seq 1 30); do
    if curl -s "http://localhost:4566/_localstack/health" | grep -q '"s3": "available"'; then
        echo "LocalStack S3 is ready"
        break
    fi
    echo "  ... waiting ($i/30)"
    sleep 2
done

# Create bucket if not exists
BUCKET="${S3_BUCKET_NAME:-chc-files}"
echo ""
echo "--- Ensuring bucket '$BUCKET' exists ---"
aws --endpoint-url=http://localhost:4566 s3 mb "s3://$BUCKET" 2>/dev/null && echo "[OK] Bucket created" || echo "[SKIP] Bucket already exists"

echo ""
echo "=== LocalStack setup done ==="
echo "MailHog web UI: http://localhost:8025"
echo "LocalStack S3:  http://localhost:4566"
