from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.request import Request, RequestFile, RequestStatus, RequestType


def count_by_tenant(db: Session, tenant_id: int) -> int:
    return db.query(Request).filter(Request.tenant_id == tenant_id).count()


def create_request(
    db: Session,
    tenant_id: int,
    user_id: int,
    display_id: str,
    type: RequestType = RequestType.chc,
    chc_modules: list[str] | None = None,
    manual_input_data: str | None = None,
) -> Request:
    req = Request(
        tenant_id=tenant_id,
        user_id=user_id,
        display_id=display_id,
        type=type,
        chc_modules=chc_modules,
        manual_input_data=manual_input_data,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def create_file(db: Session, request_id: int, filename: str, s3_key: str | None, file_size: int | None = None) -> RequestFile:
    f = RequestFile(request_id=request_id, original_filename=filename, s3_key=s3_key, file_size=file_size)
    db.add(f)
    db.commit()
    db.refresh(f)
    return f


def get_by_id(db: Session, request_id: int) -> Request | None:
    return db.query(Request).filter(Request.id == request_id).first()


def get_file_by_id(db: Session, file_id: int) -> RequestFile | None:
    return db.query(RequestFile).filter(RequestFile.id == file_id).first()


def get_by_user(db: Session, user_id: int) -> list[Request]:
    return db.query(Request).filter(Request.user_id == user_id).order_by(Request.submitted_at.desc()).all()


def get_by_tenant(db: Session, tenant_id: int) -> list[Request]:
    return db.query(Request).filter(Request.tenant_id == tenant_id).order_by(Request.submitted_at.desc()).all()


def get_by_expert(db: Session, expert_id: int) -> list[Request]:
    return db.query(Request).filter(Request.assigned_expert_id == expert_id).order_by(Request.submitted_at.desc()).all()


def update_status(db: Session, req: Request, status: RequestStatus):
    req.status = status
    now = datetime.now(timezone.utc)
    if status == RequestStatus.completed:
        req.completed_at = now
    elif status == RequestStatus.delivered:
        req.delivered_at = now
    elif status == RequestStatus.cancelled:
        req.cancelled_at = now
    req.updated_at = now
    db.commit()
    db.refresh(req)
    return req


def assign_expert(db: Session, req: Request, expert_id: int):
    req.assigned_expert_id = expert_id
    req.assigned_at = datetime.now(timezone.utc)
    req.status = RequestStatus.processing
    db.commit()
    db.refresh(req)
    return req
