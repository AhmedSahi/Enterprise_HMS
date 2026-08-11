from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

class InvoiceBase(BaseModel):
    total_amount: float

class InvoiceCreate(InvoiceBase):
    patient_id: int
    appointment_id: Optional[int] = None

class InvoiceResponse(InvoiceBase):
    id: int
    patient_id: int
    appointment_id: Optional[int] = None
    paid_amount: float
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaymentCreate(BaseModel):
    invoice_id: int
    amount: float
    payment_method: str

class PaymentResponse(BaseModel):
    id: int
    invoice_id: int
    amount: float
    payment_method: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)