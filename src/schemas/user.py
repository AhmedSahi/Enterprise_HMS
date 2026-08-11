import re
from pydantic import BaseModel, EmailStr, Field, field_validator

class UserCreate(BaseModel):
    """Secure schema for user signup with strict field validation and password checks."""
    
    email: EmailStr = Field(
        ..., 
        description="User email address", 
        examples=["hafiz@example.com"]
    )
    
    password: str = Field(
        ..., 
        min_length=8, 
        max_length=64, 
        description="Password must contain at least 8 characters, uppercase, lowercase, number, and special character."
    )
    
    full_name: str | None = Field(
        default=None, 
        min_length=2, 
        max_length=100, 
        description="Optional full name of the user"
    )

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, value: str) -> str:
        """Enforce strict password complexity for security."""
        if not re.search(r"[A-Z]", value):
            raise ValueError("Password must contain at least one uppercase letter (A-Z).")
        if not re.search(r"[a-z]", value):
            raise ValueError("Password must contain at least one lowercase letter (a-z).")
        if not re.search(r"\d", value):
            raise ValueError("Password must contain at least one digit (0-9).")
        if not re.search(r"[@$!%*?&]", value):
            raise ValueError("Password must contain at least one special character (@$!%*?&).")
        return value

class UserLogin(BaseModel):
    """Schema for user login request validation."""
    
    email: EmailStr = Field(..., description="Registered email address")
    password: str = Field(..., min_length=1, description="Account password")

class UserResponse(BaseModel):
    """Schema for safe user profile response serialization."""
    
    id: int
    email: EmailStr
    full_name: str | None = None
    is_active: bool
    is_verified: bool

    class Config:
        from_attributes = True