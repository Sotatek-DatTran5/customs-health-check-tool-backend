"""
Shared test fixtures: test database, test client, auth helpers.
Uses the real PostgreSQL (Docker) with a separate test DB.
"""
import os

# Override settings BEFORE any app import
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://user:password@localhost:5433/chc_test",
)
os.environ["REDIS_URL"] = "redis://localhost:6379/15"  # separate DB for tests
os.environ["CELERY_BROKER_URL"] = "redis://localhost:6379/15"
os.environ["SMTP_HOST"] = ""  # disable real email sending
os.environ["AWS_ENDPOINT_URL"] = "http://localhost:4566"

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from httpx import AsyncClient, ASGITransport
from fastapi.testclient import TestClient

from app.core.database import Base, get_db
from app.core.security import hash_password, create_access_token
from app.main import app
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.models.request import Request, RequestFile, RequestStatus, RequestType

# --- Test DB engine ---
TEST_DB_URL = os.environ["DATABASE_URL"]
# Create test DB if not exists
_admin_url = TEST_DB_URL.rsplit("/", 1)[0] + "/postgres"
_admin_engine = create_engine(_admin_url, isolation_level="AUTOCOMMIT")
with _admin_engine.connect() as conn:
    exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname='chc_test'")).fetchone()
    if not exists:
        conn.execute(text("CREATE DATABASE chc_test"))
_admin_engine.dispose()

engine = create_engine(TEST_DB_URL)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Create all tables once per test session."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    """Per-test DB session with rollback."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestSession(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db):
    """FastAPI test client with DB override."""
    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app, headers={"host": "localhost"}) as c:
        yield c
    app.dependency_overrides.clear()


# --- Data fixtures ---

@pytest.fixture()
def tenant(db) -> Tenant:
    t = Tenant(
        name="Test Corp",
        tenant_code="TEST",
        subdomain="test",
        is_active=True,
        etariff_daily_limit=10,
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture()
def super_admin(db) -> User:
    u = User(
        email="superadmin@chc.com",
        full_name="Super Admin",
        password_hash=hash_password("Admin@123"),
        role=UserRole.super_admin,
        tenant_id=None,
    )
    db.add(u)
    db.flush()
    return u


@pytest.fixture()
def admin_user(db, tenant) -> User:
    u = User(
        email="admin@test.com",
        full_name="Tenant Admin",
        password_hash=hash_password("Admin@123"),
        role=UserRole.tenant_admin,
        tenant_id=tenant.id,
    )
    db.add(u)
    db.flush()
    return u


@pytest.fixture()
def normal_user(db, tenant) -> User:
    u = User(
        email="user@test.com",
        full_name="Test User",
        password_hash=hash_password("User@1234"),
        role=UserRole.user,
        tenant_id=tenant.id,
    )
    db.add(u)
    db.flush()
    return u


@pytest.fixture()
def expert_user(db) -> User:
    u = User(
        email="expert@chc.com",
        full_name="Test Expert",
        password_hash=hash_password("Expert@123"),
        role=UserRole.expert,
        tenant_id=None,
    )
    db.add(u)
    db.flush()
    return u


def make_token(user: User) -> str:
    """Generate a valid access token for a user."""
    return create_access_token({
        "user_id": user.id,
        "tenant_id": user.tenant_id,
        "role": user.role.value,
    })


def auth_header(user: User) -> dict:
    """Return Authorization header for a user."""
    return {"Authorization": f"Bearer {make_token(user)}"}
