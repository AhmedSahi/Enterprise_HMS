"""
MODULE 7: Blood Bank
Tables: blood_inventory, blood_requests
"""
from enum import Enum as PyEnum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from src.models.base import Base, TimestampMixin


class BloodRequestStatusEnum(str, PyEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class BloodInventory(Base, TimestampMixin):
    """Current stock for a single blood group. One row per group."""
    __tablename__ = "blood_inventory"

    id = Column(Integer, primary_key=True, index=True)
    blood_group = Column(String(5), unique=True, nullable=False)
    available_units = Column(Integer, nullable=False, default=0)
    last_updated = Column(DateTime(timezone=True), nullable=True)


class BloodRequest(Base, TimestampMixin):
    """A patient's request for blood units, going through an approval workflow."""
    __tablename__ = "blood_requests"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patient_details.id", ondelete="CASCADE"), nullable=False)
    requested_by_doctor_id = Column(Integer, ForeignKey("staff_details.id", ondelete="SET NULL"), nullable=True)
    blood_group = Column(String(5), nullable=False)
    units_required = Column(Integer, nullable=False)
    status = Column(Enum(BloodRequestStatusEnum), nullable=False, default=BloodRequestStatusEnum.PENDING)
    processed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    patient = relationship("PatientDetails", foreign_keys=[patient_id])
    requested_by_doctor = relationship("StaffDetails", foreign_keys=[requested_by_doctor_id])
    processor = relationship("User", foreign_keys=[processed_by])