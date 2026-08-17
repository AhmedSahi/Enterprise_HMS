"""
Central import point for all ORM models across the 7 modules.
Import this package (or `from src.models import *`) in Alembic's env.py
so every model is registered on Base.metadata before autogenerate runs.
"""
from src.models.base import Base

# Module 1: IAM & Security
from src.models.IAM import User, Role, Permission, RefreshToken, AuditLog, user_roles, role_permissions

# Module 2: Unified Profiles & Identity
from src.models.profile import (
    UserProfile, UserContact, StaffDetails, PatientDetails,
    Allergen, PatientAllergy, PatientMedicalHistory,
    GenderEnum, StaffTypeEnum, AllergenCategoryEnum, AllergySeverityEnum, MedicalHistoryStatusEnum,
)

# Module 3: Hospital Infrastructure
from src.models.infrastructure import (
    Department, Ward, Room, Bed, BedTransfer, OperationTheater,
    RoomStatusEnum, OTStatusEnum,
)

# Module 4: Clinical & IPD
from src.models.clinical import (
    DoctorSchedule, Appointment, Admission, DischargeSummary, VitalsLog,
    OTSchedule, OTTeamMember, Diagnosis, Prescription, PrescriptionItem,
    AppointmentStatusEnum, AdmissionStatusEnum, OTScheduleStatusEnum, OTRoleEnum,
)

# Module 5: Pharmacy & Inventory
from src.models.pharmacy import Medication, MedicationBatch

# Module 6: Billing & Finance
from src.models.billing import (
    Invoice, InvoiceItem, Payment, InsuranceProvider, PatientInsurance,
    InvoiceStatusEnum, InvoiceItemTypeEnum, PaymentMethodEnum,
)

# Module 7: Blood Bank
from src.models.blood_bank import BloodInventory, BloodRequest, BloodRequestStatusEnum

__all__ = [
    "Base",
    "User", "Role", "Permission", "RefreshToken", "AuditLog", "user_roles", "role_permissions",
    "UserProfile", "UserContact", "StaffDetails", "PatientDetails",
    "Allergen", "PatientAllergy", "PatientMedicalHistory",
    "GenderEnum", "StaffTypeEnum", "AllergenCategoryEnum", "AllergySeverityEnum", "MedicalHistoryStatusEnum",
    "Department", "Ward", "Room", "Bed", "BedTransfer", "OperationTheater",
    "RoomStatusEnum", "OTStatusEnum",
    "DoctorSchedule", "Appointment", "Admission", "DischargeSummary", "VitalsLog",
    "OTSchedule", "OTTeamMember", "Diagnosis", "Prescription", "PrescriptionItem",
    "AppointmentStatusEnum", "AdmissionStatusEnum", "OTScheduleStatusEnum", "OTRoleEnum",
    "Medication", "MedicationBatch",
    "Invoice", "InvoiceItem", "Payment", "InsuranceProvider", "PatientInsurance",
    "InvoiceStatusEnum", "InvoiceItemTypeEnum", "PaymentMethodEnum",
    "BloodInventory", "BloodRequest", "BloodRequestStatusEnum",
]
