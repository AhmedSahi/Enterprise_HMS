from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from src.models.base import Base

class BloodInventory(Base):
    __tablename__ = "blood_inventory"

    id = Column(Integer, primary_key=True, index=True)
    blood_group = Column(String(5), unique=True, nullable=False)  # e.g., A+, O-, B+
    units_available = Column(Integer, default=0, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BloodRequest(Base):
    __tablename__ = "blood_requests"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False)
    blood_group = Column(String(5), nullable=False)
    units_requested = Column(Integer, nullable=False)
    status = Column(String(20), default="pending")  # pending, approved, rejected, fulfilled
    created_at = Column(DateTime, default=datetime.utcnow)

    patient = relationship("PatientProfile" , back_populates = "blood_requests")