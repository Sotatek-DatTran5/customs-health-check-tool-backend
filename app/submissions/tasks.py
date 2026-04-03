from worker import celery_app
from app.core.database import SessionLocal
from app.core import storage
from app.models.submission import SubmissionFile, AnalysisJob, AIStatus


@celery_app.task(bind=True)
def run_ai_analysis(self, submission_file_id: int, job_id: int):
    db = SessionLocal()
    try:
        file = db.query(SubmissionFile).filter(SubmissionFile.id == submission_file_id).first()
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()

        if not file or not job:
            return

        if not file.s3_key:
            raise RuntimeError(f"No s3_key found for submission file {submission_file_id}")

        # TODO: download content from S3 → call AI API → upload result to S3 → save ai_s3_key
        # ai_s3_key = ...  # set after result is uploaded to S3

        file.ai_status = AIStatus.completed
        job.status = "success"
        db.commit()

    except Exception as e:
        if file:
            file.ai_status = AIStatus.failed
        if job:
            job.status = "failed"
            job.error_message = str(e)
        db.commit()
    finally:
        db.close()
