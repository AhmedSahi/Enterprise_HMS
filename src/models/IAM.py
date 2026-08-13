"""
MODULE 1: IAM & Security
Tables: users, roles, permissions, user_roles, role_permissions,
        refresh_tokens, audit_logs
"""
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from src.models.base import Base, TimestampMixin

# --- Association tables (RBAC many-to-many, no extra columns needed) ---
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base, TimestampMixin):
    """Pure authentication identity — email + password + status."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    roles = relationship("Role", secondary=user_roles, back_populates="users")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")

    # One-to-one links into the Profiles module (module 2)
    profile = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    contact = relationship("UserContact", back_populates="user", uselist=False, cascade="all, delete-orphan")
    staff_detail = relationship("StaffDetails", back_populates="user", uselist=False, cascade="all, delete-orphan")
    patient_detail = relationship("PatientDetails", back_populates="user", uselist=False, cascade="all, delete-orphan")

    # Reverse link into the Infrastructure module (module 3)
    managed_departments = relationship("Department", back_populates="manager")


class Role(Base, TimestampMixin):
    """A named role, e.g. 'admin', 'doctor', 'patient', 'blood_bank_manager'."""
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)

    users = relationship("User", secondary=user_roles, back_populates="roles")
    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")


class Permission(Base, TimestampMixin):
    """A fine-grained permission code, e.g. 'bloodbank:approve'."""
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    code = Column(String(100), unique=True, nullable=False, index=True)

    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")


class RefreshToken(Base, TimestampMixin):
    """Stored refresh tokens so sessions can be revoked (logout / rotation)."""
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(500), unique=True, index=True, nullable=False)
    # Stored as a real DateTime (not String) so it can be compared/queried directly.
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="refresh_tokens")


class AuditLog(Base):
    """
    Immutable trail of sensitive actions. No TimestampMixin here — 'timestamp'
    already serves that purpose and audit rows are never updated (append-only).
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(255), nullable=False)
    resource_type = Column(String(100), nullable=True)  # e.g. "invoice", "prescription"
    resource_id = Column(Integer, nullable=True)
    ip_address = Column(String(45), nullable=True)  # long enough for IPv6
    status = Column(String(20), nullable=False, default="success")  # success | failure
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="audit_logs")