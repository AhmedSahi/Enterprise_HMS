"""
MODULE 4: Clinical & IPD
Tables: doctor_schedules, appointments, admissions, discharge_summaries,
        vitals_logs, ot_schedules, ot_team_members, diagnoses,
        prescriptions, prescription_items
"""
from enum import Enum as PyEnum

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
)
from sqlalchemy.orm import relationship

from src.models.base import Base, TimestampMixin


# ---------- Enums ----------
class AppointmentStatusEnum(str, PyEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AdmissionStatusEnum(str, PyEnum):
    ADMITTED = "admitted"
    DISCHARGED = "discharged"
    TRANSFERRED = "transferred"


class OTScheduleStatusEnum(str, PyEnum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class OTRoleEnum(str, PyEnum):
    ANESTHETIST = "anesthetist"
    ASSISTANT_SURGEON = "assistant_surgeon"
    SCRUB_NURSE = "scrub_nurse"


# ---------- Scheduling ----------
class DoctorSchedule(Base, TimestampMixin):
    """A doctor's weekly recurring availability window."""
    __tablename__ = "doctor_schedules"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("staff_details.id", ondelete="CASCADE"), nullable=False)
    day_of_week = Column(Integer, nullable=False)  # 0 = Monday ... 6 = Sunday
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    slot_duration_minutes = Column(Integer, nullable=False, default=30)

    doctor = relationship("StaffDetails", back_populates="doctor_schedules")


# ---------- OPD ----------
class Appointment(Base, TimestampMixin):
    """An OPD consultation booking."""
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patient_details.id", ondelete="CASCADE"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("staff_details.id", ondelete="CASCADE"), nullable=False)
    appointment_date = Column(Date, nullable=False)
    appointment_time = Column(Time, nullable=False)
    duration_minutes = Column(Integer, nullable=False, default=30)
    status = Column(Enum(AppointmentStatusEnum), nullable=False, default=AppointmentStatusEnum.PENDING)

    patient = relationship("PatientDetails", foreign_keys=[patient_id])
    doctor = relationship("StaffDetails", foreign_keys=[doctor_id])
    diagnoses = relationship("Diagnosis", back_populates="appointment")
    prescriptions = relationship("Prescription", back_populates="appointment")
    invoices = relationship("Invoice", back_populates="appointment")


# ---------- IPD ----------
class Admission(Base, TimestampMixin):
    """An in-patient (IPD) stay."""
    __tablename__ = "admissions"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patient_details.id", ondelete="CASCADE"), nullable=False)
    bed_id = Column(Integer, ForeignKey("beds.id", ondelete="RESTRICT"), nullable=False)
    admitted_by_doctor_id = Column(Integer, ForeignKey("staff_details.id", ondelete="SET NULL"), nullable=True)
    admission_date = Column(DateTime(timezone=True), nullable=False)
    discharge_date = Column(DateTime(timezone=True), nullable=True)
    status = Column(Enum(AdmissionStatusEnum), nullable=False, default=AdmissionStatusEnum.ADMITTED)

    patient = relationship("PatientDetails", foreign_keys=[patient_id])
    bed = relationship("Bed", back_populates="admissions")
    admitted_by_doctor = relationship("StaffDetails", foreign_keys=[admitted_by_doctor_id])
    bed_transfers = relationship("BedTransfer", back_populates="admission", cascade="all, delete-orphan")
    discharge_summary = relationship(
        "DischargeSummary", back_populates="admission", uselist=False, cascade="all, delete-orphan"
    )
    vitals_logs = relationship("VitalsLog", back_populates="admission")
    diagnoses = relationship("Diagnosis", back_populates="admission")
    prescriptions = relationship("Prescription", back_populates="admission")
    invoices = relationship("Invoice", back_populates="admission")


class DischargeSummary(Base, TimestampMixin):
    """Clinical summary written when an admission ends."""
    __tablename__ = "discharge_summaries"

    id = Column(Integer, primary_key=True, index=True)
    admission_id = Column(Integer, ForeignKey("admissions.id", ondelete="CASCADE"), unique=True, nullable=False)
    final_diagnosis = Column(Text, nullable=False)
    treatment_given = Column(Text, nullable=False)
    follow_up_instructions = Column(Text, nullable=True)
    discharged_by_doctor_id = Column(Integer, ForeignKey("staff_details.id", ondelete="SET NULL"), nullable=True)

    admission = relationship("Admission", back_populates="discharge_summary")
    discharged_by_doctor = relationship("StaffDetails", foreign_keys=[discharged_by_doctor_id])


class VitalsLog(Base, TimestampMixin):
    """A single set of vitals recorded for a patient (OPD or IPD)."""
    __tablename__ = "vitals_logs"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patient_details.id", ondelete="CASCADE"), nullable=False)
    admission_id = Column(Integer, ForeignKey("admissions.id", ondelete="CASCADE"), nullable=True)
    recorded_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    bp_systolic = Column(Integer, nullable=True)
    bp_diastolic = Column(Integer, nullable=True)
    temperature = Column(Numeric(4, 1), nullable=True)
    pulse = Column(Integer, nullable=True)
    spo2 = Column(Integer, nullable=True)
    recorded_at = Column(DateTime(timezone=True), nullable=False)

    patient = relationship("PatientDetails", foreign_keys=[patient_id])
    admission = relationship("Admission", back_populates="vitals_logs")
    recorder = relationship("User", foreign_keys=[recorded_by])


# ---------- Surgery ----------
class OTSchedule(Base, TimestampMixin):
    """A booked surgery slot in an operation theater."""
    __tablename__ = "ot_schedules"

    id = Column(Integer, primary_key=True, index=True)
    ot_id = Column(Integer, ForeignKey("operation_theaters.id", ondelete="CASCADE"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patient_details.id", ondelete="CASCADE"), nullable=False)
    lead_surgeon_id = Column(Integer, ForeignKey("staff_details.id", ondelete="SET NULL"), nullable=True)
    scheduled_start = Column(DateTime(timezone=True), nullable=False)
    scheduled_end = Column(DateTime(timezone=True), nullable=False)
    status = Column(Enum(OTScheduleStatusEnum), nullable=False, default=OTScheduleStatusEnum.SCHEDULED)

    operation_theater = relationship("OperationTheater", back_populates="ot_schedules")
    patient = relationship("PatientDetails", foreign_keys=[patient_id])
    lead_surgeon = relationship("StaffDetails", foreign_keys=[lead_surgeon_id])
    team_members = relationship("OTTeamMember", back_populates="ot_schedule", cascade="all, delete-orphan")


class OTTeamMember(Base, TimestampMixin):
    """A staff member assisting in a scheduled surgery (anesthetist, nurse, etc.)."""
    __tablename__ = "ot_team_members"

    id = Column(Integer, primary_key=True, index=True)
    ot_schedule_id = Column(Integer, ForeignKey("ot_schedules.id", ondelete="CASCADE"), nullable=False)
    staff_id = Column(Integer, ForeignKey("staff_details.id", ondelete="CASCADE"), nullable=False)
    role_in_surgery = Column(Enum(OTRoleEnum), nullable=False)

    ot_schedule = relationship("OTSchedule", back_populates="team_members")
    staff = relationship("StaffDetails", foreign_keys=[staff_id])


# ---------- Diagnosis & Prescriptions ----------
class Diagnosis(Base, TimestampMixin):
    """A structured (ICD-coded) diagnosis, tied to either an OPD visit or an IPD stay."""
    __tablename__ = "diagnoses"

    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id", ondelete="CASCADE"), nullable=True)
    admission_id = Column(Integer, ForeignKey("admissions.id", ondelete="CASCADE"), nullable=True)
    icd_code = Column(String(20), nullable=False)
    description = Column(String(255), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "appointment_id IS NOT NULL OR admission_id IS NOT NULL",
            name="ck_diagnosis_source_required",
        ),
    )

    appointment = relationship("Appointment", back_populates="diagnoses")
    admission = relationship("Admission", back_populates="diagnoses")


class Prescription(Base, TimestampMixin):
    """
    Prescription header. Supports BOTH OPD (via appointment_id) and IPD
    (via admission_id) patients — IPD patients don't always have an appointment.
    """
    __tablename__ = "prescriptions"

    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id", ondelete="CASCADE"), nullable=True)
    admission_id = Column(Integer, ForeignKey("admissions.id", ondelete="CASCADE"), nullable=True)
    doctor_id = Column(Integer, ForeignKey("staff_details.id", ondelete="SET NULL"), nullable=True)
    patient_id = Column(Integer, ForeignKey("patient_details.id", ondelete="CASCADE"), nullable=False)
    notes = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "appointment_id IS NOT NULL OR admission_id IS NOT NULL",
            name="ck_prescription_source_required",
        ),
    )

    appointment = relationship("Appointment", back_populates="prescriptions")
    admission = relationship("Admission", back_populates="prescriptions")
    doctor = relationship("StaffDetails", foreign_keys=[doctor_id])
    patient = relationship("PatientDetails", foreign_keys=[patient_id])
    items = relationship("PrescriptionItem", back_populates="prescription", cascade="all, delete-orphan")


class PrescriptionItem(Base, TimestampMixin):
    """A single medicine line within a prescription."""
    __tablename__ = "prescription_items"

    id = Column(Integer, primary_key=True, index=True)
    prescription_id = Column(Integer, ForeignKey("prescriptions.id", ondelete="CASCADE"), nullable=False)
    medication_id = Column(Integer, ForeignKey("medications.id", ondelete="RESTRICT"), nullable=False)
    dosage_instructions = Column(String(255), nullable=False)
    duration_days = Column(Integer, nullable=False)
    quantity = Column(Integer, nullable=False)

    prescription = relationship("Prescription", back_populates="items")
    medication = relationship("Medication", back_populates="prescription_items")