"""HTTP client for Report Service (Excel Analysis API)."""
import time
import logging
import threading

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

POLL_INTERVAL = 5  # seconds between status checks
MAX_POLL_TIME = 600  # 10 minutes max wait

TERMINAL_STATUSES = {"SUCCESS", "FAILURE"}

# Token cache (shared across Celery workers in same process)
_token_lock = threading.Lock()
_cached_token: str | None = None


def _login() -> str:
    """Login to Report Service, return access_token."""
    with httpx.Client(base_url=settings.AI_API_URL, timeout=30.0) as c:
        r = c.post("/api/v1/auth/login", json={
            "username": settings.AI_API_USERNAME,
            "password": settings.AI_API_PASSWORD,
        })
        r.raise_for_status()
        token = r.json()["access_token"]
        logger.info("Report Service login successful")
        return token


def _get_token() -> str:
    """Get cached token or login for a new one."""
    global _cached_token
    with _token_lock:
        if not _cached_token:
            _cached_token = _login()
        return _cached_token


def _invalidate_token():
    """Clear cached token so next call triggers re-login."""
    global _cached_token
    with _token_lock:
        _cached_token = None


def _client() -> httpx.Client:
    token = _get_token()
    return httpx.Client(
        base_url=settings.AI_API_URL,
        headers={"Authorization": f"Bearer {token}"},
        timeout=60.0,
    )


def _request(method: str, url: str, **kwargs):
    """Make a request with auto-retry on 401 (token expired)."""
    with _client() as c:
        r = getattr(c, method)(url, **kwargs)
        if r.status_code == 401:
            _invalidate_token()
            # Retry with fresh token
            with _client() as c2:
                r = getattr(c2, method)(url, **kwargs)
        r.raise_for_status()
        return r


def _callback_url() -> str | None:
    """Build the webhook callback URL if BACKEND_BASE_URL is configured."""
    base = settings.BACKEND_BASE_URL.rstrip("/") if settings.BACKEND_BASE_URL else ""
    return f"{base}/requests/webhook/ai-result" if base else None


def process_async(object_name: str, input_sections: list[str] | None = None) -> str:
    """POST /api/v1/report/process/async — CHC analysis. Returns task_id."""
    body: dict = {"object_name": object_name, "callback_url": _callback_url()}
    if input_sections:
        body["input_sections"] = input_sections
    return _request("post", "/api/v1/report/process/async", json=body).json()["task_id"]


def classify_async(product_data: dict) -> str:
    """POST /api/v1/report/classify/async — single product. Returns task_id."""
    body = {**product_data, "callback_url": _callback_url()}
    return _request("post", "/api/v1/report/classify/async", json=body).json()["task_id"]


def classify_batch_async(object_name: str) -> str:
    """POST /api/v1/report/classify/batch/async — batch from Excel. Returns task_id."""
    body = {"object_name": object_name, "callback_url": _callback_url()}
    return _request("post", "/api/v1/report/classify/batch/async", json=body).json()["task_id"]


def poll_task(task_id: str, endpoint: str) -> dict:
    """Poll a task status endpoint until terminal state. Returns full response."""
    elapsed = 0
    while elapsed < MAX_POLL_TIME:
        data = _request("get", endpoint.format(task_id=task_id)).json()
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


