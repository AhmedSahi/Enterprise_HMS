"""
MODULE 5 SCHEMAS: Pharmacy & Inventory
Covers: medication catalog and batch-level stock (with expiry).
"""
from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class MedicationCreate(BaseModel):
    name: str = Field(..., max_length=200)
    generic_name: str | None = Field(default=None, max_length=200)
    dosage_form: str = Field(..., max_length=50)
    strength: str = Field(..., max_length=50)
    unit_price: float = Field(..., gt=0)


class MedicationUpdate(BaseModel):
    unit_price: float | None = Field(default=None, gt=0)


class MedicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    generic_name: str | None = None
    dosage_form: str
    strength: str
    unit_price: float


class MedicationBatchCreate(BaseModel):
    medication_id: int
    batch_number: str = Field(..., max_length=100)
    expiry_date: date
    quantity_available: int = Field(..., ge=0)
    supplier_name: str | None = Field(default=None, max_length=200)


class MedicationBatchUpdate(BaseModel):
    quantity_available: int | None = Field(default=None, ge=0)


class MedicationBatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    medication_id: int
    batch_number: str
    expiry_date: date
    quantity_available: int
    supplier_name: str | None = None