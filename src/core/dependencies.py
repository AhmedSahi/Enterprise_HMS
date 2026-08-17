"""
Reusable FastAPI dependencies: extracting the current user from a JWT,
and enforcing RBAC permissions on protected endpoints.
"""
from fastapi import Depends, HTTPException, status
#from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.security import decode_token
from src.models.IAM import User

#auth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.core.security import decode_token

security = HTTPBearer()


# def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
#     """Decode the access token and load the corresponding active user."""
#     credentials_error = HTTPException(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         detail="Could not validate credentials",
#         headers={"WWW-Authenticate": "Bearer"},
#     )
#     payload = decode_token(token)
#     if payload is None or payload.get("type") != "access":
#         raise credentials_error

#     user_id = payload.get("sub")
#     if user_id is None:
#         raise credentials_error

#     user = db.get(User, int(user_id))
#     if user is None or not user.is_active:
#         raise credentials_error

#     return user

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Decode the access token and load the corresponding active user."""
    token = credentials.credentials  # Bearer token extract karega

    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        raise credentials_error

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_error

    user = db.get(User, int(user_id))
    if user is None or not user.is_active:
        raise credentials_error

    return user


class RequirePermission:
    """
    Dependency factory that checks whether the current user's roles grant
    a specific permission code, e.g.:
        Depends(RequirePermission("iam:manage_roles"))
    """

    def __init__(self, permission_code: str) -> None:
        self.permission_code = permission_code

    def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        if current_user.is_superuser:
            return current_user

        granted_codes = {
            permission.code for role in current_user.roles for permission in role.permissions
        }
        if self.permission_code not in granted_codes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {self.permission_code}",
            )
        return current_user
