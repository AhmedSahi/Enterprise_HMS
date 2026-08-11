from pydantic import BaseModel, Field
from typing import List

class PermissionResponse(BaseModel):
    """Schema for permission serialization."""
    
    id: int
    code: str = Field(..., description="Unique permission string code")
    description: str | None = None

    class Config:
        from_attributes = True

class RoleCreate(BaseModel):
    """Schema for creating an RBAC role."""
    
    name: str = Field(..., min_length=2, max_length=50, description="Role name (e.g., admin, editor)")
    description: str | None = Field(default=None, max_length=255)

class RoleResponse(BaseModel):
    """Schema for role details response."""
    
    id: int
    name: str
    description: str | None = None
    permissions: List[PermissionResponse] = []

    class Config:
        from_attributes = True