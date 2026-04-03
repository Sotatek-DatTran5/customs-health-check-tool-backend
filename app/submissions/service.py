import json
from datetime import datetime

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core import storage, email
from app.submissions import repository
from app.submissions.schemas import ManualInputRequest, SubmissionFileResponse, SubmissionResponse, UpdateResultRequest
from app.models.submission import AIStatus, DeliveryStatus, Submission, SubmissionFile, SubmissionType
from app.models.user import User


def upload(db: Session, files: list[UploadFile], user: User) -> object:
    count = repository.count_by_tenant(db, user.tenant_id)
    display_id = f"{user.tenant.tenant_code}-{str(count + 1).zfill(3)}"

    submission = repository.create_submission(db, user.tenant_id, user.id, display_id)

    for up_file in files:
        s3_key = f"{user.tenant_id}/{user.id}/{submission.id}/{up_file.filename}"
        content = up_file.file.read()
        storage.upload_file(s3_key, content, up_file.content_type or "application/octet-stream")
        repository.create_file(db, submission.id, up_file.filename, s3_key)

    email.send_email(
        to=user.email,
        subject=f"Submission {display_id} uploaded",
        body=f"Your submission {display_id} with {len(files)} file(s) has been received.",
    )
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


def get_tenant_submissions_filtered(
    db: Session,
    tenant_id: int,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    ai_status: AIStatus | None = None,
    delivery_status: DeliveryStatus | None = None,
    search: str | None = None,
) -> list:
    query = (
        db.query(Submission)
        .filter(Submission.tenant_id == tenant_id)
        .join(User, Submission.user_id == User.id)
        .join(SubmissionFile, Submission.id == SubmissionFile.submission_id)
    )

    if date_from:
        query = query.filter(Submission.submitted_at >= date_from)
    if date_to:
        query = query.filter(Submission.submitted_at <= date_to)
    if search:
        query = query.filter(
            or_(
                Submission.display_id.ilike(f"%{search}%"),
                SubmissionFile.original_filename.ilike(f"%{search}%"),
                User.full_name.ilike(f"%{search}%"),
            )
        )
    if ai_status:
        query = query.filter(SubmissionFile.ai_status == ai_status)
    if delivery_status:
        query = query.filter(SubmissionFile.delivery_status == delivery_status)

    return query.distinct().order_by(Submission.submitted_at.desc()).all()


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
    job.celery_task_id = task.id
    db.commit()

    return {"message": "AI analysis started", "task_id": task.id}


def download_file(submission_id: int, file_id: int, tenant_id: int, db: Session):
    submission = get_submission(db, submission_id, tenant_id)
    file = repository.get_file_by_id(db, file_id)

    if not file or file.submission_id != submission.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    if not file.s3_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found in storage")

    return storage.download_file_stream(file.s3_key)


def update_result(db: Session, submission_id: int, file_id: int, payload: UpdateResultRequest, uploaded_file, current_user: User):
    submission = get_submission(db, submission_id, current_user.tenant_id)
    file = repository.get_file_by_id(db, file_id)

    if not file or file.submission_id != submission.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    if uploaded_file:
        expert_s3_key = f"{current_user.tenant_id}/results/{submission.id}/{file_id}/{uploaded_file.filename}"
        content = uploaded_file.file.read()
        storage.upload_file(expert_s3_key, content, uploaded_file.content_type or "application/octet-stream")
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

    # Generate presigned URL (7 days)
    presigned_url = storage.generate_presigned_url(result_key, expires_in=604800)

    # Send result email to submitting user
    submission_user = db.query(User).filter(User.id == submission.user_id).first()
    if submission_user:
        email.send_email(
            to=submission_user.email,
            subject=f"Result ready for {submission.display_id}",
            body=(
                f"Your submission {submission.display_id} has a new result available.\n\n"
                f"Download link (valid 7 days): {presigned_url}"
            ),
        )

    repository.publish_file(db, file, current_user.id, file.notes)
    return {"message": "Result published"}


def create_manual_submission(db: Session, data: ManualInputRequest, user: User) -> SubmissionResponse:
    # 1. Calculate display_id
    count = repository.count_by_tenant(db, user.tenant_id)
    display_id = f"{user.tenant.tenant_code}-{str(count + 1).zfill(3)}"

    # 2. Create Submission record
    submission = repository.create_submission(
        db, user.tenant_id, user.id, display_id, type=SubmissionType.manual_input
    )

    # 3. Generate structured text content (Phase 1 stub — JSON as text)
    content = {
        "commodity_name": data.commodity_name,
        "description": data.description,
        "function": data.function,
        "structure_components": data.structure_components,
        "material_composition": data.material_composition,
        "technical_specification": data.technical_specification,
        "additional_notes": data.additional_notes,
    }
    filename = f"manual_input_{display_id}.json"
    s3_key = f"{user.tenant_id}/{user.id}/{submission.id}/{filename}"
    content_bytes = json.dumps(content, ensure_ascii=False, indent=2).encode("utf-8")
    storage.upload_file(s3_key, content_bytes, "application/json")

    file = repository.create_file(db, submission.id, filename, s3_key)

    # Send confirmation email
    email.send_email(
        to=user.email,
        subject=f"Manual submission {display_id} received",
        body=(
            f"Your manual input submission {display_id} has been received.\n\n"
            f"Commodity: {data.commodity_name}"
        ),
    )

    # 7. Return SubmissionResponse
    return SubmissionResponse(
        id=submission.id,
        display_id=submission.display_id,
        type=submission.type.value,
        submitted_at=submission.submitted_at,
        files=[
            SubmissionFileResponse(
                id=file.id,
                submission_id=file.submission_id,
                original_filename=file.original_filename,
                ai_status=file.ai_status,
                delivery_status=file.delivery_status,
                published_at=file.published_at,
                created_at=file.created_at,
            )
        ],
    )


def get_result_url(db: Session, submission_id: int, file_id: int, user_id: int):
    submission = repository.get_submission_by_id(db, submission_id)
    if not submission or submission.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    file = repository.get_file_by_id(db, file_id)
    if not file or file.submission_id != submission.id or not file.published_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not available")

    result_key = file.expert_s3_key or file.ai_s3_key
    if not result_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not available")
    url = storage.generate_presigned_url(result_key, expires_in=604800)
    return {"url": url}
