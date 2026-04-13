"""Celery tasks for AI analysis via Report Service.

Two modes:
- Callback mode (BACKEND_BASE_URL set): submit task → return immediately.
  Report Service POSTs result to /requests/webhook/ai-result when done.
- Poll mode (fallback): submit task → poll every 5s for up to 10 min.
"""
import json
import logging

from worker import celery_app
from app.core.config import settings
from app.core.database import SessionLocal
from app.core import storage
from app.core import report_client
from app.models.request import Request, RequestFile, RequestStatus, RequestType
from app.requests import repository

logger = logging.getLogger(__name__)

_USE_CALLBACK = bool(settings.BACKEND_BASE_URL)

# CHC modules that map to Report Service input_sections
SECTION_MAP = {
    "tariff_classification": "tariff_classification",
    "customs_valuation": "customs_valuation",
    "non_tariff_measures": "non_tariff_measures",
    "exim_statistics": "exim_statistics",
}

# Manual E-Tariff field mapping: CHC schema → Report Service schema
CLASSIFY_FIELD_MAP = {
    "commodity_name": "product_name",
    "scientific_name": "science_name",
    "description": "product_description",
    "function": "function",
    "material_composition": "material",
    "structure_components": "structure",
    "technical_specification": "specifications",
}


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def run_ai_analysis(self, request_file_id: int):
    """Run AI analysis for a single request file via Report Service."""
    db = SessionLocal()
    try:
        rf = db.query(RequestFile).filter(RequestFile.id == request_file_id).first()
        if not rf:
            return

        request = db.query(Request).filter(Request.id == rf.request_id).first()
        if not request:
            return

        rf.ai_status = "running"
        db.commit()

        if request.type == RequestType.chc:
            _process_chc(db, rf, request)
        elif request.type == RequestType.etariff_manual:
            _process_manual_etariff(db, rf, request)
        elif request.type == RequestType.etariff_batch:
            _process_batch_etariff(db, rf, request)

        if not _USE_CALLBACK:
            # Poll mode: task completed synchronously, mark done here
            rf.ai_status = "completed"
            db.commit()

            all_files_done = all(f.ai_status == "completed" for f in request.files)
            if all_files_done:
                if request.type == RequestType.chc:
                    request.ai_draft_s3_key = rf.ai_s3_key
                    repository.update_status(db, request, RequestStatus.pending_assignment)
                    logger.info("CHC request %s → pending_assignment", request.display_id)
                    from app.core.email_service import send_wp_draft_ready
                    send_wp_draft_ready(db, request)
                elif request.type in (RequestType.etariff_manual, RequestType.etariff_batch):
                    repository.update_status(db, request, RequestStatus.delivered)
                    logger.info("E-Tariff request %s auto-delivered", request.display_id)

            logger.info("AI analysis completed for file %d (request %s)", rf.id, request.display_id)
        else:
            # Callback mode: result will arrive via webhook, just log
            logger.info("AI task submitted for file %d (request %s), awaiting callback", rf.id, request.display_id)

    except Exception as e:
        logger.exception("AI analysis failed for file %d: %s", request_file_id, e)
        db.rollback()
        rf = db.query(RequestFile).filter(RequestFile.id == request_file_id).first()
        if rf:
            rf.ai_status = "failed"
            db.commit()
        raise self.retry(exc=e)
    finally:
        db.close()


def _process_chc(db, rf: RequestFile, request: Request):
    """CHC order: pass s3_key → submit task (+ optional poll)."""
    input_sections = None
    if request.chc_modules:
        input_sections = [SECTION_MAP[m] for m in request.chc_modules if m in SECTION_MAP]

    task_id = report_client.process_async(rf.s3_key, input_sections or None)
    rf.ai_task_id = task_id
    db.commit()

    if not _USE_CALLBACK:
        result = report_client.poll_process_task(task_id)
        if result["status"] == "FAILURE":
            raise RuntimeError(f"Report Service failed: {result.get('error', 'unknown')}")
        rf.ai_s3_key = result["result"]["object_name"]


def _process_manual_etariff(db, rf: RequestFile, request: Request):
    """Manual E-Tariff: map form data → submit classify task (+ optional poll)."""
    input_data = json.loads(request.manual_input_data) if request.manual_input_data else {}
    product_data = {v: input_data.get(k, "") for k, v in CLASSIFY_FIELD_MAP.items()}

    task_id = report_client.classify_async(product_data)
    rf.ai_task_id = task_id
    db.commit()

    if not _USE_CALLBACK:
        result = report_client.poll_classify_task(task_id)
        if result["status"] == "FAILURE":
            raise RuntimeError(f"Classification failed: {result.get('error', 'unknown')}")
        task_result = result["result"]
        rf.ai_s3_key = task_result["object_name"]
        classification_data = {
            "hs_code": task_result.get("hs_code"),
            "classification_result": task_result.get("classification_result"),
        }
        rf.ai_result_data = json.dumps(classification_data, ensure_ascii=False)


def _process_batch_etariff(db, rf: RequestFile, request: Request):
    """Batch E-Tariff: pass s3_key → submit classify batch task (+ optional poll)."""
    task_id = report_client.classify_batch_async(rf.s3_key)
    rf.ai_task_id = task_id
    db.commit()

    if not _USE_CALLBACK:
        result = report_client.poll_classify_batch_task(task_id)
        if result["status"] == "FAILURE":
            raise RuntimeError(f"Batch classification failed: {result.get('error', 'unknown')}")
        rf.ai_s3_key = result["result"]["object_name"]


# ── SLA Monitoring (BRD v8) ──

@celery_app.task
def check_sla_compliance():
    """Hourly scan: warn at 48h, breach at 72h for requests in processing."""
    from datetime import datetime, timezone, timedelta
    from app.core.email_service import send_sla_warning, send_sla_breach

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        warning_threshold = now - timedelta(hours=48)
        breach_threshold = now - timedelta(hours=72)

        processing = db.query(Request).filter(
            Request.status == RequestStatus.processing,
            Request.assigned_at.isnot(None),
            Request.assigned_at < warning_threshold,
        ).all()

        for req in processing:
            hours = (now - req.assigned_at).total_seconds() / 3600
            if hours >= 72:
                send_sla_breach(db, req)
                logger.warning("SLA breach: %s (%.0fh)", req.display_id, hours)
            elif hours >= 48:
                send_sla_warning(db, req)
                logger.info("SLA warning: %s (%.0fh)", req.display_id, hours)
    except Exception as e:
        logger.exception("SLA check failed: %s", e)
    finally:
        db.close()
