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


    # =========================================================================
# DISCHARGE SUMMARIES
# =========================================================================
@router.post(
    "/discharge-summaries",
    response_model=DischargeSummaryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Write a discharge summary",
    description="Also finalizes the admission (status -> discharged) and frees the bed, if not already done.",
    dependencies=[Depends(RequirePermission("clinical:manage_admissions"))],
    responses={400: {"description": "A discharge summary already exists for this admission"}, 404: {"description": "Admission not found"}},
)
def create_discharge_summary(payload: DischargeSummaryCreate, db: Session = Depends(get_db)) -> DischargeSummary:
    admission = db.get(Admission, payload.admission_id)
    if admission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admission not found")
    if admission.discharge_summary is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A discharge summary already exists for this admission")
    if payload.discharged_by_doctor_id is not None:
        _get_doctor_staff_or_404(db, payload.discharged_by_doctor_id)

    summary = DischargeSummary(**payload.model_dump())
    db.add(summary)

    if admission.status == AdmissionStatusEnum.ADMITTED:
        admission.status = AdmissionStatusEnum.DISCHARGED
        admission.discharge_date = datetime.now()
        bed = db.get(Bed, admission.bed_id)
        if bed is not None:
            bed.is_occupied = False

    db.commit()
    db.refresh(summary)
    return summary


@router.get(
    "/discharge-summaries/{admission_id}",
    response_model=DischargeSummaryResponse,
    summary="Get the discharge summary for an admission",
    responses={403: {"description": "Not this admission's patient or doctor"}, 404: {"description": "No discharge summary found"}},
)
def get_discharge_summary(
    admission_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> DischargeSummary:
    admission = db.get(Admission, admission_id)
    if admission is None or admission.discharge_summary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No discharge summary found for this admission")
    assert_clinical_access(db, current_user, admission.patient_id)
    return admission.discharge_summary


# =========================================================================
# VITALS
# =========================================================================
@router.post(
    "/vitals",
    response_model=VitalsLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a patient's vitals",
    dependencies=[Depends(RequirePermission("clinical:manage_vitals"))],
    responses={403: {"description": "Not this patient's treating doctor"}, 404: {"description": "Patient not found"}},
)
def record_vitals(
    payload: VitalsLogCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> VitalsLog:
    _get_patient_or_404(db, payload.patient_id)
    assert_clinical_access(db, current_user, payload.patient_id)

    vitals = VitalsLog(**payload.model_dump(), recorded_by=current_user.id)
    db.add(vitals)
    db.commit()
    db.refresh(vitals)
    return vitals


@router.get(
    "/vitals",
    response_model=list[VitalsLogResponse],
    summary="List vitals for a patient",
    responses={403: {"description": "Not this patient's treating doctor"}, 404: {"description": "Patient not found"}},
)
def list_vitals(
    patient_id: int = Query(...),
    admission_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[VitalsLog]:
    _get_patient_or_404(db, patient_id)
    assert_clinical_access(db, current_user, patient_id)

    query = db.query(VitalsLog).filter(VitalsLog.patient_id == patient_id)
    if admission_id is not None:
        query = query.filter(VitalsLog.admission_id == admission_id)
    return query.order_by(VitalsLog.recorded_at.desc()).all()


# =========================================================================
# SURGERY (Operation Theater scheduling)
# =========================================================================
@router.post(
    "/ot-schedules",
    response_model=OTScheduleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Book a surgery slot",
    description="Rejects overlapping bookings for the same operation theater.",
    dependencies=[Depends(RequirePermission("clinical:manage_surgery"))],
    responses={400: {"description": "OT already booked for an overlapping time"}, 404: {"description": "OT, patient, or surgeon not found"}},
)
def create_ot_schedule(payload: OTScheduleCreate, db: Session = Depends(get_db)) -> OTSchedule:
    ot = db.get(OperationTheater, payload.ot_id)
    if ot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operation theater not found")
    _get_patient_or_404(db, payload.patient_id)
    if payload.lead_surgeon_id is not None:
        _get_doctor_staff_or_404(db, payload.lead_surgeon_id)

    overlapping = db.query(OTSchedule).filter(
        OTSchedule.ot_id == payload.ot_id,
        OTSchedule.status.notin_([OTScheduleStatusEnum.CANCELLED]),
        OTSchedule.scheduled_start < payload.scheduled_end,
        payload.scheduled_start < OTSchedule.scheduled_end,
    ).first()
    if overlapping:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This operation theater is already booked for an overlapping time")

    ot_schedule = OTSchedule(**payload.model_dump())
    db.add(ot_schedule)
    db.commit()
    db.refresh(ot_schedule)
    return ot_schedule


@router.get(
    "/ot-schedules/{ot_schedule_id}",
    response_model=OTScheduleResponse,
    summary="Get a single surgery booking",
    responses={404: {"description": "Not found"}},
)
def get_ot_schedule(
    ot_schedule_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> OTSchedule:
    ot_schedule = db.get(OTSchedule, ot_schedule_id)
    if ot_schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Surgery booking not found")
    return ot_schedule


@router.patch(
    "/ot-schedules/{ot_schedule_id}/status",
    response_model=OTScheduleResponse,
    summary="Update a surgery's status",
    dependencies=[Depends(RequirePermission("clinical:manage_surgery"))],
    responses={404: {"description": "Not found"}},
)
def update_ot_schedule_status(ot_schedule_id: int, payload: OTScheduleStatusUpdate, db: Session = Depends(get_db)) -> OTSchedule:
    ot_schedule = db.get(OTSchedule, ot_schedule_id)
    if ot_schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Surgery booking not found")
    ot_schedule.status = payload.status
    db.commit()
    db.refresh(ot_schedule)
    return ot_schedule


@router.post(
    "/ot-schedules/{ot_schedule_id}/team",
    response_model=OTTeamMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a team member to a scheduled surgery",
    dependencies=[Depends(RequirePermission("clinical:manage_surgery"))],
    responses={400: {"description": "This staff member already holds this role in this surgery"}, 404: {"description": "Surgery or staff member not found"}},
)
def add_ot_team_member(ot_schedule_id: int, payload: OTTeamMemberCreate, db: Session = Depends(get_db)) -> OTTeamMember:
    if db.get(OTSchedule, ot_schedule_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Surgery booking not found")
    if payload.ot_schedule_id != ot_schedule_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ot_schedule_id in the URL and body must match")
    if db.get(StaffDetails, payload.staff_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found")

    duplicate = db.query(OTTeamMember).filter(
        OTTeamMember.ot_schedule_id == ot_schedule_id,
        OTTeamMember.staff_id == payload.staff_id,
        OTTeamMember.role_in_surgery == payload.role_in_surgery,
    ).first()
    if duplicate:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This staff member already holds this role in this surgery")

    member = OTTeamMember(**payload.model_dump())
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.get(
    "/ot-schedules/{ot_schedule_id}/team",
    response_model=list[OTTeamMemberResponse],
    summary="List a surgery's team members",
    responses={404: {"description": "Surgery booking not found"}},
)
def list_ot_team(
    ot_schedule_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[OTTeamMember]:
    if db.get(OTSchedule, ot_schedule_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Surgery booking not found")
    return db.query(OTTeamMember).filter(OTTeamMember.ot_schedule_id == ot_schedule_id).all()


# =========================================================================
# DIAGNOSES
# =========================================================================
@router.post(
    "/diagnoses",
    response_model=DiagnosisResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a diagnosis for an OPD visit or IPD stay",
    dependencies=[Depends(RequirePermission("clinical:manage_diagnoses"))],
    responses={403: {"description": "Not this patient's treating doctor"}, 404: {"description": "Appointment/admission not found"}},
)
def create_diagnosis(
    payload: DiagnosisCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Diagnosis:
    patient_id = _resolve_patient_id_from_visit(db, payload.appointment_id, payload.admission_id)
    assert_clinical_access(db, current_user, patient_id)

    diagnosis = Diagnosis(**payload.model_dump())
    db.add(diagnosis)
    db.commit()
    db.refresh(diagnosis)
    return diagnosis


@router.get(
    "/diagnoses",
    response_model=list[DiagnosisResponse],
    summary="List diagnoses for an appointment or admission",
    responses={403: {"description": "Not this patient's treating doctor"}, 404: {"description": "Appointment/admission not found"}},
)
def list_diagnoses(
    appointment_id: int | None = Query(default=None),
    admission_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Diagnosis]:
    if appointment_id is None and admission_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide appointment_id or admission_id")

    patient_id = _resolve_patient_id_from_visit(db, appointment_id, admission_id)
    assert_clinical_access(db, current_user, patient_id)

    query = db.query(Diagnosis)
    if appointment_id is not None:
        query = query.filter(Diagnosis.appointment_id == appointment_id)
    if admission_id is not None:
        query = query.filter(Diagnosis.admission_id == admission_id)
    return query.all()


def _resolve_patient_id_from_visit(db: Session, appointment_id: int | None, admission_id: int | None) -> int:
    """Looks up which patient an appointment_id/admission_id belongs to, for access-control checks."""
    if appointment_id is not None:
        appointment = db.get(Appointment, appointment_id)
        if appointment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
        return appointment.patient_id
    if admission_id is not None:
        admission = db.get(Admission, admission_id)
        if admission is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admission not found")
        return admission.patient_id
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide appointment_id or admission_id")


# =========================================================================
# PRESCRIPTIONS (with real pharmacy stock deduction)
# =========================================================================
@router.post(
    "/prescriptions",
    response_model=PrescriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Write a prescription (deducts real pharmacy stock)",
    description=(
        "Every item's quantity is deducted from stock using FEFO (first-expiring-first-out) "
        "across that medication's non-expired batches. If ANY item doesn't have enough total "
        "stock, the ENTIRE prescription is rejected — nothing is partially deducted."
    ),
    dependencies=[Depends(RequirePermission("clinical:manage_prescriptions"))],
    responses={
        400: {"description": "Insufficient stock for one or more items"},
        403: {"description": "Not this patient's treating doctor"},
        404: {"description": "Appointment/admission/patient/medication not found"},
    },
)
def create_prescription(
    payload: PrescriptionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Prescription:
    visit_patient_id = _resolve_patient_id_from_visit(db, payload.appointment_id, payload.admission_id)
    if visit_patient_id != payload.patient_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="patient_id does not match the patient on the referenced appointment/admission",
        )
    assert_clinical_access(db, current_user, payload.patient_id)

    doctor = get_own_staff_record(db, current_user)
    doctor_id = doctor.id if doctor is not None and doctor.staff_type == StaffTypeEnum.DOCTOR else None

    # --- Validate every item's stock BEFORE deducting anything (atomicity) ---
    plans: list[tuple[PrescriptionItem, list[tuple[MedicationBatch, int]]]] = []
    for item in payload.items:
        medication = db.get(Medication, item.medication_id)
        if medication is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Medication {item.medication_id} not found")

        batches = (
            db.query(MedicationBatch)
            .filter(MedicationBatch.medication_id == item.medication_id, MedicationBatch.expiry_date > date.today())
            .order_by(MedicationBatch.expiry_date.asc())  # FEFO
            .all()
        )
        remaining = item.quantity
        deduction_plan: list[tuple[MedicationBatch, int]] = []
        for batch in batches:
            if remaining <= 0:
                break
            take = min(batch.quantity_available, remaining)
            if take > 0:
                deduction_plan.append((batch, take))
                remaining -= take

        if remaining > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient stock for '{medication.name}': short by {remaining} unit(s)",
            )

        plans.append((item, deduction_plan))

    # --- Everything validated OK — now actually create the prescription and deduct stock ---
    prescription = Prescription(
        appointment_id=payload.appointment_id,
        admission_id=payload.admission_id,
        doctor_id=doctor_id,
        patient_id=payload.patient_id,
        notes=payload.notes,
    )
    db.add(prescription)
    db.flush()

    for item, deduction_plan in plans:
        db.add(
            PrescriptionItem(
                prescription_id=prescription.id,
                medication_id=item.medication_id,
                dosage_instructions=item.dosage_instructions,
                duration_days=item.duration_days,
                quantity=item.quantity,
            )
        )
        for batch, take in deduction_plan:
            batch.quantity_available -= take

    db.commit()
    db.refresh(prescription)
    return prescription


@router.get(
    "/prescriptions",
    response_model=list[PrescriptionResponse],
    summary="List prescriptions for a patient",
    responses={403: {"description": "Not this patient's treating doctor"}, 404: {"description": "Patient not found"}},
)
def list_prescriptions(
    patient_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Prescription]:
    _get_patient_or_404(db, patient_id)
    assert_clinical_access(db, current_user, patient_id)
    return db.query(Prescription).filter(Prescription.patient_id == patient_id).all()


@router.get(
    "/prescriptions/{prescription_id}",
    response_model=PrescriptionResponse,
    summary="Get a single prescription with its items",
    responses={403: {"description": "Not this patient's treating doctor"}, 404: {"description": "Prescription not found"}},
)
def get_prescription(
    prescription_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Prescription:
    prescription = db.get(Prescription, prescription_id)
    if prescription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prescription not found")
    assert_clinical_access(db, current_user, prescription.patient_id)
    return prescription