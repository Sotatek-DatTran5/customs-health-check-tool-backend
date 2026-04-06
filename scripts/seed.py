"""
Seed script — creates super_admin user if not exists.
Run: uv run python scripts/seed.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal, engine, Base
from app.core.security import hash_password
from app.models.user import User, UserRole
import app.models  # noqa: ensure all models loaded


def seed():
    # Create tables if they don't exist (fallback if no migration)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.role == UserRole.super_admin).first()
        if existing:
            print(f"[SKIP] Super admin already exists: {existing.email}")
            return

        admin = User(
            email="admin@chc.com",
            full_name="Super Admin",
            password_hash=hash_password("Admin@123"),
            role=UserRole.super_admin,
            tenant_id=None,
            is_first_login=False,
        )
        db.add(admin)
        db.commit()
        print("[OK] Super admin created: admin@chc.com / Admin@123")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
