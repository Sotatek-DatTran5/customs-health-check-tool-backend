"""
Celery tasks for AI analysis (mock for now).
TODO: Replace with actual AI API call when available.
"""
from worker import celery_app
from app.core.database import SessionLocal
from app.models.request import RequestFile


@celery_app.task(bind=True)
def run_ai_analysis(self, request_file_id: int):
    """Mock AI analysis — marks file as completed after processing."""
    db = SessionLocal()
    try:
        f = db.query(RequestFile).filter(RequestFile.id == request_file_id).first()
        if not f:
            return

        f.ai_status = "running"
        db.commit()

        # TODO: Replace with actual AI API call:
        # 1. Download file from S3 using f.s3_key
        # 2. Send to AI API (settings.AI_API_URL)
        # 3. Upload result to S3
        # 4. Set f.ai_s3_key = result_s3_key

        # Mock: just mark as completed
        f.ai_status = "completed"
        db.commit()

    except Exception as e:
        if f:
            f.ai_status = "failed"
            db.commit()
        raise
    finally:
        db.close()
