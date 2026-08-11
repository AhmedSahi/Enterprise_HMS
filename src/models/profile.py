from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from src.models.base import Base

class DoctorProfile(Base):
    __tablename__ = "doctor_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    specialization = Column(String(100), nullable=False)
    license_number = Column(String(50), unique=True, nullable=False)
    consultation_fee = Column(Float, nullable=False, default=0.0)

    # Optional back relationship to User model
    user = relationship("User", back_populates="doctor_profile")

    # DoctorProfile model ke andar
    appointments = relationship("Appointment", back_populates="doctor")



class PatientProfile(Base):
    __tablename__ = "patient_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    mrn = Column(String(50), unique=True, nullable=False)  # Medical Record Number
    blood_group = Column(String(5), nullable=False)
    emergency_contact = Column(String(20), nullable=True)

    # Optional back relationship to User model
    user = relationship("User", back_populates="patient_profile")

    # PatientProfile model ke andar
    appointments = relationship("Appointment", back_populates="patient")

    #invoice relationship
    invoice = relationship("Invoice", back_populates="patient", uselist = False , cascade="all, delete-orphan")
    #blood_requests relationship
    blood_requests = relationship("BloodRequest", back_populates="patient", cascade="all, delete-orphan")