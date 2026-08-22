"""
MODULE 7 SCHEMAS: Blood Bank
Covers: stock levels per blood group and the request/approval workflow.
"""
from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.models.blood_bank import BloodRequestStatusEnum


def validate_blood_group(cls, value: str) -> str:
    """Validate that the blood group is one of the allowed values."""
    allowed = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}
    if value not in allowed:
        raise ValueError(f"Invalid blood group: {value}. Must be one of {allowed}.")
    return value


class BloodInventoryUpdate(BaseModel):
    """Used by staff to set/adjust stock for a blood group."""
    blood_group: str = Field(..., max_length=5)
    available_units: int = Field(..., ge=0)

    @field_validator("blood_group")
    @classmethod
    def validate_bg(cls, value: str) -> str:
        return validate_blood_group(cls, value)


class BloodInventoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    blood_group: str
    available_units: int
    last_updated_by: int | None = None

   
class BloodRequestCreate(BaseModel):
    patient_id: int
    requested_by_doctor_id: int | None = None
    blood_group: str = Field(..., max_length=5)
    units_required: int = Field(..., gt=0)

    @field_validator("blood_group")
    @classmethod
    def validate_bg(cls, value: str) -> str:
        return validate_blood_group(cls, value)


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

    