"""
Shared pytest fixtures.

Key idea: every single test function gets its OWN fresh, empty, in-memory
SQLite database (see the `engine` fixture below). Nothing persists between
tests — so tests can never interfere with each other or depend on run order.
This mirrors FastAPI's official recommended testing pattern.
"""
import os
from datetime import date

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.core.database import get_db
from src.core.security import get_password_hash  
from main import app
from src.models import *  # noqa: F401,F403 -- registers every model before tables are created
from src.models.base import Base
from src.models.IAM import Permission, Role, User
from src.models.profile import UserContact, UserProfile

# The full default permission set (mirrors src/scripts/seed_admin.py)
DEFAULT_PERMISSIONS = [
    ("Manage Users", "iam:manage_users"),
    ("View Users", "iam:view_users"),
    ("Manage Roles", "iam:manage_roles"),
    ("Manage Permissions", "iam:manage_permissions"),
    ("View Audit Logs", "iam:view_audit_logs"),
    ("Manage Staff Profiles", "profiles:manage_staff"),
    ("View Staff Profiles", "profiles:view_staff"),
    ("Manage Patient Profiles", "profiles:manage_patients"),
    ("View Patient Profiles", "profiles:view_patients"),
    ("Manage Allergens", "profiles:manage_allergens"),
    ("Manage Patient Allergies", "profiles:manage_patient_allergies"),
    ("Manage Medical History", "profiles:manage_medical_history"),
    ("Manage Departments", "infrastructure:manage_departments"),
    ("Manage Wards", "infrastructure:manage_wards"),
    ("Manage Rooms", "infrastructure:manage_rooms"),
    ("Manage Beds", "infrastructure:manage_beds"),
    ("Manage Operation Theaters", "infrastructure:manage_ot"),
]


@pytest.fixture()
def engine():
    """A brand-new in-memory SQLite database, alive only for one test."""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # keeps the same in-memory DB alive across connections within this test
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)


@pytest.fixture()
def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture()
def client(engine, session_factory):
    """A FastAPI TestClient wired to the fresh per-test database."""

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def seed_superadmin(session_factory):
    """
    Directly seeds a superuser + every default permission + the admin role,
    exactly like src/scripts/seed_admin.py does — but in-process, so it's
    instant and doesn't touch a real database.
    """
    db = session_factory()
    user = User(
        email="superadmin@hms.com",
        hashed_password=get_password_hash("SuperAdmin123!"),
        is_active=True,
        is_superuser=True,
    )
    db.add(user)
    db.flush()
    db.add(UserProfile(user_id=user.id, first_name="Super", last_name="Admin", gender="other", dob=date(1990, 1, 1)))
    db.add(UserContact(user_id=user.id, primary_phone="0000000000"))

    perm_objs = []
    for name, code in DEFAULT_PERMISSIONS:
        perm = Permission(name=name, code=code)
        db.add(perm)
        db.flush()
        perm_objs.append(perm)

    admin_role = Role(name="admin", description="Full system access")
    db.add(admin_role)
    db.flush()
    admin_role.permissions.extend(perm_objs)
    user.roles.append(admin_role)

    db.commit()
    db.close()


@pytest.fixture()
def superadmin_token(client, seed_superadmin):
    """Logs in as the seeded superadmin and returns a bearer access token."""
    resp = client.post("/api/v1/auth/login", json={"email": "superadmin@hms.com", "password": "SuperAdmin123!"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture()
def auth_headers(superadmin_token):
    return {"Authorization": f"Bearer {superadmin_token}"}


def signup_plain_user(client, email: str, phone: str = "03000000000") -> dict:
    """Helper: sign up a normal (no roles, no permissions) user for tests that need one."""
    resp = client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "Plain123!",
            "first_name": "Test",
            "last_name": "User",
            "gender": "male",
            "dob": "1995-01-01",
            "primary_phone": phone,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()
