from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.submissions import repository
from app.submissions.schemas import UpdateResultRequest
from app.models.submission import AIStatus
from app.models.user import User


def upload(db: Session, files: list[UploadFile], user: User) -> object:
    count = repository.count_by_tenant(db, user.tenant_id)
    display_id = f"{user.tenant.tenant_code}-{str(count + 1).zfill(3)}"

    submission = repository.create_submission(db, user.tenant_id, user.id, display_id)

    for file in files:
        s3_key = f"{user.tenant_id}/{user.id}/{submission.id}/{file.filename}"
        # TODO: upload file lên S3
        repository.create_file(db, submission.id, file.filename, s3_key)

    # TODO: gửi mail xác nhận (Celery task)
    return submission


def get_user_submissions(db: Session, user_id: int):
    return repository.get_submissions_by_user(db, user_id)


def get_submission(db: Session, submission_id: int, tenant_id: int):
    submission = repository.get_submission_by_id(db, submission_id)
    if not submission or submission.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    return submission


def get_tenant_submissions(db: Session, tenant_id: int):
    return repository.get_submissions_by_tenant(db, tenant_id)


def trigger_ai(db: Session, submission_id: int, file_id: int, current_user: User):
    submission = get_submission(db, submission_id, current_user.tenant_id)
    file = repository.get_file_by_id(db, file_id)

    if not file or file.submission_id != submission.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    if file.ai_status == AIStatus.running:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="AI analysis already running")

    job = repository.create_analysis_job(db, file.id, current_user.id)
    repository.update_file_ai_status(db, file, AIStatus.running)

    from app.submissions.tasks import run_ai_analysis
    task = run_ai_analysis.delay(file.id, job.id)

    return {"message": "AI analysis started", "task_id": task.id}


def download_file(submission_id: int, file_id: int, tenant_id: int, db: Session):
    submission = get_submission(db, submission_id, tenant_id)
    file = repository.get_file_by_id(db, file_id)

    if not file or file.submission_id != submission.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    # TODO: stream file từ S3
    pass


def update_result(db: Session, submission_id: int, file_id: int, payload: UpdateResultRequest, uploaded_file, current_user: User):
    submission = get_submission(db, submission_id, current_user.tenant_id)
    file = repository.get_file_by_id(db, file_id)

    if not file or file.submission_id != submission.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    if uploaded_file:
        expert_s3_key = f"{current_user.tenant_id}/results/{submission.id}/{file_id}/{uploaded_file.filename}"
        # TODO: upload file chỉnh sửa lên S3
        file.expert_s3_key = expert_s3_key

    if payload.notes:
        file.notes = payload.notes

    db.commit()


def publish(db: Session, submission_id: int, file_id: int, current_user: User):
    submission = get_submission(db, submission_id, current_user.tenant_id)
    file = repository.get_file_by_id(db, file_id)

    if not file or file.submission_id != submission.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    result_key = file.expert_s3_key or file.ai_s3_key
    if not result_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No result file available")

    # TODO: generate presigned URL 7 ngày
    # TODO: gửi mail cho user (Celery task)
    repository.publish_file(db, file, current_user.id, file.notes)
    return {"message": "Result published"}


def get_result_url(db: Session, submission_id: int, file_id: int, user_id: int):
    submission = repository.get_submission_by_id(db, submission_id)
    if not submission or submission.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    file = repository.get_file_by_id(db, file_id)
    if not file or file.submission_id != submission.id or not file.published_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not available")

    # TODO: generate presigned URL 7 ngày từ S3
    return {"url": "presigned_url_placeholder"}
