from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from datetime import datetime
from sqlalchemy.orm import relationship
from src.models.base import Base

class AuditLog(Base):
    """Security audit logs to track user activities."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(100), nullable=False)  # e.g., 'LOGIN_SUCCESS'
    ip_address = Column(String(50), nullable=True)
    status = Column(String(50), nullable=False)     # 'SUCCESS' or 'FAILED'
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="audit_logs")