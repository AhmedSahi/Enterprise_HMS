from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from src.models.base import Base, TimestampMixin
from src.models.role import user_roles

class User(Base, TimestampMixin):
    """User core profile model."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)

    roles = relationship("Role", secondary=user_roles, back_populates="users")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")

    doctor_profile = relationship(
        "DoctorProfile", 
        back_populates="user", 
        uselist=False, 
        cascade="all, delete-orphan"
    )
    patient_profile = relationship(
        "PatientProfile", 
        back_populates="user", 
        uselist=False, 
        cascade="all, delete-orphan"
    )

    
    managed_departments = relationship("Department", back_populates="manager")

class RefreshToken(Base, TimestampMixin):
    """Refresh token storage for JWT session management."""
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(500), unique=True, index=True, nullable=False)
    expires_at = Column(String(100), nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="refresh_tokens")