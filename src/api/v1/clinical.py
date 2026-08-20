"""
MODULE 4 ROUTER: Clinical & IPD

Real-world business rules enforced here (not just CRUD):
    - Double-booking prevention: a doctor cannot have two overlapping
      appointments, and an operation theater cannot have two overlapping
      surgeries.
    - Bed occupancy is kept in sync: admitting a patient marks their bed
      occupied; discharging frees it. A bed already occupied cannot be
      re-admitted into.
    - A patient cannot have two simultaneously ACTIVE admissions.
    - Appointment status follows a one-way state machine (no resurrecting a
      cancelled/completed appointment).
    - Clinical data (diagnoses, prescriptions, vitals) is scoped via
      `assert_clinical_access` — a doctor only sees/writes records for
      patients they've actually treated (see src/core/clinical_access.py).
    - Prescriptions deduct real pharmacy stock (FEFO: first-expiring batch
      used first) and the whole prescription is rejected atomically if any
      single item doesn't have enough stock.
"""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.core.clinical_access import assert_clinical_access, get_own_patient_record, get_own_staff_record
from src.core.database import get_db
from src.core.dependencies import RequirePermission, get_current_user
from src.models.clinical import (
    Admission,
    AdmissionStatusEnum,
    Appointment,
    AppointmentStatusEnum,
    Diagnosis,
    DischargeSummary,
    DoctorSchedule,
    OTSchedule,
    OTScheduleStatusEnum,
    OTTeamMember,
    Prescription,
    PrescriptionItem,
    VitalsLog,
)
from src.models.IAM import User
from src.models.infrastructure import Bed, OperationTheater
from src.models.pharmacy import Medication, MedicationBatch
from src.models.profile import PatientDetails, StaffDetails, StaffTypeEnum
from src.schemas.clinical import (
    AdmissionCreate,
    AdmissionResponse,
    AdmissionStatusUpdate,
    AppointmentCreate,
    AppointmentResponse,
    AppointmentStatusUpdate,
    DiagnosisCreate,
    DiagnosisResponse,
    DischargeSummaryCreate,
    DischargeSummaryResponse,
    DoctorScheduleCreate,
    DoctorScheduleResponse,
    OTScheduleCreate,
    OTScheduleResponse,
    OTScheduleStatusUpdate,
    OTTeamMemberCreate,
    OTTeamMemberResponse,
    PrescriptionCreate,
    PrescriptionResponse,
    VitalsLogCreate,
    VitalsLogResponse,
)
from src.schemas.IAM import MessageResponse

router = APIRouter(tags=["Clinical & IPD"])

# Terminal appointment states that can never transition further
_APPOINTMENT_TERMINAL_STATES = {AppointmentStatusEnum.COMPLETED, AppointmentStatusEnum.CANCELLED}
# Valid forward transitions for an appointment's status
_APPOINTMENT_TRANSITIONS = {
    AppointmentStatusEnum.PENDING: {AppointmentStatusEnum.CONFIRMED, AppointmentStatusEnum.CANCELLED},
    AppointmentStatusEnum.CONFIRMED: {AppointmentStatusEnum.COMPLETED, AppointmentStatusEnum.CANCELLED},
}


def _get_doctor_staff_or_404(db: Session, doctor_id: int) -> StaffDetails:
    doctor = db.get(StaffDetails, doctor_id)
    if doctor is None or doctor.staff_type != StaffTypeEnum.DOCTOR:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    return doctor


def _get_patient_or_404(db: Session, patient_id: int) -> PatientDetails:
    patient = db.get(PatientDetails, patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


# =========================================================================
# DOCTOR SCHEDULES
# =========================================================================
@router.post(
    "/doctor-schedules",
    response_model=DoctorScheduleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a doctor's recurring weekly availability slot",
    description="Rejects overlapping time ranges for the same doctor on the same day.",
    dependencies=[Depends(RequirePermission("clinical:manage_schedules"))],
    responses={404: {"description": "Doctor not found"}, 400: {"description": "Overlaps an existing slot for this doctor"}},
)
def create_doctor_schedule(payload: DoctorScheduleCreate, db: Session = Depends(get_db)) -> DoctorSchedule:
    _get_doctor_staff_or_404(db, payload.doctor_id)
    if payload.start_time >= payload.end_time:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_time must be before end_time")

    existing = db.query(DoctorSchedule).filter(
        DoctorSchedule.doctor_id == payload.doctor_id, DoctorSchedule.day_of_week == payload.day_of_week
    ).all()
    for slot in existing:
        if payload.start_time < slot.end_time and slot.start_time < payload.end_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Overlaps an existing schedule slot ({slot.start_time}-{slot.end_time}) on this day",
            )

    schedule = DoctorSchedule(**payload.model_dump())
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


@router.get(
    "/doctor-schedules/{doctor_id}",
    response_model=list[DoctorScheduleResponse],
    summary="Get a doctor's weekly schedule",
    responses={404: {"description": "Doctor not found"}},
)
def get_doctor_schedule(
    doctor_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[DoctorSchedule]:
    _get_doctor_staff_or_404(db, doctor_id)
    return db.query(DoctorSchedule).filter(DoctorSchedule.doctor_id == doctor_id).all()


@router.delete(
    "/doctor-schedules/{schedule_id}",
    response_model=MessageResponse,
    summary="Delete a doctor schedule slot",
    dependencies=[Depends(RequirePermission("clinical:manage_schedules"))],
    responses={404: {"description": "Schedule slot not found"}},
)
def delete_doctor_schedule(schedule_id: int, db: Session = Depends(get_db)) -> MessageResponse:
    schedule = db.get(DoctorSchedule, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule slot not found")
    db.delete(schedule)
    db.commit()
    return MessageResponse(message=f"Schedule slot {schedule_id} deleted")


# =========================================================================
# APPOINTMENTS (OPD)
# =========================================================================
@router.post(
    "/appointments",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Book an OPD appointment",
    description=(
        "Self-booking: omit `patient_id` and the caller's own patient record is used. "
        "Booking on behalf of someone else (e.g. reception): supply `patient_id` and hold "
        "the `clinical:manage_appointments` permission."
    ),
    responses={
        400: {"description": "Doctor already booked at that time, or the slot is in the past"},
        403: {"description": "Caller is not a patient and lacks clinical:manage_appointments"},
        404: {"description": "Doctor or patient not found"},
    },
)
def book_appointment(
    payload: AppointmentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Appointment:
    doctor = _get_doctor_staff_or_404(db, payload.doctor_id)

    if payload.patient_id is None:
        own_patient = get_own_patient_record(db, current_user)
        if own_patient is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a patient. To book on someone else's behalf, supply patient_id "
                "and hold the clinical:manage_appointments permission.",
            )
        patient_id = own_patient.id
    else:
        granted = {p.code for r in current_user.roles for p in r.permissions}
        if not current_user.is_superuser and "clinical:manage_appointments" not in granted:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Booking on behalf of a patient requires the clinical:manage_appointments permission.",
            )
        _get_patient_or_404(db, payload.patient_id)
        patient_id = payload.patient_id

    requested_dt = datetime.combine(payload.appointment_date, payload.appointment_time)
    if requested_dt < datetime.now():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot book an appointment in the past")

    requested_end = (
        datetime.combine(date.min, payload.appointment_time) + timedelta(minutes=payload.duration_minutes)
    ).time()

    same_day = db.query(Appointment).filter(
        Appointment.doctor_id == payload.doctor_id,
        Appointment.appointment_date == payload.appointment_date,
        Appointment.status.notin_([AppointmentStatusEnum.CANCELLED]),
    ).all()
    for existing in same_day:
        existing_end = (
            datetime.combine(date.min, existing.appointment_time) + timedelta(minutes=existing.duration_minutes)
        ).time()
        if payload.appointment_time < existing_end and existing.appointment_time < requested_end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This doctor already has an overlapping appointment at that time",
            )

    appointment = Appointment(
        patient_id=patient_id,
        doctor_id=payload.doctor_id,
        appointment_date=payload.appointment_date,
        appointment_time=payload.appointment_time,
        duration_minutes=payload.duration_minutes,
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment


@router.get(
    "/appointments",
    response_model=list[AppointmentResponse],
    summary="List appointments",
    description=(
        "Patients see only their own appointments; doctors see only their own; "
        "admins/reception (with clinical:view_all_patient_records or clinical:manage_appointments) see all."
    ),
)
def list_appointments(
    patient_id: int | None = Query(default=None),
    doctor_id: int | None = Query(default=None),
    appointment_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Appointment]:
    query = db.query(Appointment)

    granted = {p.code for r in current_user.roles for p in r.permissions}
    has_broad_access = current_user.is_superuser or "clinical:view_all_patient_records" in granted

    if not has_broad_access:
        own_patient = get_own_patient_record(db, current_user)
        own_staff = get_own_staff_record(db, current_user)
        if own_patient is not None:
            query = query.filter(Appointment.patient_id == own_patient.id)
        elif own_staff is not None and own_staff.staff_type == StaffTypeEnum.DOCTOR:
            query = query.filter(Appointment.doctor_id == own_staff.id)
        else:
            return []  # neither a patient nor a doctor, and no broad-access permission

    if patient_id is not None:
        query = query.filter(Appointment.patient_id == patient_id)
    if doctor_id is not None:
        query = query.filter(Appointment.doctor_id == doctor_id)
    if appointment_date is not None:
        query = query.filter(Appointment.appointment_date == appointment_date)
    return query.all()


@router.get(
    "/appointments/{appointment_id}",
    response_model=AppointmentResponse,
    summary="Get a single appointment",
    responses={403: {"description": "Not this appointment's patient or doctor"}, 404: {"description": "Appointment not found"}},
)
def get_appointment(
    appointment_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
    assert_clinical_access(db, current_user, appointment.patient_id)
    return appointment


@router.patch(
    "/appointments/{appointment_id}/status",
    response_model=AppointmentResponse,
    summary="Update an appointment's status",
    description=(
        "Follows a one-way state machine: pending -> confirmed -> completed, or "
        "pending/confirmed -> cancelled. Completed and cancelled are terminal."
    ),
    dependencies=[Depends(RequirePermission("clinical:manage_appointments"))],
    responses={400: {"description": "Invalid status transition"}, 404: {"description": "Appointment not found"}},
)
def update_appointment_status(
    appointment_id: int, payload: AppointmentStatusUpdate, db: Session = Depends(get_db)
) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    if appointment.status in _APPOINTMENT_TERMINAL_STATES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Appointment is already '{appointment.status.value}' and cannot be changed further",
        )
    allowed_next = _APPOINTMENT_TRANSITIONS.get(appointment.status, set())
    if payload.status not in allowed_next:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot move from '{appointment.status.value}' to '{payload.status.value}'",
        )

    appointment.status = payload.status
    db.commit()
    db.refresh(appointment)
    return appointment


# =========================================================================
# ADMISSIONS (IPD)
# =========================================================================
@router.post(
    "/admissions",
    response_model=AdmissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Admit a patient (IPD)",
    description="The bed must exist and be unoccupied. On success the bed is marked occupied.",
    dependencies=[Depends(RequirePermission("clinical:manage_admissions"))],
    responses={
        400: {"description": "Bed already occupied, or patient already has an active admission"},
        404: {"description": "Patient, bed, or admitting doctor not found"},
    },
)
def admit_patient(payload: AdmissionCreate, db: Session = Depends(get_db)) -> Admission:
    _get_patient_or_404(db, payload.patient_id)

    bed = db.get(Bed, payload.bed_id)
    if bed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bed not found")
    if bed.is_occupied:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This bed is already occupied")

    if payload.admitted_by_doctor_id is not None:
        _get_doctor_staff_or_404(db, payload.admitted_by_doctor_id)

    active_admission = db.query(Admission).filter(
        Admission.patient_id == payload.patient_id, Admission.status == AdmissionStatusEnum.ADMITTED
    ).first()
    if active_admission:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Patient already has an active admission")

    admission = Admission(**payload.model_dump())
    bed.is_occupied = True
    db.add(admission)
    db.commit()
    db.refresh(admission)
    return admission


@router.get(
    "/admissions",
    response_model=list[AdmissionResponse],
    summary="List admissions",
    description="Scoped the same way as appointments: patients see their own, doctors see their own, admins see all.",
)
def list_admissions(
    patient_id: int | None = Query(default=None),
    admission_status: AdmissionStatusEnum | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Admission]:
    query = db.query(Admission)
    granted = {p.code for r in current_user.roles for p in r.permissions}
    has_broad_access = current_user.is_superuser or "clinical:view_all_patient_records" in granted

    if not has_broad_access:
        own_patient = get_own_patient_record(db, current_user)
        own_staff = get_own_staff_record(db, current_user)
        if own_patient is not None:
            query = query.filter(Admission.patient_id == own_patient.id)
        elif own_staff is not None and own_staff.staff_type == StaffTypeEnum.DOCTOR:
            query = query.filter(Admission.admitted_by_doctor_id == own_staff.id)
        else:
            return []

    if patient_id is not None:
        query = query.filter(Admission.patient_id == patient_id)
    if admission_status is not None:
        query = query.filter(Admission.status == admission_status)
    return query.all()


@router.get(
    "/admissions/{admission_id}",
    response_model=AdmissionResponse,
    summary="Get a single admission",
    responses={403: {"description": "Not this admission's patient or doctor"}, 404: {"description": "Admission not found"}},
)
def get_admission(
    admission_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Admission:
    admission = db.get(Admission, admission_id)
    if admission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admission not found")
    assert_clinical_access(db, current_user, admission.patient_id)
    return admission


@router.patch(
    "/admissions/{admission_id}/status",
    response_model=AdmissionResponse,
    summary="Discharge a patient (or mark transferred)",
    description=(
        "Setting status to 'discharged' automatically frees the bed and stamps discharge_date "
        "(if not supplied). To move a patient to a DIFFERENT bed while still admitted, use "
        "`POST /beds/transfer` instead — this endpoint does not change bed assignment."
    ),
    dependencies=[Depends(RequirePermission("clinical:manage_admissions"))],
    responses={400: {"description": "Admission is not currently active"}, 404: {"description": "Admission not found"}},
)
def update_admission_status(
    admission_id: int, payload: AdmissionStatusUpdate, db: Session = Depends(get_db)
) -> Admission:
    admission = db.get(Admission, admission_id)
    if admission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admission not found")
    if admission.status != AdmissionStatusEnum.ADMITTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Admission is already '{admission.status.value}' and cannot be changed further",
        )

    admission.status = payload.status
    if payload.status == AdmissionStatusEnum.DISCHARGED:
        admission.discharge_date = payload.discharge_date or datetime.now()
        bed = db.get(Bed, admission.bed_id)
        if bed is not None:
            bed.is_occupied = False

    db.commit()
    db.refresh(admission)
    return admission