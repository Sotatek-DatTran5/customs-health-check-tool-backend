"""Celery tasks for AI analysis via Report Service."""
import json
import logging

from worker import celery_app
from app.core.database import SessionLocal
from app.core import storage
from app.core import report_client
from app.models.request import Request, RequestFile, RequestType

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


def _upload_to_report_service(s3_key: str, filename: str) -> str:
    """Download from our S3, upload to Report Service MinIO. Returns object_name."""
    client = storage._get_s3_client()
    obj = client.get_object(Bucket=storage._bucket(), Key=s3_key)
    file_bytes = obj["Body"].read()

    info = report_client.get_upload_url(filename)
    report_client.upload_to_presigned_url(info["upload_url"], file_bytes)
    return info["object_name"]


def _save_result(db, rf: RequestFile, download_url: str, request: Request):
    """Download result from Report Service, save to our S3."""
    result_bytes = report_client.download_result(download_url)
    result_key = f"{request.tenant_id}/ai-results/{request.id}/{rf.id}/{rf.original_filename}"
    storage.upload_file(result_key, result_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    rf.ai_s3_key = result_key


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
    """CHC order: upload file → process/async → poll → save result."""
    object_name = _upload_to_report_service(rf.s3_key, rf.original_filename)

    input_sections = None
    if request.chc_modules:
        input_sections = [SECTION_MAP[m] for m in request.chc_modules if m in SECTION_MAP]

    task_id = report_client.process_async(object_name, input_sections or None)
    rf.ai_task_id = task_id
    db.commit()

    result = report_client.poll_process_task(task_id)
    if result["status"] == "FAILURE":
        raise RuntimeError(f"Report Service failed: {result.get('error', 'unknown')}")

    _save_result(db, rf, result["result"]["download_url"], request)


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
    _save_result(db, rf, task_result["download_url"], request)

    # Save structured classification data for frontend display
    classification_data = {
        "hs_code": task_result.get("hs_code"),
        "classification_result": task_result.get("classification_result"),
    }
    rf.ai_result_data = json.dumps(classification_data, ensure_ascii=False)


def _process_batch_etariff(db, rf: RequestFile, request: Request):
    """Batch E-Tariff: upload file → classify/batch/async → poll → save result."""
    object_name = _upload_to_report_service(rf.s3_key, rf.original_filename)

    task_id = report_client.classify_batch_async(object_name)
    rf.ai_task_id = task_id
    db.commit()

    result = report_client.poll_classify_batch_task(task_id)
    if result["status"] == "FAILURE":
        raise RuntimeError(f"Batch classification failed: {result.get('error', 'unknown')}")

    _save_result(db, rf, result["result"]["download_url"], request)
