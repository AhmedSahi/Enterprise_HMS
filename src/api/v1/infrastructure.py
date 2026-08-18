"""
MODULE 3 ROUTER: Hospital Infrastructure

Design notes:
    - Deleting a department/ward/room is blocked (400) if anything still
      references it (staff, wards, beds) — this prevents silent data loss
      from cascading deletes wiping out records the caller didn't expect.
    - Deleting a bed with existing admissions is prevented at the DATABASE
      level already (ondelete="RESTRICT" on admissions.bed_id), but we
      check first here too so the caller gets a clean 400 instead of a
      raw database error.
    - Read (GET) endpoints on infrastructure resources are open to any
      authenticated user (e.g. any staff member needs to check bed
      availability) — only mutating endpoints require a specific permission.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.dependencies import RequirePermission, get_current_user
from src.models.clinical import Admission
from src.models.IAM import User
from src.models.infrastructure import Bed, BedTransfer, Department, OperationTheater, Room, Ward
from src.schemas.IAM import MessageResponse
from src.schemas.infrastructure import (
    BedCreate,
    BedResponse,
    BedTransferCreate,
    BedTransferResponse,
    DepartmentCreate,
    DepartmentResponse,
    OperationTheaterCreate,
    OperationTheaterResponse,
    RoomCreate,
    RoomResponse,
    WardCreate,
    WardResponse,
)

router = APIRouter(tags=["Hospital Infrastructure"])


# =========================================================================
# DEPARTMENTS
# =========================================================================
@router.post(
    "/departments",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a department",
    dependencies=[Depends(RequirePermission("infrastructure:manage_departments"))],
    responses={400: {"description": "Department name already exists"}, 404: {"description": "manager_id user not found"}},
)
def create_department(payload: DepartmentCreate, db: Session = Depends(get_db)) -> Department:
    if db.query(Department).filter(Department.name == payload.name).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Department name already exists")
    if payload.manager_id is not None and db.get(User, payload.manager_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="manager_id does not match any user")

    department = Department(**payload.model_dump())
    db.add(department)
    db.commit()
    db.refresh(department)
    return department


@router.get(
    "/departments",
    response_model=list[DepartmentResponse],
    summary="List departments",
)
def list_departments(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[Department]:
    return db.query(Department).all()


@router.get(
    "/departments/{department_id}",
    response_model=DepartmentResponse,
    summary="Get a single department",
    responses={404: {"description": "Department not found"}},
)
def get_department(
    department_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Department:
    department = db.get(Department, department_id)
    if department is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    return department


@router.patch(
    "/departments/{department_id}",
    response_model=DepartmentResponse,
    summary="Update a department",
    dependencies=[Depends(RequirePermission("infrastructure:manage_departments"))],
    responses={404: {"description": "Department (or manager_id user) not found"}},
)
def update_department(department_id: int, payload: DepartmentCreate, db: Session = Depends(get_db)) -> Department:
    department = db.get(Department, department_id)
    if department is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    if payload.manager_id is not None and db.get(User, payload.manager_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="manager_id does not match any user")

    department.name = payload.name
    department.manager_id = payload.manager_id
    db.commit()
    db.refresh(department)
    return department


@router.delete(
    "/departments/{department_id}",
    response_model=MessageResponse,
    summary="Delete a department",
    description="Blocked if the department still has wards, staff, or operation theaters attached.",
    dependencies=[Depends(RequirePermission("infrastructure:manage_departments"))],
    responses={404: {"description": "Department not found"}, 400: {"description": "Department still has dependents"}},
)
def delete_department(department_id: int, db: Session = Depends(get_db)) -> MessageResponse:
    department = db.get(Department, department_id)
    if department is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

    if department.wards or department.staff_members or department.operation_theaters:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a department that still has wards, staff, or operation theaters. Reassign or remove them first.",
        )

    db.delete(department)
    db.commit()
    return MessageResponse(message=f"Department {department_id} deleted")


# =========================================================================
# WARDS
# =========================================================================
@router.post(
    "/wards",
    response_model=WardResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a ward within a department",
    dependencies=[Depends(RequirePermission("infrastructure:manage_wards"))],
    responses={404: {"description": "Department not found"}},
)
def create_ward(payload: WardCreate, db: Session = Depends(get_db)) -> Ward:
    if db.get(Department, payload.department_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    ward = Ward(**payload.model_dump())
    db.add(ward)
    db.commit()
    db.refresh(ward)
    return ward


@router.get(
    "/wards",
    response_model=list[WardResponse],
    summary="List wards",
    description="Optionally filter by department.",
)
def list_wards(
    department_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Ward]:
    query = db.query(Ward)
    if department_id is not None:
        query = query.filter(Ward.department_id == department_id)
    return query.all()


@router.get(
    "/wards/{ward_id}",
    response_model=WardResponse,
    summary="Get a single ward",
    responses={404: {"description": "Ward not found"}},
)
def get_ward(ward_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Ward:
    ward = db.get(Ward, ward_id)
    if ward is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ward not found")
    return ward


@router.patch(
    "/wards/{ward_id}",
    response_model=WardResponse,
    summary="Update a ward",
    dependencies=[Depends(RequirePermission("infrastructure:manage_wards"))],
    responses={404: {"description": "Ward not found"}},
)
def update_ward(ward_id: int, payload: WardCreate, db: Session = Depends(get_db)) -> Ward:
    ward = db.get(Ward, ward_id)
    if ward is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ward not found")
    if db.get(Department, payload.department_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

    for field, value in payload.model_dump().items():
        setattr(ward, field, value)
    db.commit()
    db.refresh(ward)
    return ward


@router.delete(
    "/wards/{ward_id}",
    response_model=MessageResponse,
    summary="Delete a ward",
    description="Blocked if the ward still has beds attached.",
    dependencies=[Depends(RequirePermission("infrastructure:manage_wards"))],
    responses={404: {"description": "Ward not found"}, 400: {"description": "Ward still has beds"}},
)
def delete_ward(ward_id: int, db: Session = Depends(get_db)) -> MessageResponse:
    ward = db.get(Ward, ward_id)
    if ward is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ward not found")
    if ward.beds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a ward that still has beds. Remove or relocate the beds first.",
        )
    db.delete(ward)
    db.commit()
    return MessageResponse(message=f"Ward {ward_id} deleted")


# =========================================================================
# ROOMS
# =========================================================================
@router.post(
    "/rooms",
    response_model=RoomResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a private/semi-private room",
    dependencies=[Depends(RequirePermission("infrastructure:manage_rooms"))],
    responses={400: {"description": "Room number already exists"}},
)
def create_room(payload: RoomCreate, db: Session = Depends(get_db)) -> Room:
    if db.query(Room).filter(Room.room_number == payload.room_number).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Room number already exists")
    room = Room(**payload.model_dump())
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


@router.get(
    "/rooms",
    response_model=list[RoomResponse],
    summary="List rooms",
    description="Optionally filter by status or room type.",
)
def list_rooms(
    status_filter: str | None = Query(default=None, alias="status"),
    room_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Room]:
    query = db.query(Room)
    if status_filter is not None:
        query = query.filter(Room.status == status_filter)
    if room_type is not None:
        query = query.filter(Room.room_type == room_type)
    return query.all()


@router.get(
    "/rooms/{room_id}",
    response_model=RoomResponse,
    summary="Get a single room",
    responses={404: {"description": "Room not found"}},
)
def get_room(room_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Room:
    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    return room


@router.patch(
    "/rooms/{room_id}",
    response_model=RoomResponse,
    summary="Update a room (rate, status, etc.)",
    dependencies=[Depends(RequirePermission("infrastructure:manage_rooms"))],
    responses={404: {"description": "Room not found"}},
)
def update_room(room_id: int, payload: RoomCreate, db: Session = Depends(get_db)) -> Room:
    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")

    for field, value in payload.model_dump().items():
        setattr(room, field, value)
    db.commit()
    db.refresh(room)
    return room


# =========================================================================
# BEDS
# =========================================================================
@router.post(
    "/beds",
    response_model=BedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a bed in a ward or room",
    description="Exactly one of ward_id / room_id must be provided (validated by the schema itself).",
    dependencies=[Depends(RequirePermission("infrastructure:manage_beds"))],
    responses={404: {"description": "ward_id or room_id does not exist"}},
)
def create_bed(payload: BedCreate, db: Session = Depends(get_db)) -> Bed:
    if payload.ward_id is not None and db.get(Ward, payload.ward_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ward not found")
    if payload.room_id is not None and db.get(Room, payload.room_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")

    bed = Bed(**payload.model_dump())
    db.add(bed)
    db.commit()
    db.refresh(bed)
    return bed


@router.get(
    "/beds",
    response_model=list[BedResponse],
    summary="List beds",
    description="Optionally filter by ward, room, or occupancy.",
)
def list_beds(
    ward_id: int | None = Query(default=None),
    room_id: int | None = Query(default=None),
    is_occupied: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Bed]:
    query = db.query(Bed)
    if ward_id is not None:
        query = query.filter(Bed.ward_id == ward_id)
    if room_id is not None:
        query = query.filter(Bed.room_id == room_id)
    if is_occupied is not None:
        query = query.filter(Bed.is_occupied == is_occupied)
    return query.all()


@router.get(
    "/beds/available",
    response_model=list[BedResponse],
    summary="List currently available (unoccupied) beds",
    description="Convenience shortcut for `GET /beds?is_occupied=false`.",
)
def list_available_beds(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[Bed]:
    return db.query(Bed).filter(Bed.is_occupied.is_(False)).all()


@router.get(
    "/beds/{bed_id}",
    response_model=BedResponse,
    summary="Get a single bed",
    responses={404: {"description": "Bed not found"}},
)
def get_bed(bed_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Bed:
    bed = db.get(Bed, bed_id)
    if bed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bed not found")
    return bed


@router.patch(
    "/beds/{bed_id}",
    response_model=BedResponse,
    summary="Update a bed's number or occupancy flag",
    dependencies=[Depends(RequirePermission("infrastructure:manage_beds"))],
    responses={404: {"description": "Bed not found"}},
)
def update_bed(bed_id: int, payload: BedCreate, db: Session = Depends(get_db)) -> Bed:
    bed = db.get(Bed, bed_id)
    if bed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bed not found")
    if payload.ward_id is not None and db.get(Ward, payload.ward_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ward not found")
    if payload.room_id is not None and db.get(Room, payload.room_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")

    bed.bed_number = payload.bed_number
    bed.ward_id = payload.ward_id
    bed.room_id = payload.room_id
    db.commit()
    db.refresh(bed)
    return bed


@router.post(
    "/beds/transfer",
    response_model=BedTransferResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Transfer an admitted patient to a different bed",
    description=(
        "Moves an active admission to a new bed: frees the old bed, marks the new bed "
        "occupied, and records the move in the transfer history. Requires `infrastructure:manage_beds`."
    ),
    dependencies=[Depends(RequirePermission("infrastructure:manage_beds"))],
    responses={
        404: {"description": "Admission or target bed not found"},
        400: {"description": "Target bed is already occupied, or admission is not currently active"},
    },
)
def transfer_bed(payload: BedTransferCreate, db: Session = Depends(get_db)) -> BedTransfer:
    admission = db.get(Admission, payload.admission_id)
    if admission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admission not found")
    if admission.status.value != "admitted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot transfer a bed for an admission that is not currently active",
        )

    new_bed = db.get(Bed, payload.to_bed_id)
    if new_bed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target bed not found")
    if new_bed.is_occupied:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target bed is already occupied")

    old_bed = db.get(Bed, admission.bed_id)
    if old_bed is not None:
        old_bed.is_occupied = False

    new_bed.is_occupied = True
    admission.bed_id = new_bed.id

    transfer = BedTransfer(
        admission_id=payload.admission_id,
        from_bed_id=old_bed.id if old_bed else None,
        to_bed_id=new_bed.id,
        transferred_at=payload.transferred_at,
        reason=payload.reason,
    )
    db.add(transfer)
    db.commit()
    db.refresh(transfer)
    return transfer


@router.get(
    "/admissions/{admission_id}/bed-transfers",
    response_model=list[BedTransferResponse],
    summary="Get bed transfer history for an admission",
    responses={404: {"description": "Admission not found"}},
)
def list_bed_transfers(
    admission_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[BedTransfer]:
    if db.get(Admission, admission_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admission not found")
    return (
        db.query(BedTransfer)
        .filter(BedTransfer.admission_id == admission_id)
        .order_by(BedTransfer.transferred_at.asc())
        .all()
    )


# =========================================================================
# OPERATION THEATERS
# =========================================================================
@router.post(
    "/operation-theaters",
    response_model=OperationTheaterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an operation theater",
    dependencies=[Depends(RequirePermission("infrastructure:manage_ot"))],
    responses={400: {"description": "name_or_code already exists"}, 404: {"description": "Department not found"}},
)
def create_operation_theater(payload: OperationTheaterCreate, db: Session = Depends(get_db)) -> OperationTheater:
    if db.query(OperationTheater).filter(OperationTheater.name_or_code == payload.name_or_code).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This OT name/code already exists")
    if payload.department_id is not None and db.get(Department, payload.department_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

    ot = OperationTheater(**payload.model_dump())
    db.add(ot)
    db.commit()
    db.refresh(ot)
    return ot


@router.get(
    "/operation-theaters",
    response_model=list[OperationTheaterResponse],
    summary="List operation theaters",
    description="Optionally filter by status.",
)
def list_operation_theaters(
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[OperationTheater]:
    query = db.query(OperationTheater)
    if status_filter is not None:
        query = query.filter(OperationTheater.status == status_filter)
    return query.all()


@router.get(
    "/operation-theaters/{ot_id}",
    response_model=OperationTheaterResponse,
    summary="Get a single operation theater",
    responses={404: {"description": "Operation theater not found"}},
)
def get_operation_theater(
    ot_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> OperationTheater:
    ot = db.get(OperationTheater, ot_id)
    if ot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operation theater not found")
    return ot


@router.patch(
    "/operation-theaters/{ot_id}",
    response_model=OperationTheaterResponse,
    summary="Update an operation theater (e.g. status)",
    dependencies=[Depends(RequirePermission("infrastructure:manage_ot"))],
    responses={404: {"description": "Operation theater not found"}},
)
def update_operation_theater(ot_id: int, payload: OperationTheaterCreate, db: Session = Depends(get_db)) -> OperationTheater:
    ot = db.get(OperationTheater, ot_id)
    if ot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operation theater not found")

    for field, value in payload.model_dump().items():
        setattr(ot, field, value)
    db.commit()
    db.refresh(ot)
    return ot