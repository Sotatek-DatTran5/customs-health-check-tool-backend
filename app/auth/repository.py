from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.password_reset_token import PasswordResetToken


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email, User.is_active == True).first()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id, User.is_active == True).first()


def update_last_login(db: Session, user: User):
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()


def update_password(db: Session, user: User, password_hash: str):
    user.password_hash = password_hash
    db.commit()


def create_reset_token(db: Session, user_id: int, token: str, expires_at: datetime) -> PasswordResetToken:
    reset_token = PasswordResetToken(user_id=user_id, token=token, expires_at=expires_at)
    db.add(reset_token)
    db.commit()
    db.refresh(reset_token)
    return reset_token


def get_reset_token(db: Session, token: str) -> PasswordResetToken | None:
    return db.query(PasswordResetToken).filter(
        PasswordResetToken.token == token,
        PasswordResetToken.used_at == None,
        PasswordResetToken.expires_at > datetime.now(timezone.utc),
    ).first()


def mark_reset_token_used(db: Session, reset_token: PasswordResetToken):
    reset_token.used_at = datetime.now(timezone.utc)
    db.commit()
