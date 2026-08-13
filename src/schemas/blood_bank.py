"""
MODULE 7 SCHEMAS: Blood Bank
Covers: stock levels per blood group and the request/approval workflow.
"""
from pydantic import BaseModel, ConfigDict, Field

from src.models.blood_bank import BloodRequestStatusEnum


class BloodInventoryUpdate(BaseModel):
    """Used by staff to set/adjust stock for a blood group."""
    blood_group: str = Field(..., max_length=5)
    available_units: int = Field(..., ge=0)


class BloodInventoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    blood_group: str
    available_units: int


class BloodRequestCreate(BaseModel):
    patient_id: int
    requested_by_doctor_id: int | None = None
    blood_group: str = Field(..., max_length=5)
    units_required: int = Field(..., gt=0)


class BloodRequestDecision(BaseModel):
    """Used by a manager to approve or reject a pending request."""
    status: BloodRequestStatusEnum


class BloodRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    patient_id: int
    requested_by_doctor_id: int | None = None
    blood_group: str
    units_required: int
    status: BloodRequestStatusEnum
    processed_by: int | None = None