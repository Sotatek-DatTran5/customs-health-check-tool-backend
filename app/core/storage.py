import boto3
import botocore
from botocore.config import Config as BotoConfig
from fastapi.responses import StreamingResponse
import io

from app.core.config import settings


def _get_s3_client():
    kwargs = {
        "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
        "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
        "region_name": settings.AWS_REGION,
    }
    if settings.AWS_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.AWS_ENDPOINT_URL
    return boto3.client(
        "s3",
        **kwargs,
        config=BotoConfig(signature_version="s3v4"),
    )


def _bucket():
    return settings.S3_BUCKET_NAME


def ensure_bucket():
    """Create bucket if it doesn't exist (for LocalStack initial setup)."""
    client = _get_s3_client()
    try:
        client.head_bucket(Bucket=_bucket())
    except botocore.exceptions.ClientError:
        client.create_bucket(Bucket=_bucket())


def upload_file(s3_key: str, content: bytes, content_type: str = "application/octet-stream") -> str:
    """Upload file to S3. Returns the s3_key."""
    client = _get_s3_client()
    client.put_object(
        Bucket=_bucket(),
        Key=s3_key,
        Body=content,
        ContentType=content_type,
    )
    return s3_key


def download_file_stream(s3_key: str) -> StreamingResponse:
    """Stream file from S3 as a FastAPI StreamingResponse."""
    client = _get_s3_client()
    file_obj = io.BytesIO()
    client.download_fileobj(_bucket(), s3_key, file_obj)
    file_obj.seek(0)

    # Extract filename from key for Content-Disposition
    filename = s3_key.split("/")[-1]

    return StreamingResponse(
        file_obj,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def generate_presigned_url(s3_key: str, expires_in: int = 604800) -> str:
    """Generate presigned URL (default 7 days)."""
    client = _get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": _bucket(), "Key": s3_key},
        ExpiresIn=expires_in,
    )
