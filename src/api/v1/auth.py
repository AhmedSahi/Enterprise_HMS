"""
Authentication endpoints.

Design note on signup:
    Signup creates User + UserProfile + UserContact together in ONE database
    transaction (see `signup` below). There is deliberately NO separate
    "create profile" or "create contact" endpoint — a user must never exist
    in a half-created state without their identity/contact data. If anything
    fails mid-way, the whole transaction is rolled back and nothing is saved.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.dependencies import get_current_user
from src.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from src.models.IAM import AuditLog, RefreshToken, User
from src.models.profile import UserContact, UserProfile
from src.schemas.IAM import (
    MessageResponse,
    RefreshTokenRequest,
    Token,
    UserLogin,
    UserSignupRequest,
    UserSignupResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _write_audit_log(db: Session, user_id: int | None, action: str, request: Request, status_: str = "success") -> None:
    """Internal helper: append an audit trail entry. Never raises — audit failures shouldn't break the flow."""
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            resource_type="user",
            resource_id=user_id,
            ip_address=request.client.host if request and request.client else None,
            status=status_,
        )
    )


@router.post(
    "/signup",
    response_model=UserSignupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user (account + identity + contact)",
    description=(
        "Creates a new user account **together with** their identity profile "
        "(name, gender, DOB) and contact details (phone, address) in a single "
        "atomic transaction. If any part fails, nothing is saved — there is "
        "no way to end up with a user that has no profile or no contact info. "
        "\n\nThere is intentionally no separate 'create profile' or 'create "
        "contact' endpoint; use `PATCH /users/{user_id}/profile` and "
        "`PATCH /users/{user_id}/contact` to edit this data afterwards."
    ),
    responses={
        400: {"description": "Email already registered"},
        422: {"description": "Validation error (weak password, missing required field, etc.)"},
    },
)
def signup(payload: UserSignupRequest, request: Request, db: Session = Depends(get_db)) -> User:
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    try:
        # Step 1: create the auth identity
        user = User(email=payload.email, hashed_password=get_password_hash(payload.password))
        db.add(user)
        db.flush()  # assigns user.id WITHOUT committing, so we can use it below

        # Step 2: create the identity profile, tied to the same user
        profile = UserProfile(
            user_id=user.id,
            first_name=payload.first_name,
            last_name=payload.last_name,
            gender=payload.gender,
            dob=payload.dob,
            cnic=payload.cnic,
        )
        db.add(profile)

        # Step 3: create the contact record, tied to the same user
        contact = UserContact(
            user_id=user.id,
            primary_phone=payload.primary_phone,
            secondary_phone=payload.secondary_phone,
            address=payload.address,
            emergency_name=payload.emergency_name,
            emergency_phone=payload.emergency_phone,
        )
        db.add(contact)

        _write_audit_log(db, user.id, "user_signup", request)

        db.commit()  # all three rows commit together
    except SQLAlchemyError:
        db.rollback()  # all three roll back together — no orphaned user
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not complete signup")

    db.refresh(user)
    db.refresh(profile)
    db.refresh(contact)

    return UserSignupResponse(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        created_at=user.created_at,
        profile=profile,
        contact=contact,
    )


@router.post(
    "/login",
    response_model=Token,
    summary="Log in with email and password",
    description="Authenticates a user and issues a short-lived access token plus a long-lived refresh token.",
    responses={401: {"description": "Invalid credentials"}, 403: {"description": "Account is inactive"}},
)
def login(payload: UserLogin, request: Request, db: Session = Depends(get_db)) -> Token:
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not verify_password(payload.password, user.hashed_password):
        _write_audit_log(db, user.id if user else None, "user_login", request, status_="failure")
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive")

    #user_role = getattr(user, "role", "SUPER_ADMIN")

    access_token = create_access_token(subject=str(user.id))
    refresh_token_str, expires_at = create_refresh_token(subject=str(user.id))

    db.add(RefreshToken(token=refresh_token_str, expires_at=expires_at, user_id=user.id))
    _write_audit_log(db, user.id, "user_login", request)
    db.commit()

    return Token(access_token=access_token, refresh_token=refresh_token_str)


@router.post(
    "/refresh",
    response_model=Token,
    summary="Exchange a refresh token for a new access token",
    description="Validates a stored, non-revoked, non-expired refresh token and issues a fresh access token.",
    responses={401: {"description": "Refresh token is invalid, revoked, or expired"}},
)
def refresh(payload: RefreshTokenRequest, db: Session = Depends(get_db)) -> Token:
    stored = db.query(RefreshToken).filter(RefreshToken.token == payload.refresh_token).first()
    if stored is None or stored.revoked:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    if stored.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    token_payload = decode_token(payload.refresh_token)
    if token_payload is None or token_payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    new_access_token = create_access_token(subject=token_payload["sub"])
    return Token(access_token=new_access_token, refresh_token=payload.refresh_token)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Log out (revoke a refresh token)",
    description="Revokes the given refresh token so it can no longer be used to obtain new access tokens.",
)
def logout(
    payload: RefreshTokenRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    stored = db.query(RefreshToken).filter(
        RefreshToken.token == payload.refresh_token, RefreshToken.user_id == current_user.id
    ).first()
    if stored:
        stored.revoked = True
        _write_audit_log(db, current_user.id, "user_logout", request)
        db.commit()

    return MessageResponse(message="Logged out successfully")
