from sqlalchemy.orm import Session

from app.models.user import User, UserRole


def get_all_in_tenant(db: Session, tenant_id: int) -> list[User]:
    return db.query(User).filter(
        User.tenant_id == tenant_id,
        User.role.in_([UserRole.user, UserRole.expert]),
    ).all()


def get_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def get_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def create(db: Session, **kwargs) -> User:
    user = User(**kwargs)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update(db: Session, user: User, **kwargs) -> User:
    for key, value in kwargs.items():
        if value is not None:
            setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user


def soft_delete(db: Session, user: User):
    user.is_active = False
    db.commit()
