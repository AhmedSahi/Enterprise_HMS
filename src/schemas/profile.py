from pydantic import BaseModel, ConfigDict
from typing import Optional

# --- Doctor Profile Schemas ---
class DoctorProfileBase(BaseModel):
    specialization: str
    license_number: str
    consultation_fee: float

class DoctorProfileCreate(DoctorProfileBase):
    pass

class DoctorProfileResponse(DoctorProfileBase):
    id: int
    user_id: int

    model_config = ConfigDict(from_attributes=True)


# --- Patient Profile Schemas ---
class PatientProfileBase(BaseModel):
    mrn: str
    blood_group: str
    emergency_contact: Optional[str] = None

class PatientProfileCreate(PatientProfileBase):
    pass

class PatientProfileResponse(PatientProfileBase):
    id: int
    user_id: int

    model_config = ConfigDict(from_attributes=True)