from pydantic import BaseModel, Field

class TokenResponse(BaseModel):
    """Schema returning JWT tokens securely."""
    
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")

class TokenPayload(BaseModel):
    """Schema for decoded JWT token payload data."""
    
    sub: str | None = Field(default=None, description="Subject (User Email or ID)")
    exp: int | None = Field(default=None, description="Expiration timestamp")