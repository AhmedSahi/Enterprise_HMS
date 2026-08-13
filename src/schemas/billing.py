"""
MODULE 6 SCHEMAS: Billing & Finance
Covers: itemized invoices, payments, insurance providers and patient policies.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.models.billing import InvoiceItemTypeEnum, InvoiceStatusEnum, PaymentMethodEnum


class InvoiceItemCreate(BaseModel):
    item_type: InvoiceItemTypeEnum
    description: str = Field(..., max_length=255)
    quantity: int = Field(default=1, gt=0)
    unit_price: float = Field(..., gt=0)


class InvoiceItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    invoice_id: int
    item_type: InvoiceItemTypeEnum
    description: str
    quantity: int
    unit_price: float
    amount: float


class InvoiceCreate(BaseModel):
    """Exactly one of admission_id / appointment_id is expected (an invoice belongs to one visit)."""
    patient_id: int
    admission_id: int | None = None
    appointment_id: int | None = None
    items: list[InvoiceItemCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_single_source(self) -> "InvoiceCreate":
        if self.admission_id is not None and self.appointment_id is not None:
            raise ValueError("An invoice can be tied to either an admission or an appointment, not both.")
        return self


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    patient_id: int
    admission_id: int | None = None
    appointment_id: int | None = None
    total_amount: float
    paid_amount: float
    status: InvoiceStatusEnum
    items: list[InvoiceItemResponse] = []


class PaymentCreate(BaseModel):
    invoice_id: int
    amount_paid: float = Field(..., gt=0)
    payment_method: PaymentMethodEnum
    transaction_date: datetime


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    invoice_id: int
    amount_paid: float
    payment_method: PaymentMethodEnum
    processed_by: int | None = None
    transaction_date: datetime


class InsuranceProviderCreate(BaseModel):
    name: str = Field(..., max_length=200)
    contact_info: str | None = Field(default=None, max_length=255)


class InsuranceProviderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    contact_info: str | None = None


class PatientInsuranceCreate(BaseModel):
    patient_id: int
    provider_id: int
    policy_number: str = Field(..., max_length=100)
    coverage_details: str | None = Field(default=None, max_length=500)


class PatientInsuranceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    patient_id: int
    provider_id: int
    policy_number: str
    coverage_details: str | None = None