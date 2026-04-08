"""HTTP client for Report Service (Excel Analysis API)."""
import time
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

POLL_INTERVAL = 5  # seconds between status checks
MAX_POLL_TIME = 600  # 10 minutes max wait

TERMINAL_STATUSES = {"SUCCESS", "FAILURE"}


def _client() -> httpx.Client:
    headers = {}
    if settings.AI_API_KEY:
        headers["Authorization"] = f"Bearer {settings.AI_API_KEY}"
    return httpx.Client(base_url=settings.AI_API_URL, headers=headers, timeout=60.0)


def get_upload_url(filename: str) -> dict:
    """GET /api/v1/report/upload-url — presigned URL for MinIO upload."""
    with _client() as c:
        r = c.get("/api/v1/report/upload-url", params={"filename": filename})
        r.raise_for_status()
        return r.json()


def upload_to_presigned_url(upload_url: str, file_bytes: bytes):
    """PUT file bytes to a presigned upload URL."""
    with httpx.Client(timeout=120.0) as c:
        r = c.put(upload_url, content=file_bytes, headers={"Content-Type": "application/octet-stream"})
        r.raise_for_status()


def process_async(object_name: str, input_sections: list[str] | None = None) -> str:
    """POST /api/v1/report/process/async — CHC analysis. Returns task_id."""
    body: dict = {"object_name": object_name}
    if input_sections:
        body["input_sections"] = input_sections
    with _client() as c:
        r = c.post("/api/v1/report/process/async", json=body)
        r.raise_for_status()
        return r.json()["task_id"]


def classify_async(product_data: dict) -> str:
    """POST /api/v1/report/classify/async — single product. Returns task_id."""
    with _client() as c:
        r = c.post("/api/v1/report/classify/async", json=product_data)
        r.raise_for_status()
        return r.json()["task_id"]


def classify_batch_async(object_name: str) -> str:
    """POST /api/v1/report/classify/batch/async — batch from Excel. Returns task_id."""
    with _client() as c:
        r = c.post("/api/v1/report/classify/batch/async", json={"object_name": object_name})
        r.raise_for_status()
        return r.json()["task_id"]


def poll_task(task_id: str, endpoint: str) -> dict:
    """Poll a task status endpoint until terminal state. Returns full response."""
    elapsed = 0
    with _client() as c:
        while elapsed < MAX_POLL_TIME:
            r = c.get(endpoint.format(task_id=task_id))
            r.raise_for_status()
            data = r.json()
            status = data.get("status", "")
            logger.info("Poll %s — status=%s (elapsed=%ds)", task_id, status, elapsed)
            if status in TERMINAL_STATUSES:
                return data
            time.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL
    raise TimeoutError(f"Task {task_id} did not complete within {MAX_POLL_TIME}s")


def poll_process_task(task_id: str) -> dict:
    """Poll CHC process task."""
    return poll_task(task_id, "/api/v1/report/task/{task_id}")


def poll_classify_task(task_id: str) -> dict:
    """Poll single classify task."""
    return poll_task(task_id, "/api/v1/report/classify/async/{task_id}")


def poll_classify_batch_task(task_id: str) -> dict:
    """Poll batch classify task."""
    return poll_task(task_id, "/api/v1/report/classify/batch/task/{task_id}")


def download_result(download_url: str) -> bytes:
    """Download result file from a presigned URL."""
    with httpx.Client(timeout=120.0) as c:
        r = c.get(download_url)
        r.raise_for_status()
        return r.content
