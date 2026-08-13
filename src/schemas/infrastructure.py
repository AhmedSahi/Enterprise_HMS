"""
MODULE 3 SCHEMAS: Hospital Infrastructure
Covers: departments, wards, rooms, beds, bed transfers, operation theaters.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.models.infrastructure import OTStatusEnum, RoomStatusEnum


class DepartmentCreate(BaseModel):
    name: str = Field(..., max_length=150)
    manager_id: int | None = None


class DepartmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    manager_id: int | None = None


class WardCreate(BaseModel):
    department_id: int
    name: str = Field(..., max_length=150)
    ward_type: str = Field(..., max_length=50)
    total_capacity: int = Field(..., gt=0)


class WardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    department_id: int
    name: str
    ward_type: str
    total_capacity: int


class RoomCreate(BaseModel):
    room_number: str = Field(..., max_length=20)
    room_type: str = Field(..., max_length=50)
    floor: str | None = Field(default=None, max_length=20)
    daily_rate: float = Field(..., gt=0)


class RoomResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    room_number: str
    room_type: str
    floor: str | None = None
    daily_rate: float
    status: RoomStatusEnum


class BedCreate(BaseModel):
    """Exactly one of ward_id / room_id must be provided — mirrors the DB check constraint."""

    bed_number: str = Field(..., max_length=20)
    ward_id: int | None = None
    room_id: int | None = None

    @model_validator(mode="after")
    def check_single_location(self) -> "BedCreate":
        if (self.ward_id is None) == (self.room_id is None):
            raise ValueError("Provide exactly one of ward_id or room_id, not both or neither.")
        return self


class BedResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    bed_number: str
    ward_id: int | None = None
    room_id: int | None = None
    is_occupied: bool


class BedTransferCreate(BaseModel):
    admission_id: int
    from_bed_id: int | None = None
    to_bed_id: int
    transferred_at: datetime
    reason: str | None = None


class BedTransferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    admission_id: int
    from_bed_id: int | None = None
    to_bed_id: int
    transferred_at: datetime
    reason: str | None = None


class OperationTheaterCreate(BaseModel):
    name_or_code: str = Field(..., max_length=50)
    department_id: int | None = None
    floor: str | None = Field(default=None, max_length=20)


class OperationTheaterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name_or_code: str
    department_id: int | None = None
    floor: str | None = None
    status: OTStatusEnum