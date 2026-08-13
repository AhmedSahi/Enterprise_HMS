"""
MODULE 2 SCHEMAS: Unified Profiles & Identity
Covers: identity, contact, staff/patient metadata, allergies, medical history.
"""
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from src.models.profile import (
    AllergenCategoryEnum,
    AllergySeverityEnum,
    GenderEnum,
    MedicalHistoryStatusEnum,
    StaffTypeEnum,
)


# ---------- Common identity ----------
class UserProfileCreate(BaseModel):
    user_id: int
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    gender: GenderEnum
    dob: date
    cnic: str | None = Field(default=None, max_length=20)


class UserProfileUpdate(BaseModel):
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    gender: GenderEnum | None = None
    dob: date | None = None
    cnic: str | None = Field(default=None, max_length=20)


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: GenderEnum
    dob: date
    cnic: str | None = None


class UserContactCreate(BaseModel):
    user_id: int
    primary_phone: str = Field(..., max_length=20)
    secondary_phone: str | None = Field(default=None, max_length=20)
    address: str | None = None
    emergency_name: str | None = Field(default=None, max_length=150)
    emergency_phone: str | None = Field(default=None, max_length=20)


class UserContactUpdate(BaseModel):
    primary_phone: str | None = Field(default=None, max_length=20)
    secondary_phone: str | None = Field(default=None, max_length=20)
    address: str | None = None
    emergency_name: str | None = Field(default=None, max_length=150)
    emergency_phone: str | None = Field(default=None, max_length=20)


class UserContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    primary_phone: str
    secondary_phone: str | None = None
    address: str | None = None
    emergency_name: str | None = None
    emergency_phone: str | None = None


# ---------- Staff ----------
class StaffDetailsCreate(BaseModel):
    user_id: int
    department_id: int | None = None
    employee_code: str = Field(..., max_length=50)
    staff_type: StaffTypeEnum
    specialization: str | None = Field(default=None, max_length=150)
    license_number: str | None = Field(default=None, max_length=100)
    consultation_fee: float | None = Field(default=None, gt=0)


class StaffDetailsUpdate(BaseModel):
    department_id: int | None = None
    specialization: str | None = Field(default=None, max_length=150)
    consultation_fee: float | None = Field(default=None, gt=0)


class StaffDetailsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    department_id: int | None = None
    employee_code: str
    staff_type: StaffTypeEnum
    specialization: str | None = None
    license_number: str | None = None
    consultation_fee: float | None = None


# ---------- Patient ----------
class PatientDetailsCreate(BaseModel):
    user_id: int
    patient_code: str = Field(..., max_length=50, description="Medical Record Number (MRN)")
    blood_group: str = Field(..., max_length=5)


class PatientDetailsUpdate(BaseModel):
    blood_group: str | None = Field(default=None, max_length=5)


class PatientDetailsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    patient_code: str
    blood_group: str


# ---------- Allergies ----------
class AllergenCreate(BaseModel):
    name: str = Field(..., max_length=150)
    category: AllergenCategoryEnum


class AllergenResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: AllergenCategoryEnum


class PatientAllergyCreate(BaseModel):
    patient_id: int
    allergen_id: int
    severity: AllergySeverityEnum
    reaction_notes: str | None = None


class PatientAllergyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    allergen_id: int
    severity: AllergySeverityEnum
    reaction_notes: str | None = None


# ---------- Medical history ----------
class PatientMedicalHistoryCreate(BaseModel):
    patient_id: int
    condition_name: str = Field(..., max_length=200)
    diagnosed_date: date | None = None
    status: MedicalHistoryStatusEnum = MedicalHistoryStatusEnum.ACTIVE
    notes: str | None = None


class PatientMedicalHistoryUpdate(BaseModel):
    status: MedicalHistoryStatusEnum | None = None
    notes: str | None = None


class PatientMedicalHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    condition_name: str
    diagnosed_date: date | None = None
    status: MedicalHistoryStatusEnum
    notes: str | None = None