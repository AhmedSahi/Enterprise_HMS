from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

# --- Department Schemas ---
class DepartmentBase(BaseModel):
    name: str

class DepartmentCreate(DepartmentBase):
    manager_id: Optional[int] = None

class DepartmentResponse(DepartmentBase):
    id: int
    manager_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# --- Appointment Schemas ---
class AppointmentBase(BaseModel):
    doctor_id: int
    scheduled_at: datetime

class AppointmentCreate(AppointmentBase):
    pass

class AppointmentResponse(AppointmentBase):
    id: int
    patient_id: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Prescription Schemas ---
class PrescriptionBase(BaseModel):
    diagnosis: str
    medicines_notes: str

class PrescriptionCreate(PrescriptionBase):
    appointment_id: int

class PrescriptionResponse(PrescriptionBase):
    id: int
    appointment_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)