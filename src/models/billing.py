"""
MODULE 6: Billing & Finance
Tables: invoices, invoice_items, payments, insurance_providers, patient_insurance
"""
from enum import Enum as PyEnum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from src.models.base import Base, TimestampMixin


# ---------- Enums ----------
class InvoiceStatusEnum(str, PyEnum):
    UNPAID = "unpaid"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    CANCELLED = "cancelled"


class InvoiceItemTypeEnum(str, PyEnum):
    CONSULTATION = "consultation"
    ROOM = "room"
    MEDICINE = "medicine"
    LAB = "lab"
    OT = "ot"
    OTHER = "other"


class PaymentMethodEnum(str, PyEnum):
    CASH = "cash"
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"
    INSURANCE = "insurance"


class Invoice(Base, TimestampMixin):
    """
    A patient's bill. total_amount/paid_amount are running totals — the actual
    breakdown lives in InvoiceItem so charges can be itemized (consultation,
    room, medicine, etc.) instead of a single lump sum.
    """
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patient_details.id", ondelete="CASCADE"), nullable=False)
    admission_id = Column(Integer, ForeignKey("admissions.id", ondelete="SET NULL"), nullable=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True)
    total_amount = Column(Numeric(12, 2), nullable=False, default=0)
    paid_amount = Column(Numeric(12, 2), nullable=False, default=0)
    status = Column(Enum(InvoiceStatusEnum), nullable=False, default=InvoiceStatusEnum.UNPAID)

    patient = relationship("PatientDetails", foreign_keys=[patient_id])
    admission = relationship("Admission", back_populates="invoices")
    appointment = relationship("Appointment", back_populates="invoices")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")


class InvoiceItem(Base, TimestampMixin):
    """A single line item on an invoice."""
    __tablename__ = "invoice_items"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    item_type = Column(Enum(InvoiceItemTypeEnum), nullable=False)
    description = Column(String(255), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Numeric(10, 2), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)  # quantity * unit_price, stored for auditability

    invoice = relationship("Invoice", back_populates="items")


class Payment(Base, TimestampMixin):
    """A single payment transaction applied against an invoice."""
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    amount_paid = Column(Numeric(12, 2), nullable=False)
    payment_method = Column(Enum(PaymentMethodEnum), nullable=False)
    processed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    transaction_date = Column(DateTime(timezone=True), nullable=False)

    invoice = relationship("Invoice", back_populates="payments")
    processor = relationship("User", foreign_keys=[processed_by])


class InsuranceProvider(Base, TimestampMixin):
    """A TPA / insurance company."""
    __tablename__ = "insurance_providers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), unique=True, nullable=False)
    contact_info = Column(String(255), nullable=True)

    patient_policies = relationship("PatientInsurance", back_populates="provider")


class PatientInsurance(Base, TimestampMixin):
    """A patient's active insurance policy with a provider."""
    __tablename__ = "patient_insurance"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patient_details.id", ondelete="CASCADE"), nullable=False)
    provider_id = Column(Integer, ForeignKey("insurance_providers.id", ondelete="CASCADE"), nullable=False)
    policy_number = Column(String(100), nullable=False)
    coverage_details = Column(String(500), nullable=True)

    patient = relationship("PatientDetails", foreign_keys=[patient_id])
    provider = relationship("InsuranceProvider", back_populates="patient_policies")