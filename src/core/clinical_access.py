"""
Shared row-level access control for clinical data.

A permission like `profiles:manage_medical_history` or `clinical:manage_diagnoses`
only proves someone is the RIGHT KIND of user to touch this category of data at
all (e.g. "any doctor"). It does NOT mean they should see every patient in the
hospital. Real hospitals scope clinical records to "need to know": the patient
themself, their TREATING doctor (someone with an appointment or admission
linking them to this specific patient), or someone holding the broader
`clinical:view_all_patient_records` override (e.g. a medical director, or the
superuser). `assert_clinical_access` is the single source of truth for this
rule and is reused across every module that touches patient clinical data.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.models.clinical import Admission, Appointment
from src.models.IAM import User
from src.models.profile import PatientDetails, StaffDetails, StaffTypeEnum


def has_treated_patient(db: Session, doctor_staff_id: int, patient_id: int) -> bool:
    """True if this doctor has at least one appointment or admission tying them to this patient."""
    has_appointment = (
        db.query(Appointment)
        .filter(Appointment.doctor_id == doctor_staff_id, Appointment.patient_id == patient_id)
        .first()
        is not None
    )
    if has_appointment:
        return True
    return (
        db.query(Admission)
        .filter(Admission.admitted_by_doctor_id == doctor_staff_id, Admission.patient_id == patient_id)
        .first()
        is not None
    )


def assert_clinical_access(db: Session, current_user: User, patient_id: int) -> None:
    """
    Raises 403 unless the caller is allowed to view/edit this specific
    patient's clinical data. Allowed if the caller is:
      1. A superuser, or
      2. Holds the `clinical:view_all_patient_records` override permission, or
      3. IS the patient themself, or
      4. Is a doctor who has actually treated this patient.
    """
    if current_user.is_superuser:
        return

    granted_codes = {permission.code for role in current_user.roles for permission in role.permissions}
    if "clinical:view_all_patient_records" in granted_codes:
        return

    patient = db.get(PatientDetails, patient_id)
    if patient is not None and patient.user_id == current_user.id:
        return  # patients can always see their own records

    staff = (
        db.query(StaffDetails)
        .filter(StaffDetails.user_id == current_user.id, StaffDetails.staff_type == StaffTypeEnum.DOCTOR)
        .first()
    )
    if staff is not None and has_treated_patient(db, staff.id, patient_id):
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "You do not have access to this patient's clinical records. "
            "Only the patient themself, their treating doctor, or a holder of "
            "'clinical:view_all_patient_records' may view or edit this data."
        ),
    )


def get_own_staff_record(db: Session, current_user: User) -> StaffDetails | None:
    """Returns the caller's own StaffDetails row, if they are staff, else None."""
    return db.query(StaffDetails).filter(StaffDetails.user_id == current_user.id).first()


def get_own_patient_record(db: Session, current_user: User) -> PatientDetails | None:
    """Returns the caller's own PatientDetails row, if they are a patient, else None."""
    return db.query(PatientDetails).filter(PatientDetails.user_id == current_user.id).first()
