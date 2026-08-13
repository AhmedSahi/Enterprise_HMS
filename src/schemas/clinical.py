"""
MODULE 4 SCHEMAS: Clinical & IPD
Covers: doctor scheduling, OPD appointments, IPD admissions, discharge,
vitals, surgery (OT), diagnoses, prescriptions.
"""
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.models.clinical import (
    AdmissionStatusEnum,
    AppointmentStatusEnum,
    OTRoleEnum,
    OTScheduleStatusEnum,
)


# ---------- Scheduling ----------
class DoctorScheduleCreate(BaseModel):
    doctor_id: int
    day_of_week: int = Field(..., ge=0, le=6, description="0 = Monday ... 6 = Sunday")
    start_time: time
    end_time: time
    slot_duration_minutes: int = Field(default=30, gt=0)


class DoctorScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    doctor_id: int
    day_of_week: int
    start_time: time
    end_time: time
    slot_duration_minutes: int


# ---------- OPD ----------
class AppointmentCreate(BaseModel):
    """Created by a patient (or reception) to book a doctor."""
    doctor_id: int
    appointment_date: date
    appointment_time: time
    duration_minutes: int = Field(default=30, gt=0)


class AppointmentStatusUpdate(BaseModel):
    status: AppointmentStatusEnum


class AppointmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    patient_id: int
    doctor_id: int
    appointment_date: date
    appointment_time: time
    duration_minutes: int
    status: AppointmentStatusEnum


# ---------- IPD ----------
class AdmissionCreate(BaseModel):
    patient_id: int
    bed_id: int
    admitted_by_doctor_id: int | None = None
    admission_date: datetime


class AdmissionStatusUpdate(BaseModel):
    status: AdmissionStatusEnum
    discharge_date: datetime | None = None


class AdmissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    patient_id: int
    bed_id: int
    admitted_by_doctor_id: int | None = None
    admission_date: datetime
    discharge_date: datetime | None = None
    status: AdmissionStatusEnum


class DischargeSummaryCreate(BaseModel):
    admission_id: int
    final_diagnosis: str
    treatment_given: str
    follow_up_instructions: str | None = None
    discharged_by_doctor_id: int | None = None


class DischargeSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    admission_id: int
    final_diagnosis: str
    treatment_given: str
    follow_up_instructions: str | None = None
    discharged_by_doctor_id: int | None = None


class VitalsLogCreate(BaseModel):
    """Either patient_id alone (OPD) or with admission_id (IPD) may be supplied."""
    patient_id: int
    admission_id: int | None = None
    bp_systolic: int | None = Field(default=None, gt=0)
    bp_diastolic: int | None = Field(default=None, gt=0)
    temperature: float | None = None
    pulse: int | None = Field(default=None, gt=0)
    spo2: int | None = Field(default=None, ge=0, le=100)
    recorded_at: datetime


class VitalsLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    patient_id: int
    admission_id: int | None = None
    recorded_by: int | None = None
    bp_systolic: int | None = None
    bp_diastolic: int | None = None
    temperature: float | None = None
    pulse: int | None = None
    spo2: int | None = None
    recorded_at: datetime


# ---------- Surgery ----------
class OTScheduleCreate(BaseModel):
    ot_id: int
    patient_id: int
    lead_surgeon_id: int | None = None
    scheduled_start: datetime
    scheduled_end: datetime

    @model_validator(mode="after")
    def check_time_order(self) -> "OTScheduleCreate":
        if self.scheduled_end <= self.scheduled_start:
            raise ValueError("scheduled_end must be after scheduled_start.")
        return self


class OTScheduleStatusUpdate(BaseModel):
    status: OTScheduleStatusEnum


class OTScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ot_id: int
    patient_id: int
    lead_surgeon_id: int | None = None
    scheduled_start: datetime
    scheduled_end: datetime
    status: OTScheduleStatusEnum


class OTTeamMemberCreate(BaseModel):
    ot_schedule_id: int
    staff_id: int
    role_in_surgery: OTRoleEnum


class OTTeamMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ot_schedule_id: int
    staff_id: int
    role_in_surgery: OTRoleEnum


# ---------- Diagnosis & prescriptions ----------
class DiagnosisCreate(BaseModel):
    """Exactly one of appointment_id / admission_id must be provided."""
    appointment_id: int | None = None
    admission_id: int | None = None
    icd_code: str = Field(..., max_length=20)
    description: str = Field(..., max_length=255)

    @model_validator(mode="after")
    def check_source(self) -> "DiagnosisCreate":
        if self.appointment_id is None and self.admission_id is None:
            raise ValueError("Provide at least one of appointment_id or admission_id.")
        return self


class DiagnosisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    appointment_id: int | None = None
    admission_id: int | None = None
    icd_code: str
    description: str


class PrescriptionItemCreate(BaseModel):
    medication_id: int
    dosage_instructions: str = Field(..., max_length=255)
    duration_days: int = Field(..., gt=0)
    quantity: int = Field(..., gt=0)


class PrescriptionItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    prescription_id: int
    medication_id: int
    dosage_instructions: str
    duration_days: int
    quantity: int


class PrescriptionCreate(BaseModel):
    """Exactly one of appointment_id / admission_id must be provided — supports OPD and IPD."""
    appointment_id: int | None = None
    admission_id: int | None = None
    patient_id: int
    notes: str | None = None
    items: list[PrescriptionItemCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_source(self) -> "PrescriptionCreate":
        if self.appointment_id is None and self.admission_id is None:
            raise ValueError("Provide at least one of appointment_id or admission_id.")
        return self


class PrescriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    appointment_id: int | None = None
    admission_id: int | None = None
    doctor_id: int | None = None
    patient_id: int
    notes: str | None = None
    items: list[PrescriptionItemResponse] = []