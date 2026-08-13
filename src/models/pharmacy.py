"""
MODULE 5: Pharmacy & Inventory
Tables: medications, medication_batches
"""
from sqlalchemy import Column, Date, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import relationship

from src.models.base import Base, TimestampMixin


class Medication(Base, TimestampMixin):
    """Drug catalog entry. Stock/expiry data lives separately in MedicationBatch."""
    __tablename__ = "medications"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    generic_name = Column(String(200), nullable=True)
    dosage_form = Column(String(50), nullable=False)  # tablet, syrup, injection...
    strength = Column(String(50), nullable=False)  # e.g. "500mg"
    unit_price = Column(Numeric(10, 2), nullable=False)

    batches = relationship("MedicationBatch", back_populates="medication", cascade="all, delete-orphan")
    prescription_items = relationship("PrescriptionItem", back_populates="medication")


class MedicationBatch(Base, TimestampMixin):
    """
    A physical batch of stock for a medication, with its own expiry date.
    Split from Medication so expired stock can be tracked/excluded correctly.
    """
    __tablename__ = "medication_batches"

    id = Column(Integer, primary_key=True, index=True)
    medication_id = Column(Integer, ForeignKey("medications.id", ondelete="CASCADE"), nullable=False)
    batch_number = Column(String(100), nullable=False)
    expiry_date = Column(Date, nullable=False)
    quantity_available = Column(Integer, nullable=False, default=0)
    supplier_name = Column(String(200), nullable=True)

    __table_args__ = (UniqueConstraint("medication_id", "batch_number", name="uq_medication_batch"),)

    medication = relationship("Medication", back_populates="batches")