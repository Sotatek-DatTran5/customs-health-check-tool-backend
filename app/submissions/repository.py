from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.submission import Submission, SubmissionFile, AnalysisJob, AIStatus, DeliveryStatus, SubmissionType


def count_by_tenant(db: Session, tenant_id: int) -> int:
    return db.query(Submission).filter(Submission.tenant_id == tenant_id).count()


def create_submission(db: Session, tenant_id: int, user_id: int, display_id: str, type: SubmissionType = SubmissionType.file_upload) -> Submission:
    submission = Submission(tenant_id=tenant_id, user_id=user_id, display_id=display_id, type=type)
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission


def create_file(db: Session, submission_id: int, filename: str, s3_key: str | None) -> SubmissionFile:
    file = SubmissionFile(submission_id=submission_id, original_filename=filename, s3_key=s3_key)
    db.add(file)
    db.commit()
    db.refresh(file)
    return file


def get_submissions_by_tenant(db: Session, tenant_id: int) -> list[Submission]:
    return db.query(Submission).filter(Submission.tenant_id == tenant_id).all()


def get_submissions_by_user(db: Session, user_id: int) -> list[Submission]:
    return db.query(Submission).filter(Submission.user_id == user_id).all()


def get_submission_by_id(db: Session, submission_id: int) -> Submission | None:
    return db.query(Submission).filter(Submission.id == submission_id).first()


def get_file_by_id(db: Session, file_id: int) -> SubmissionFile | None:
    return db.query(SubmissionFile).filter(SubmissionFile.id == file_id).first()


def create_analysis_job(db: Session, file_id: int, triggered_by: int) -> AnalysisJob:
    job = AnalysisJob(submission_file_id=file_id, triggered_by=triggered_by, status="queued")
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def update_file_ai_status(db: Session, file: SubmissionFile, ai_status: AIStatus, celery_task_id: str | None = None):
    file.ai_status = ai_status
    db.commit()


def publish_file(db: Session, file: SubmissionFile, reviewed_by: int, notes: str | None):
    file.delivery_status = DeliveryStatus.sent
    file.reviewed_by = reviewed_by
    file.notes = notes
    file.published_at = datetime.now(timezone.utc)
    db.commit()
