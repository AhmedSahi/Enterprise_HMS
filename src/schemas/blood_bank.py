from pydantic import BaseModel, ConfigDict
from datetime import datetime

class BloodInventoryUpdate(BaseModel):
    blood_group: str
    units_available: int

class BloodInventoryResponse(BaseModel):
    id: int
    blood_group: str
    units_available: int
    last_updated: datetime

    model_config = ConfigDict(from_attributes=True)


class BloodRequestCreate(BaseModel):
    patient_id: int
    blood_group: str
    units_requested: int

class BloodRequestResponse(BaseModel):
    id: int
    patient_id: int
    blood_group: str
    units_requested: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)