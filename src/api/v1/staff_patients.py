"""
MODULE 2 ROUTER: Unified Profiles & Identity (Staff + Patient specific data)

Design notes:
    - No DELETE endpoint for StaffDetails/PatientDetails: these rows are
      referenced everywhere (appointments, admissions, invoices, ...).
      Deactivation happens at the account level via PATCH /users/{id}
      (is_active=False), not by removing the domain record.
    - A given user_id may hold EITHER a staff profile OR a patient profile,
      never both — this is enforced explicitly below, since the DB schema
      alone (two independent unique FKs) does not prevent one user from
      having both.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.dependencies import RequirePermission, get_current_user
from src.models.IAM import User
from src.models.profile import (
    Allergen,
    PatientAllergy,
    PatientDetails,
    PatientMedicalHistory,
    StaffDetails,
)
from src.schemas.IAM import MessageResponse
from src.schemas.profile import (
    AllergenCreate,
    AllergenResponse,
    PatientAllergyCreate,
    PatientAllergyResponse,
    PatientDetailsCreate,
    PatientDetailsResponse,
    PatientDetailsUpdate,
    PatientMedicalHistoryCreate,
    PatientMedicalHistoryResponse,
    PatientMedicalHistoryUpdate,
    StaffDetailsCreate,
    StaffDetailsResponse,
    StaffDetailsUpdate,
)

router = APIRouter(tags=["Profiles: Staff & Patients"])


def _get_user_or_404(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _assert_no_dual_role(db: Session, user_id: int) -> None:
    """A user cannot simultaneously be a staff member and a patient."""
    if db.query(StaffDetails).filter(StaffDetails.user_id == user_id).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This user already has a staff profile and cannot also have a patient profile.",
        )
    if db.query(PatientDetails).filter(PatientDetails.user_id == user_id).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This user already has a patient profile and cannot also have a staff profile.",
        )


# =========================================================================
# STAFF
# =========================================================================
@router.post(
    "/staff",
    response_model=StaffDetailsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a staff profile for an existing user",
    description=(
        "Turns an existing user account into a staff member (doctor, nurse, receptionist, "
        "lab tech, pharmacist, or admin). A user cannot hold both a staff and a patient "
        "profile. Requires the `profiles:manage_staff` permission."
    ),
    dependencies=[Depends(RequirePermission("profiles:manage_staff"))],
    responses={
        400: {"description": "User already has a profile, or employee_code/license_number already taken"},
        404: {"description": "User (or department, if provided) not found"},
        422: {"description": "Doctor-only fields (specialization/license/fee) misused for the given staff_type"},
    },
)
def create_staff(payload: StaffDetailsCreate, db: Session = Depends(get_db)) -> StaffDetails:
    _get_user_or_404(db, payload.user_id)
    _assert_no_dual_role(db, payload.user_id)

    if db.query(StaffDetails).filter(StaffDetails.employee_code == payload.employee_code).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Employee code already in use")

    if payload.license_number and db.query(StaffDetails).filter(
        StaffDetails.license_number == payload.license_number
    ).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="License number already in use")

    if payload.department_id is not None:
        from src.models.infrastructure import Department  # local import avoids circular module load order

        if db.get(Department, payload.department_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

    staff = StaffDetails(**payload.model_dump())
    db.add(staff)
    db.commit()
    db.refresh(staff)
    return staff


@router.get(
    "/staff",
    response_model=list[StaffDetailsResponse],
    summary="List staff members",
    description="Returns staff members, optionally filtered by department or staff type.",
    dependencies=[Depends(RequirePermission("profiles:view_staff"))],
)
def list_staff(
    department_id: int | None = Query(default=None),
    staff_type: str | None = Query(default=None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[StaffDetails]:
    query = db.query(StaffDetails)
    if department_id is not None:
        query = query.filter(StaffDetails.department_id == department_id)
    if staff_type is not None:
        query = query.filter(StaffDetails.staff_type == staff_type)
    return query.offset(skip).limit(limit).all()


@router.get(
    "/staff/{staff_id}",
    response_model=StaffDetailsResponse,
    summary="Get a single staff profile",
    dependencies=[Depends(RequirePermission("profiles:view_staff"))],
    responses={404: {"description": "Staff profile not found"}},
)
def get_staff(staff_id: int, db: Session = Depends(get_db)) -> StaffDetails:
    staff = db.get(StaffDetails, staff_id)
    if staff is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff profile not found")
    return staff


@router.patch(
    "/staff/{staff_id}",
    response_model=StaffDetailsResponse,
    summary="Update a staff profile",
    description="Updates department, specialization, or consultation fee. Requires `profiles:manage_staff`.",
    dependencies=[Depends(RequirePermission("profiles:manage_staff"))],
    responses={404: {"description": "Staff profile (or new department) not found"}},
)
def update_staff(staff_id: int, payload: StaffDetailsUpdate, db: Session = Depends(get_db)) -> StaffDetails:
    staff = db.get(StaffDetails, staff_id)
    if staff is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff profile not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "department_id" in update_data and update_data["department_id"] is not None:
        from src.models.infrastructure import Department

        if db.get(Department, update_data["department_id"]) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

    for field, value in update_data.items():
        setattr(staff, field, value)
    db.commit()
    db.refresh(staff)
    return staff


# =========================================================================
# PATIENTS
# =========================================================================
@router.post(
    "/patients",
    response_model=PatientDetailsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a patient profile for an existing user",
    description=(
        "Turns an existing user account into a patient (assigns an MRN and blood group). "
        "A user cannot hold both a staff and a patient profile. Requires `profiles:manage_patients`."
    ),
    dependencies=[Depends(RequirePermission("profiles:manage_patients"))],
    responses={
        400: {"description": "User already has a profile, or patient_code already taken"},
        404: {"description": "User not found"},
        422: {"description": "blood_group is not a valid value (e.g. must be one of A+, A-, B+, B-, AB+, AB-, O+, O-)"},
    },
)
def create_patient(payload: PatientDetailsCreate, db: Session = Depends(get_db)) -> PatientDetails:
    _get_user_or_404(db, payload.user_id)
    _assert_no_dual_role(db, payload.user_id)

    if db.query(PatientDetails).filter(PatientDetails.patient_code == payload.patient_code).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Patient code (MRN) already in use")

    patient = PatientDetails(**payload.model_dump())
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


@router.get(
    "/patients",
    response_model=list[PatientDetailsResponse],
    summary="List patients",
    description="Returns patients, optionally searching by MRN (patient_code).",
    dependencies=[Depends(RequirePermission("profiles:view_patients"))],
)
def list_patients(
    patient_code: str | None = Query(default=None, description="Exact MRN to search for"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[PatientDetails]:
    query = db.query(PatientDetails)
    if patient_code is not None:
        query = query.filter(PatientDetails.patient_code == patient_code)
    return query.offset(skip).limit(limit).all()


@router.get(
    "/patients/{patient_id}",
    response_model=PatientDetailsResponse,
    summary="Get a single patient profile",
    dependencies=[Depends(RequirePermission("profiles:view_patients"))],
    responses={404: {"description": "Patient profile not found"}},
)
def get_patient(patient_id: int, db: Session = Depends(get_db)) -> PatientDetails:
    patient = db.get(PatientDetails, patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found")
    return patient


@router.patch(
    "/patients/{patient_id}",
    response_model=PatientDetailsResponse,
    summary="Update a patient's blood group",
    dependencies=[Depends(RequirePermission("profiles:manage_patients"))],
    responses={404: {"description": "Patient profile not found"}},
)
def update_patient(patient_id: int, payload: PatientDetailsUpdate, db: Session = Depends(get_db)) -> PatientDetails:
    patient = db.get(PatientDetails, patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(patient, field, value)
    db.commit()
    db.refresh(patient)
    return patient


# =========================================================================
# ALLERGENS (master list)
# =========================================================================
@router.post(
    "/allergens",
    response_model=AllergenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new allergen to the master list",
    dependencies=[Depends(RequirePermission("profiles:manage_allergens"))],
    responses={400: {"description": "Allergen with this name already exists"}},
)
def create_allergen(payload: AllergenCreate, db: Session = Depends(get_db)) -> Allergen:
    if db.query(Allergen).filter(Allergen.name == payload.name).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Allergen already exists")
    allergen = Allergen(**payload.model_dump())
    db.add(allergen)
    db.commit()
    db.refresh(allergen)
    return allergen


@router.get(
    "/allergens",
    response_model=list[AllergenResponse],
    summary="List all known allergens",
)
def list_allergens(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[Allergen]:
    return db.query(Allergen).all()


# =========================================================================
# PATIENT ALLERGIES
# =========================================================================
@router.post(
    "/patients/{patient_id}/allergies",
    response_model=PatientAllergyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record an allergy for a patient",
    dependencies=[Depends(RequirePermission("profiles:manage_patient_allergies"))],
    responses={
        400: {"description": "This allergy is already recorded for this patient"},
        404: {"description": "Patient or allergen not found"},
    },
)
def add_patient_allergy(
    patient_id: int, payload: PatientAllergyCreate, db: Session = Depends(get_db)
) -> PatientAllergy:
    if payload.patient_id != patient_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="patient_id in the URL and request body must match",
        )
    if db.get(PatientDetails, patient_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    if db.get(Allergen, payload.allergen_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allergen not found")

    duplicate = (
        db.query(PatientAllergy)
        .filter(PatientAllergy.patient_id == patient_id, PatientAllergy.allergen_id == payload.allergen_id)
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This allergy is already recorded")

    allergy = PatientAllergy(**payload.model_dump())
    db.add(allergy)
    db.commit()
    db.refresh(allergy)
    return allergy


@router.get(
    "/patients/{patient_id}/allergies",
    response_model=list[PatientAllergyResponse],
    summary="List a patient's recorded allergies",
    responses={404: {"description": "Patient not found"}},
)
def list_patient_allergies(
    patient_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[PatientAllergy]:
    if db.get(PatientDetails, patient_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return db.query(PatientAllergy).filter(PatientAllergy.patient_id == patient_id).all()


@router.delete(
    "/patient-allergies/{allergy_id}",
    response_model=MessageResponse,
    summary="Remove a recorded patient allergy",
    dependencies=[Depends(RequirePermission("profiles:manage_patient_allergies"))],
    responses={404: {"description": "Allergy record not found"}},
)
def delete_patient_allergy(allergy_id: int, db: Session = Depends(get_db)) -> MessageResponse:
    allergy = db.get(PatientAllergy, allergy_id)
    if allergy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allergy record not found")
    db.delete(allergy)
    db.commit()
    return MessageResponse(message=f"Allergy record {allergy_id} removed")


# =========================================================================
# PATIENT MEDICAL HISTORY
# =========================================================================
@router.post(
    "/patients/{patient_id}/medical-history",
    response_model=PatientMedicalHistoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a medical history entry for a patient",
    dependencies=[Depends(RequirePermission("profiles:manage_medical_history"))],
    responses={404: {"description": "Patient not found"}},
)
def add_medical_history(
    patient_id: int, payload: PatientMedicalHistoryCreate, db: Session = Depends(get_db)
) -> PatientMedicalHistory:
    if payload.patient_id != patient_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="patient_id in the URL and request body must match",
        )
    if db.get(PatientDetails, patient_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    entry = PatientMedicalHistory(**payload.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get(
    "/patients/{patient_id}/medical-history",
    response_model=list[PatientMedicalHistoryResponse],
    summary="List a patient's medical history",
    responses={404: {"description": "Patient not found"}},
)
def list_medical_history(
    patient_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[PatientMedicalHistory]:
    if db.get(PatientDetails, patient_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return db.query(PatientMedicalHistory).filter(PatientMedicalHistory.patient_id == patient_id).all()


@router.patch(
    "/medical-history/{entry_id}",
    response_model=PatientMedicalHistoryResponse,
    summary="Update a medical history entry (e.g. mark resolved)",
    dependencies=[Depends(RequirePermission("profiles:manage_medical_history"))],
    responses={404: {"description": "Medical history entry not found"}},
)
def update_medical_history(
    entry_id: int, payload: PatientMedicalHistoryUpdate, db: Session = Depends(get_db)
) -> PatientMedicalHistory:
    entry = db.get(PatientMedicalHistory, entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical history entry not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return entry