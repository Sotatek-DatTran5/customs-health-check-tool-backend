from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.user import User, UserRole
from app.submissions import service
from app.submissions.schemas import SubmissionResponse, UpdateResultRequest

router = APIRouter(tags=["submissions"])

expert_or_admin = require_roles(UserRole.expert, UserRole.tenant_admin)


# ── User site ──────────────────────────────────────────────

@router.post("", response_model=SubmissionResponse)
def upload(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.upload(db, files, current_user)


@router.get("/my", response_model=list[SubmissionResponse])
def get_my_submissions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return service.get_user_submissions(db, current_user.id)


@router.get("/my/{submission_id}", response_model=SubmissionResponse)
def get_my_submission(submission_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return service.get_submission(db, submission_id, current_user.tenant_id)


@router.get("/my/{submission_id}/files/{file_id}/result")
def get_result_url(submission_id: int, file_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return service.get_result_url(db, submission_id, file_id, current_user.id)


# ── Admin site ─────────────────────────────────────────────

@router.get("", response_model=list[SubmissionResponse])
def get_submissions(db: Session = Depends(get_db), current_user: User = Depends(expert_or_admin)):
    return service.get_tenant_submissions(db, current_user.tenant_id)


@router.get("/{submission_id}", response_model=SubmissionResponse)
def get_submission(submission_id: int, db: Session = Depends(get_db), current_user: User = Depends(expert_or_admin)):
    return service.get_submission(db, submission_id, current_user.tenant_id)


@router.get("/{submission_id}/files/{file_id}/download")
def download_file(submission_id: int, file_id: int, db: Session = Depends(get_db), current_user: User = Depends(expert_or_admin)):
    return service.download_file(submission_id, file_id, current_user.tenant_id, db)


@router.post("/{submission_id}/files/{file_id}/analyze")
def trigger_ai(submission_id: int, file_id: int, db: Session = Depends(get_db), current_user: User = Depends(expert_or_admin)):
    return service.trigger_ai(db, submission_id, file_id, current_user)


@router.post("/{submission_id}/analyze-all")
def analyze_all(submission_id: int, db: Session = Depends(get_db), current_user: User = Depends(expert_or_admin)):
    submission = service.get_submission(db, submission_id, current_user.tenant_id)
    results = []
    for file in submission.files:
        result = service.trigger_ai(db, submission_id, file.id, current_user)
        results.append(result)
    return results


@router.put("/{submission_id}/files/{file_id}/result")
def update_result(
    submission_id: int,
    file_id: int,
    payload: UpdateResultRequest = Depends(),
    uploaded_file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(expert_or_admin),
):
    return service.update_result(db, submission_id, file_id, payload, uploaded_file, current_user)


@router.post("/{submission_id}/files/{file_id}/publish")
def publish(submission_id: int, file_id: int, db: Session = Depends(get_db), current_user: User = Depends(expert_or_admin)):
    return service.publish(db, submission_id, file_id, current_user)
