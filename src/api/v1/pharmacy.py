"""
MODULE 5 ROUTER: Pharmacy & Inventory

Design notes:
    - Medications (catalog) and MedicationBatches (physical stock with expiry)
      are kept separate on purpose — see models/pharmacy.py. Stock quantity
      queries always exclude expired batches so a nurse/pharmacist can never
      accidentally dispense out-of-date medicine through this API.
    - Deleting a medication is blocked if any batches still have stock, or if
      it's ever been prescribed (the latter is also enforced at the DB level
      via ondelete="RESTRICT" on prescription_items.medication_id).
"""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.dependencies import RequirePermission, get_current_user
from src.models.clinical import PrescriptionItem
from src.models.IAM import User
from src.models.pharmacy import Medication, MedicationBatch
from src.schemas.IAM import MessageResponse
from src.schemas.pharmacy import (
    MedicationBatchAdjust,
    MedicationBatchCreate,
    MedicationBatchResponse,
    MedicationCreate,
    MedicationResponse,
    MedicationUpdate,
)

router = APIRouter(tags=["Pharmacy & Inventory"])


# =========================================================================
# MEDICATIONS (catalog)
# =========================================================================
@router.post(
    "/medications",
    response_model=MedicationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a medication to the catalog",
    dependencies=[Depends(RequirePermission("pharmacy:manage_catalog"))],
)
def create_medication(payload: MedicationCreate, db: Session = Depends(get_db)) -> Medication:
    medication = Medication(**payload.model_dump())
    db.add(medication)
    db.commit()
    db.refresh(medication)
    return medication


@router.get(
    "/medications",
    response_model=list[MedicationResponse],
    summary="List / search medications",
    description="Optionally search by (partial, case-insensitive) name.",
)
def list_medications(
    name: str | None = Query(default=None, description="Partial name search"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Medication]:
    query = db.query(Medication)
    if name is not None:
        query = query.filter(Medication.name.ilike(f"%{name}%"))
    return query.offset(skip).limit(limit).all()


@router.get(
    "/medications/{medication_id}",
    response_model=MedicationResponse,
    summary="Get a single medication",
    responses={404: {"description": "Medication not found"}},
)
def get_medication(
    medication_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Medication:
    medication = db.get(Medication, medication_id)
    if medication is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medication not found")
    return medication


@router.patch(
    "/medications/{medication_id}",
    response_model=MedicationResponse,
    summary="Update a medication's price",
    dependencies=[Depends(RequirePermission("pharmacy:manage_catalog"))],
    responses={404: {"description": "Medication not found"}},
)
def update_medication(medication_id: int, payload: MedicationUpdate, db: Session = Depends(get_db)) -> Medication:
    medication = db.get(Medication, medication_id)
    if medication is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medication not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(medication, field, value)
    db.commit()
    db.refresh(medication)
    return medication


@router.delete(
    "/medications/{medication_id}",
    response_model=MessageResponse,
    summary="Delete a medication from the catalog",
    description="Blocked if any batch still has stock, or if this medication has ever been prescribed.",
    dependencies=[Depends(RequirePermission("pharmacy:manage_catalog"))],
    responses={404: {"description": "Medication not found"}, 400: {"description": "Medication still has stock or prescription history"}},
)
def delete_medication(medication_id: int, db: Session = Depends(get_db)) -> MessageResponse:
    medication = db.get(Medication, medication_id)
    if medication is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medication not found")

    if any(batch.quantity_available > 0 for batch in medication.batches):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a medication with remaining stock. Zero out or remove its batches first.",
        )
    if db.query(PrescriptionItem).filter(PrescriptionItem.medication_id == medication_id).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a medication that has prescription history.",
        )

    db.delete(medication)
    db.commit()
    return MessageResponse(message=f"Medication {medication_id} deleted")


# =========================================================================
# MEDICATION BATCHES (physical stock, with expiry)
# =========================================================================
@router.post(
    "/medications/{medication_id}/batches",
    response_model=MedicationBatchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a stock batch for a medication",
    description="expiry_date must be in the future. (batch_number, medication_id) must be unique.",
    dependencies=[Depends(RequirePermission("pharmacy:manage_inventory"))],
    responses={
        404: {"description": "Medication not found"},
        400: {"description": "This batch_number already exists for this medication"},
        422: {"description": "expiry_date is not in the future"},
    },
)
def add_medication_batch(
    medication_id: int, payload: MedicationBatchCreate, db: Session = Depends(get_db)
) -> MedicationBatch:
    if db.get(Medication, medication_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medication not found")
    if payload.medication_id != medication_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="medication_id in the URL and request body must match",
        )

    duplicate = (
        db.query(MedicationBatch)
        .filter(MedicationBatch.medication_id == medication_id, MedicationBatch.batch_number == payload.batch_number)
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This batch_number already exists for this medication")

    batch = MedicationBatch(**payload.model_dump())
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


@router.get(
    "/medications/{medication_id}/batches",
    response_model=list[MedicationBatchResponse],
    summary="List stock batches for a medication",
    description="By default excludes already-expired batches; pass include_expired=true to see everything.",
    responses={404: {"description": "Medication not found"}},
)
def list_medication_batches(
    medication_id: int,
    include_expired: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MedicationBatch]:
    if db.get(Medication, medication_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medication not found")

    query = db.query(MedicationBatch).filter(MedicationBatch.medication_id == medication_id)
    if not include_expired:
        query = query.filter(MedicationBatch.expiry_date > date.today())
    return query.order_by(MedicationBatch.expiry_date.asc()).all()


@router.get(
    "/medication-batches/expiring",
    response_model=list[MedicationBatchResponse],
    summary="List batches expiring soon (across all medications)",
    description="Returns non-expired batches whose expiry_date falls within the next `days` days (default 30).",
)
def list_expiring_batches(
    days: int = Query(default=30, gt=0, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MedicationBatch]:
    today = date.today()
    cutoff = today + timedelta(days=days)
    return (
        db.query(MedicationBatch)
        .filter(MedicationBatch.expiry_date > today, MedicationBatch.expiry_date <= cutoff)
        .order_by(MedicationBatch.expiry_date.asc())
        .all()
    )


@router.patch(
    "/medication-batches/{batch_id}",
    response_model=MedicationBatchResponse,
    summary="Adjust a batch's stock quantity (manual correction)",
    dependencies=[Depends(RequirePermission("pharmacy:manage_inventory"))],
    responses={404: {"description": "Batch not found"}},
)
def adjust_medication_batch(batch_id: int, payload: MedicationBatchAdjust, db: Session = Depends(get_db)) -> MedicationBatch:
    batch = db.get(MedicationBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    batch.quantity_available = payload.quantity_available
    db.commit()
    db.refresh(batch)
    return batch
