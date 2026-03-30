from worker import celery_app
from app.core.database import SessionLocal
from app.models.submission import SubmissionFile, AnalysisJob, AIStatus


@celery_app.task(bind=True)
def run_ai_analysis(self, submission_file_id: int, job_id: int):
    db = SessionLocal()
    try:
        file = db.query(SubmissionFile).filter(SubmissionFile.id == submission_file_id).first()
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()

        if not file or not job:
            return

        # TODO: tải file từ S3
        # TODO: gọi AI API
        # TODO: nhận file kết quả và lưu lên S3
        # TODO: cập nhật ai_s3_key vào submission_file

        file.ai_status = AIStatus.completed
        job.status = "success"
        db.commit()

    except Exception as e:
        file.ai_status = AIStatus.failed
        job.status = "failed"
        job.error_message = str(e)
        db.commit()
    finally:
        db.close()
