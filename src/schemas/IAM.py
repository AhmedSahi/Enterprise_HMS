"""
MODULE 1 SCHEMAS: IAM & Security
Covers: signup/login, JWT tokens, roles, permissions, RBAC assignment, audit logs.
"""
import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from src.models.profile import GenderEnum
from src.schemas.profile import UserContactResponse, UserProfileResponse


# ---------- Password validation (shared) ----------
def _validate_password_complexity(value: str) -> str:
    """Enforce strict password complexity for security. Shared by signup schemas."""
    if not re.search(r"[A-Z]", value):
        raise ValueError("Password must contain at least one uppercase letter (A-Z).")
    if not re.search(r"[a-z]", value):
        raise ValueError("Password must contain at least one lowercase letter (a-z).")
    if not re.search(r"\d", value):
        raise ValueError("Password must contain at least one digit (0-9).")
    if not re.search(r"[@$!%*?&]", value):
        raise ValueError("Password must contain at least one special character (@$!%*?&).")
    return value


# ---------- Signup (atomic: User + UserProfile + UserContact together) ----------
class UserSignupRequest(BaseModel):
    """
    Single-request signup payload. Creates the User, UserProfile, and
    UserContact rows together in one DB transaction — there is intentionally
    NO separate 'create profile' or 'create contact' endpoint, since a user
    should never exist without this core identity/contact data in a
    hospital-grade system.
    """

    # --- Account credentials ---
    email: EmailStr = Field(..., description="User email address (used for login)", examples=["hafiz@example.com"])
    password: str = Field(
        ...,
        min_length=8,
        max_length=64,
        description="Must contain uppercase, lowercase, number, and special character.",
    )

    # --- Identity (-> user_profiles) ---
    first_name: str = Field(..., max_length=100, examples=["Hafiz"])
    last_name: str = Field(..., max_length=100, examples=["Sahi"])
    gender: GenderEnum
    dob: date = Field(..., description="Date of birth, format YYYY-MM-DD")
    cnic: str | None = Field(default=None, max_length=20, description="National ID number, optional")

    # --- Contact (-> user_contacts) ---
    primary_phone: str = Field(..., max_length=20, description="Primary contact number, required")
    secondary_phone: str | None = Field(default=None, max_length=20)
    address: str | None = None
    emergency_name: str | None = Field(default=None, max_length=150)
    emergency_phone: str | None = Field(default=None, max_length=20)

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, value: str) -> str:
        return _validate_password_complexity(value)


class UserSignupResponse(BaseModel):
    """Full response after signup: account + the profile/contact created alongside it."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    is_active: bool
    created_at: datetime
    profile: UserProfileResponse
    contact: UserContactResponse


# ---------- Users / Auth ----------
class UserCreate(BaseModel):
    """
    Minimal account-only schema — kept for internal/admin use only
    (e.g. seeding a system user). Regular signup MUST use UserSignupRequest.
    """

    email: EmailStr = Field(..., description="User email address", examples=["hafiz@example.com"])
    password: str = Field(..., min_length=8, max_length=64)

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, value: str) -> str:
        return _validate_password_complexity(value)


class UserLogin(BaseModel):
    """Schema for login request validation."""

    email: EmailStr
    password: str = Field(..., min_length=1)


class UserUpdate(BaseModel):
    """Partial update for account-level fields (not profile data)."""

    is_active: bool | None = None


class UserResponse(BaseModel):
    """Safe, public-facing user representation (never includes the password hash)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    is_active: bool
    created_at: datetime


class MessageResponse(BaseModel):
    """Generic message wrapper for simple confirmations."""
    message: str


# ---------- Tokens ----------
class Token(BaseModel):
    """Response returned on successful login or refresh."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Payload to exchange a refresh token for a new access token."""
    refresh_token: str = Field(..., description="The refresh token issued at login")


class TokenPayload(BaseModel):
    """Shape of a decoded JWT payload — used internally, not exposed via API."""
    sub: str | None = None
    type: str | None = None
    exp: int | None = None


# ---------- Roles & Permissions (RBAC) ----------
class RoleCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: str | None = None


class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None = None


class PermissionCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    code: str = Field(..., min_length=2, max_length=100, description="Unique code, e.g. 'bloodbank:approve'")


class PermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str


class RoleWithPermissionsResponse(RoleResponse):
    """Role response that also includes its granted permissions."""
    permissions: list[PermissionResponse] = []


class AssignRoleRequest(BaseModel):
    """Attach a role to a user."""
    user_id: int
    role_id: int


class AssignPermissionRequest(BaseModel):
    """Attach a permission to a role."""
    role_id: int
    permission_id: int


# ---------- Audit ----------
class AuditLogResponse(BaseModel):
    """Read-only view of an audit trail entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None = None
    action: str
    resource_type: str | None = None
    resource_id: int | None = None
    ip_address: str | None = None
    status: str
    timestamp: datetime
