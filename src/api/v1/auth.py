from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from src.core.database import get_db
from src.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token
)
from src.core.deps import get_current_user
from src.models.user import User, RefreshToken
from src.models.role import Role
from src.models.audit import AuditLog
from src.schemas.user  import (
    UserCreate,
    UserResponse,
    UserLogin,
    MessageResponse
)
from src.schemas.token import TokenResponse, RefreshTokenRequest

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(user_in: UserCreate, db: Session = Depends(get_db)):
    # 1. Check if email already exists
    existing_user = db.query(User).filter(User.email == user_in.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered"
        )

    # 2. Hash password and create user
    hashed_pwd = get_password_hash(user_in.password)
    new_user = User(
        email=user_in.email,
        full_name=user_in.full_name,
        hashed_password=hashed_pwd,
        is_active=True
    )
    
    # 3. Assign default 'User' role
    default_role = db.query(Role).filter(Role.name == "User").first()
    if default_role:
        new_user.roles.append(default_role)

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # 4. Create Audit Log entry
    audit = AuditLog(
        user_id=new_user.id,
        action="USER_SIGNUP",
        ip_address="127.0.0.1",
        status="SUCCESS"
    )
    db.add(audit)
    db.commit()

    return new_user


@router.post("/login", response_model=TokenResponse)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    # 1. Authenticate user credentials
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account"
        )

    # 2. Generate Access and Refresh JWT tokens
    token_data = {"sub": str(user.id), "email": user.email}
    access_token = create_access_token(data=token_data)
    refresh_token_str = create_refresh_token(data=token_data)

    # 3. Save refresh token to database
    db_refresh_token = RefreshToken(
        token=refresh_token_str,
        user_id=user.id,
        revoked=False
    )
    db.add(db_refresh_token)

    # 4. Audit Log
    audit = AuditLog(
        user_id=user.id,
        action="USER_LOGIN",
        ip_address="127.0.0.1",
        status="SUCCESS"
    )
    db.add(audit)
    db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_str,
        token_type="bearer"
    )



@router.post("/refresh", response_model=TokenResponse)
def refresh_token(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    # 1. Check token in database
    token_record = db.query(RefreshToken).filter(
        RefreshToken.token == payload.refresh_token,
        RefreshToken.revoked == False
    ).first()

    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked refresh token"
        )

    # 2. Decode and validate token payload
    decoded_payload = decode_token(payload.refresh_token)
    if not decoded_payload or "sub" not in decoded_payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Expired or malformed token"
        )

    user_id = int(decoded_payload["sub"])
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer active"
        )

    # 3. Issue new access token and rotate refresh token
    new_token_data = {"sub": str(user.id), "email": user.email}
    new_access_token = create_access_token(data=new_token_data)
    new_refresh_token = create_refresh_token(data=new_token_data)

    # Revoke old refresh token and store new one
    token_record.revoked = True
    new_db_refresh_token = RefreshToken(
        token=new_refresh_token,
        user_id=user.id,
        revoked=False
    )
    db.add(new_db_refresh_token)
    db.commit()

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer"
    )



@router.post("/logout", response_model=MessageResponse)
def logout(
    payload: RefreshTokenRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Revoke current session refresh token
    token_record = db.query(RefreshToken).filter(
        RefreshToken.token == payload.refresh_token,
        RefreshToken.user_id == current_user.id
    ).first()

    if token_record:
        token_record.revoked = True
        
    audit = AuditLog(
        user_id=current_user.id,
        action="USER_LOGOUT",
        ip_address="127.0.0.1",
        status="SUCCESS"
    )
    db.add(audit)
    db.commit()

    return MessageResponse(message="Successfully logged out")


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user