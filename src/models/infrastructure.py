"""
MODULE 3: Hospital Infrastructure
Tables: departments, wards, rooms, beds, bed_transfers, operation_theaters
"""
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from src.models.base import Base, TimestampMixin


# ---------- Enums ----------
class RoomStatusEnum(str, PyEnum):
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    MAINTENANCE = "maintenance"


class OTStatusEnum(str, PyEnum):
    AVAILABLE = "available"
    IN_USE = "in_use"
    MAINTENANCE = "maintenance"


# ---------- Tables ----------
class Department(Base, TimestampMixin):
    """A medical or admin department, headed by a staff user."""
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), unique=True, nullable=False)
    manager_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    manager = relationship("User", back_populates="managed_departments")
    staff_members = relationship("StaffDetails", back_populates="department")
    wards = relationship("Ward", back_populates="department")
    operation_theaters = relationship("OperationTheater", back_populates="department")


class Ward(Base, TimestampMixin):
    """A shared patient hall belonging to a department."""
    __tablename__ = "wards"

    id = Column(Integer, primary_key=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(150), nullable=False)
    ward_type = Column(String(50), nullable=False)  # e.g. general, icu, isolation
    total_capacity = Column(Integer, nullable=False)

    department = relationship("Department", back_populates="wards")
    beds = relationship("Bed", back_populates="ward")


class Room(Base, TimestampMixin):
    """A private/semi-private room, independent of any ward."""
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True)
    room_number = Column(String(20), unique=True, nullable=False)
    room_type = Column(String(50), nullable=False)  # private, semi_private
    floor = Column(String(20), nullable=True)
    daily_rate = Column(Numeric(10, 2), nullable=False)
    status = Column(Enum(RoomStatusEnum), nullable=False, default=RoomStatusEnum.AVAILABLE)

    beds = relationship("Bed", back_populates="room")


class Bed(Base, TimestampMixin):
    """
    A physical bed. Belongs to EITHER a ward OR a private room, never both/neither
    — enforced with a CHECK constraint at the database level.
    """
    __tablename__ = "beds"

    id = Column(Integer, primary_key=True, index=True)
    bed_number = Column(String(20), nullable=False)
    ward_id = Column(Integer, ForeignKey("wards.id", ondelete="CASCADE"), nullable=True)
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=True)
    is_occupied = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "(ward_id IS NOT NULL AND room_id IS NULL) OR (ward_id IS NULL AND room_id IS NOT NULL)",
            name="ck_bed_single_location",
        ),
    )

    ward = relationship("Ward", back_populates="beds")
    room = relationship("Room", back_populates="beds")
    admissions = relationship("Admission", back_populates="bed")


class BedTransfer(Base, TimestampMixin):
    """History of a patient moving from one bed to another during a single admission."""
    __tablename__ = "bed_transfers"

    id = Column(Integer, primary_key=True, index=True)
    admission_id = Column(Integer, ForeignKey("admissions.id", ondelete="CASCADE"), nullable=False)
    from_bed_id = Column(Integer, ForeignKey("beds.id", ondelete="SET NULL"), nullable=True)
    to_bed_id = Column(Integer, ForeignKey("beds.id", ondelete="SET NULL"), nullable=False)
    transferred_at = Column(DateTime(timezone=True), nullable=False)
    reason = Column(Text, nullable=True)

    admission = relationship("Admission", back_populates="bed_transfers")


class OperationTheater(Base, TimestampMixin):
    """A surgery suite."""
    __tablename__ = "operation_theaters"

    id = Column(Integer, primary_key=True, index=True)
    name_or_code = Column(String(50), unique=True, nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    floor = Column(String(20), nullable=True)
    status = Column(Enum(OTStatusEnum), nullable=False, default=OTStatusEnum.AVAILABLE)

    department = relationship("Department", back_populates="operation_theaters")
    ot_schedules = relationship("OTSchedule", back_populates="operation_theater")