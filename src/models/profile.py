"""
MODULE 2: Unified Profiles & Identity
Tables: user_profiles, user_contacts, staff_details, patient_details,
        allergens, patient_allergies, patient_medical_history
"""
from enum import Enum as PyEnum

from sqlalchemy import (
    Column,
    Date,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from src.models.base import Base, TimestampMixin


# ---------- Enums ----------
class GenderEnum(str, PyEnum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class StaffTypeEnum(str, PyEnum):
    DOCTOR = "doctor"
    NURSE = "nurse"
    RECEPTIONIST = "receptionist"
    LAB_TECH = "lab_tech"
    PHARMACIST = "pharmacist"
    ADMIN = "admin"


class AllergenCategoryEnum(str, PyEnum):
    DRUG = "drug"
    FOOD = "food"
    ENVIRONMENTAL = "environmental"


class AllergySeverityEnum(str, PyEnum):
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"


class MedicalHistoryStatusEnum(str, PyEnum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    CHRONIC = "chronic"


# ---------- Common identity (every user has at most one of each) ----------
class UserProfile(Base, TimestampMixin):
    """Personal identity fields shared by all users (staff & patients alike)."""
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    gender = Column(Enum(GenderEnum), nullable=False)
    dob = Column(Date, nullable=False)
    cnic = Column(String(20), unique=True, nullable=True)

    user = relationship("User", back_populates="profile")


class UserContact(Base, TimestampMixin):
    """Contact details shared by all users."""
    __tablename__ = "user_contacts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    primary_phone = Column(String(20), nullable=False)
    secondary_phone = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    emergency_name = Column(String(150), nullable=True)
    emergency_phone = Column(String(20), nullable=True)

    user = relationship("User", back_populates="contact")


# ---------- Role-specific metadata ----------
class StaffDetails(Base, TimestampMixin):
    """Employment metadata for any staff member (doctor, nurse, admin, etc.)."""
    __tablename__ = "staff_details"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    employee_code = Column(String(50), unique=True, nullable=False)
    staff_type = Column(Enum(StaffTypeEnum), nullable=False)
    # Only meaningful for staff_type == DOCTOR; kept nullable for everyone else.
    specialization = Column(String(150), nullable=True)
    license_number = Column(String(100), unique=True, nullable=True)
    consultation_fee = Column(Numeric(10, 2), nullable=True)

    user = relationship("User", back_populates="staff_detail")
    department = relationship("Department", back_populates="staff_members")
    doctor_schedules = relationship("DoctorSchedule", back_populates="doctor", cascade="all, delete-orphan")


class PatientDetails(Base, TimestampMixin):
    """Hospital-specific metadata for a patient."""
    __tablename__ = "patient_details"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    patient_code = Column(String(50), unique=True, nullable=False)  # Medical Record Number (MRN)
    blood_group = Column(String(5), nullable=False)

    user = relationship("User", back_populates="patient_detail")
    allergies = relationship("PatientAllergy", back_populates="patient", cascade="all, delete-orphan")
    medical_history = relationship("PatientMedicalHistory", back_populates="patient", cascade="all, delete-orphan")


# ---------- Allergies (normalized, not a free-text summary) ----------
class Allergen(Base, TimestampMixin):
    """Master list of known allergens, reused across all patients."""
    __tablename__ = "allergens"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), unique=True, nullable=False)
    category = Column(Enum(AllergenCategoryEnum), nullable=False)

    patient_links = relationship("PatientAllergy", back_populates="allergen")


class PatientAllergy(Base, TimestampMixin):
    """Link table: which allergens a patient has, with severity."""
    __tablename__ = "patient_allergies"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patient_details.id", ondelete="CASCADE"), nullable=False)
    allergen_id = Column(Integer, ForeignKey("allergens.id", ondelete="CASCADE"), nullable=False)
    severity = Column(Enum(AllergySeverityEnum), nullable=False)
    reaction_notes = Column(Text, nullable=True)

    patient = relationship("PatientDetails", back_populates="allergies")
    allergen = relationship("Allergen", back_populates="patient_links")


class PatientMedicalHistory(Base, TimestampMixin):
    """Chronic/past conditions for a patient, independent of any single visit."""
    __tablename__ = "patient_medical_history"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patient_details.id", ondelete="CASCADE"), nullable=False)
    condition_name = Column(String(200), nullable=False)
    diagnosed_date = Column(Date, nullable=True)
    status = Column(Enum(MedicalHistoryStatusEnum), nullable=False, default=MedicalHistoryStatusEnum.ACTIVE)
    notes = Column(Text, nullable=True)

    patient = relationship("PatientDetails", back_populates="medical_history")