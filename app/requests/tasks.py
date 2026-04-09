"""Celery tasks for AI analysis via Report Service."""
import json
import logging

from worker import celery_app
from app.core.database import SessionLocal
from app.core import storage
from app.core import report_client
from app.models.request import Request, RequestFile, RequestStatus, RequestType
from app.requests import repository

logger = logging.getLogger(__name__)

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


def _save_result(db, rf: RequestFile, result_s3_key: str):
    """Save the result S3 key from Report Service."""
    rf.ai_s3_key = result_s3_key


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

        rf.ai_status = "completed"
        db.commit()

        # E-Tariff is self-service: auto-deliver when AI completes (BRD 6.3)
        if request.type in (RequestType.etariff_manual, RequestType.etariff_batch):
            all_files_done = all(f.ai_status == "completed" for f in request.files)
            if all_files_done:
                repository.update_status(db, request, RequestStatus.delivered)
                logger.info("E-Tariff request %s auto-delivered", request.display_id)

        logger.info("AI analysis completed for file %d (request %s)", rf.id, request.display_id)

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
    """CHC order: pass s3_key → process/async → poll → save result s3_key."""
    input_sections = None
    if request.chc_modules:
        input_sections = [SECTION_MAP[m] for m in request.chc_modules if m in SECTION_MAP]

    task_id = report_client.process_async(rf.s3_key, input_sections or None)
    rf.ai_task_id = task_id
    db.commit()

    result = report_client.poll_process_task(task_id)
    if result["status"] == "FAILURE":
        raise RuntimeError(f"Report Service failed: {result.get('error', 'unknown')}")

    _save_result(db, rf, result["result"]["object_name"])


def _process_manual_etariff(db, rf: RequestFile, request: Request):
    """Manual E-Tariff: map form data → classify/async → poll → save result + structured data."""
    input_data = json.loads(request.manual_input_data) if request.manual_input_data else {}
    product_data = {v: input_data.get(k, "") for k, v in CLASSIFY_FIELD_MAP.items()}

    task_id = report_client.classify_async(product_data)
    rf.ai_task_id = task_id
    db.commit()

    result = report_client.poll_classify_task(task_id)
    if result["status"] == "FAILURE":
        raise RuntimeError(f"Classification failed: {result.get('error', 'unknown')}")

    task_result = result["result"]
    _save_result(db, rf, task_result["object_name"])

    # Save structured classification data for frontend display
    classification_data = {
        "hs_code": task_result.get("hs_code"),
        "classification_result": task_result.get("classification_result"),
    }
    rf.ai_result_data = json.dumps(classification_data, ensure_ascii=False)


def _process_batch_etariff(db, rf: RequestFile, request: Request):
    """Batch E-Tariff: pass s3_key → classify/batch/async → poll → save result s3_key."""
    task_id = report_client.classify_batch_async(rf.s3_key)
    rf.ai_task_id = task_id
    db.commit()

    result = report_client.poll_classify_batch_task(task_id)
    if result["status"] == "FAILURE":
        raise RuntimeError(f"Batch classification failed: {result.get('error', 'unknown')}")

    _save_result(db, rf, result["result"]["object_name"])
