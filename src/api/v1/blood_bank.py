"""
MODULE 7 ROUTER: Blood Bank

Real-world business rules enforced here:
    - Approving a blood request actually DEDUCTS from live inventory —
      rejected if there isn't enough stock (no negative stock).
    - A request can only be decided once (pending -> approved/rejected is
      terminal; cannot re-decide an already-processed request).
    - Rejecting a request does NOT touch inventory (only approval does).
    - `last_updated_by` / `last_updated` are stamped automatically from the
      authenticated caller — never trusted from the request body.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.dependencies import RequirePermission, get_current_user
from src.models.blood_bank import BloodInventory, BloodRequest, BloodRequestStatusEnum
from src.models.IAM import User
from src.models.profile import PatientDetails, StaffDetails, StaffTypeEnum
from src.schemas.blood_bank import (
    BloodInventoryResponse,
    BloodInventoryUpdate,
    BloodRequestCreate,
    BloodRequestDecision,
    BloodRequestResponse,
)

router = APIRouter(prefix="/blood-bank", tags=["Blood Bank"])


# =========================================================================
# INVENTORY 
# =========================================================================
@router.get(
    "/inventory",
    response_model=list[BloodInventoryResponse],
    summary="View current blood stock levels",
    description="Returns stock for every blood group that has a record. Visible to any authenticated user.",
)
def list_inventory(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[BloodInventory]:
    return db.query(BloodInventory).all()


@router.put(
    "/inventory",
    response_model=BloodInventoryResponse,
    summary="Set/adjust the stock count for a blood group",
    description="Creates the row if this blood group has no record yet, otherwise overwrites its count.",
    dependencies=[Depends(RequirePermission("bloodbank:manage_inventory"))],
)                                                                                                           
def upsert_inventory(
    payload: BloodInventoryUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> BloodInventory:
    record = db.query(BloodInventory).filter(BloodInventory.blood_group == payload.blood_group).first()
    if record is None:
        record = BloodInventory(blood_group=payload.blood_group, available_units=payload.available_units)
        db.add(record)
    else:
        record.available_units = payload.available_units

    record.last_updated = datetime.now()
    record.last_updated_by = current_user.id
    db.commit()
    db.refresh(record)
    return record


# =========================================================================
# BLOOD REQUESTS
# =========================================================================
@router.post(
    "/requests",
    response_model=BloodRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a blood request",
    dependencies=[Depends(RequirePermission("bloodbank:request"))],
    responses={404: {"description": "Patient or requesting doctor not found"}},
)
def create_blood_request(payload: BloodRequestCreate, db: Session = Depends(get_db)) -> BloodRequest:
    if db.get(PatientDetails, payload.patient_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    if payload.requested_by_doctor_id is not None:
        doctor = db.get(StaffDetails, payload.requested_by_doctor_id)
        if doctor is None or doctor.staff_type != StaffTypeEnum.DOCTOR:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requesting doctor not found")

    blood_request = BloodRequest(**payload.model_dump())
    db.add(blood_request)
    db.commit()
    db.refresh(blood_request)
    return blood_request


@router.get(
    "/requests",
    response_model=list[BloodRequestResponse],
    summary="List blood requests",
    description="Optionally filter by status or patient.",
)
def list_blood_requests(
    request_status: BloodRequestStatusEnum | None = None,
    patient_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[BloodRequest]:
    query = db.query(BloodRequest)
    if request_status is not None:
        query = query.filter(BloodRequest.status == request_status)
    if patient_id is not None:
        query = query.filter(BloodRequest.patient_id == patient_id)
    return query.all()


@router.get(
    "/requests/{request_id}",
    response_model=BloodRequestResponse,
    summary="Get a single blood request",
    responses={404: {"description": "Blood request not found"}},
)
def get_blood_request(
    request_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> BloodRequest:
    blood_request = db.get(BloodRequest, request_id)
    if blood_request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blood request not found")
    return blood_request


@router.patch(
    "/requests/{request_id}/decision",
    response_model=BloodRequestResponse,
    summary="Approve or reject a pending blood request",
    description=(
        "Approving deducts `units_required` from that blood group's live inventory — rejected if "
        "there isn't enough stock. Rejecting leaves inventory untouched. A request can only be "
        "decided once; already-processed requests cannot be re-decided."
    ),
    dependencies=[Depends(RequirePermission("bloodbank:approve"))],
    responses={
        400: {"description": "Request already processed, or insufficient blood stock to approve"},
        404: {"description": "Blood request not found, or no inventory record for that blood group"},
    },
)
def decide_blood_request(
    request_id: int, payload: BloodRequestDecision, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> BloodRequest:
    blood_request = db.get(BloodRequest, request_id)
    if blood_request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blood request not found")
    if blood_request.status != BloodRequestStatusEnum.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"This request has already been '{blood_request.status.value}' and cannot be changed",
        )

    if payload.status == BloodRequestStatusEnum.APPROVED:
        inventory = db.query(BloodInventory).filter(BloodInventory.blood_group == blood_request.blood_group).first()
        if inventory is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No inventory record for blood group {blood_request.blood_group}")
        if inventory.available_units < blood_request.units_required:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient stock: {inventory.available_units} available, {blood_request.units_required} required",
            )
        inventory.available_units -= blood_request.units_required
        inventory.last_updated = datetime.now()
        inventory.last_updated_by = current_user.id

    blood_request.status = payload.status
    blood_request.processed_by = current_user.id
    db.commit()
    db.refresh(blood_request)
    return blood_request
