"""
User account endpoints, plus the profile/contact data that belongs to a user.

Design note:
    There is NO `POST /users/{id}/profile` or `POST /users/{id}/contact`.
    Both are created atomically during signup (see auth.py). Only GET and
    PATCH exist here, because a profile/contact should always already exist
    for every user — creating them separately would reopen the "orphaned
    user" problem signup was designed to prevent.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.dependencies import RequirePermission, get_current_user
from src.models.IAM import User
from src.models.profile import UserContact, UserProfile
from src.schemas.IAM import MessageResponse, UserResponse, UserSignupResponse, UserUpdate
from src.schemas.profile import (
    UserContactResponse,
    UserContactUpdate,
    UserProfileResponse,
    UserProfileUpdate,
)

router = APIRouter(prefix="/users", tags=["Users"])


def _get_user_or_404(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


# =========================================================================
# Account
# =========================================================================
@router.get(
    "/me",
    response_model=UserSignupResponse,
    summary="Get my own account (with profile and contact)",
    description="Returns the currently authenticated user's account, identity profile, and contact info.",
)
def get_my_account(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> UserSignupResponse:
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    contact = db.query(UserContact).filter(UserContact.user_id == current_user.id).first()
    return UserSignupResponse(
        id=current_user.id,
        email=current_user.email,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        profile=profile,
        contact=contact,
    )


@router.get(
    "",
    response_model=list[UserResponse],
    summary="List all users",
    description="Returns a paginated list of user accounts. Requires the `iam:view_users` permission.",
    dependencies=[Depends(RequirePermission("iam:view_users"))],
)
def list_users(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
) -> list[User]:
    return db.query(User).offset(skip).limit(limit).all()


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get a single user by ID",
    description="Returns basic account info for one user. Requires the `iam:view_users` permission.",
    dependencies=[Depends(RequirePermission("iam:view_users"))],
    responses={404: {"description": "User not found"}},
)
def get_user(user_id: int, db: Session = Depends(get_db)) -> User:
    return _get_user_or_404(db, user_id)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Activate or deactivate a user account",
    description="Updates account-level flags (currently `is_active`). Requires the `iam:manage_users` permission.",
    dependencies=[Depends(RequirePermission("iam:manage_users"))],
    responses={404: {"description": "User not found"}},
)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db)) -> User:
    user = _get_user_or_404(db, user_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


@router.delete(
    "/{user_id}",
    response_model=MessageResponse,
    summary="Deactivate a user account",
    description=(
        "Soft-deletes a user by setting `is_active = False` rather than removing the row — "
        "clinical/financial records reference users and must never be hard-deleted. "
        "Requires the `iam:manage_users` permission."
    ),
    dependencies=[Depends(RequirePermission("iam:manage_users"))],
    responses={404: {"description": "User not found"}},
)
def deactivate_user(user_id: int, db: Session = Depends(get_db)) -> MessageResponse:
    user = _get_user_or_404(db, user_id)
    user.is_active = False
    db.commit()
    return MessageResponse(message=f"User {user_id} deactivated")


# =========================================================================
# Profile (identity) — GET + PATCH only, created at signup
# =========================================================================
@router.get(
    "/{user_id}/profile",
    response_model=UserProfileResponse,
    summary="Get a user's identity profile",
    description="Returns name, gender, date of birth, and CNIC for the given user.",
    responses={404: {"description": "User or profile not found"}},
)
def get_user_profile(
    user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> UserProfile:
    _get_user_or_404(db, user_id)
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return profile


@router.patch(
    "/{user_id}/profile",
    response_model=UserProfileResponse,
    summary="Update a user's identity profile",
    description=(
        "Updates name, gender, date of birth, or CNIC. A user may update their own profile; "
        "updating someone else's profile requires the `iam:manage_users` permission."
    ),
    responses={403: {"description": "Not authorized to edit this profile"}, 404: {"description": "Profile not found"}},
)
def update_user_profile(
    user_id: int,
    payload: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserProfile:
    if current_user.id != user_id:
        # Editing someone else's profile requires an elevated permission
        RequirePermission("iam:manage_users")(current_user)

    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile


# =========================================================================
# Contact — GET + PATCH only, created at signup
# =========================================================================
@router.get(
    "/{user_id}/contact",
    response_model=UserContactResponse,
    summary="Get a user's contact details",
    description="Returns phone numbers, address, and emergency contact for the given user.",
    responses={404: {"description": "User or contact not found"}},
)
def get_user_contact(
    user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> UserContact:
    _get_user_or_404(db, user_id)
    contact = db.query(UserContact).filter(UserContact.user_id == user_id).first()
    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    return contact


@router.patch(
    "/{user_id}/contact",
    response_model=UserContactResponse,
    summary="Update a user's contact details",
    description=(
        "Updates phone numbers, address, or emergency contact. A user may update their own "
        "contact info; updating someone else's requires the `iam:manage_users` permission."
    ),
    responses={403: {"description": "Not authorized to edit this contact"}, 404: {"description": "Contact not found"}},
)
def update_user_contact(
    user_id: int,
    payload: UserContactUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserContact:
    if current_user.id != user_id:
        RequirePermission("iam:manage_users")(current_user)

    contact = db.query(UserContact).filter(UserContact.user_id == user_id).first()
    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(contact, field, value)
    db.commit()
    db.refresh(contact)
    return contact