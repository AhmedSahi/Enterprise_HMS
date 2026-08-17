"""
Role management endpoints (RBAC).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.dependencies import RequirePermission
from src.models.IAM import Role, User
from src.schemas.IAM import (
    AssignRoleRequest,
    MessageResponse,
    RoleCreate,
    RoleResponse,
    RoleWithPermissionsResponse,
)

router = APIRouter(prefix="/roles", tags=["Roles"])


def _get_role_or_404(db: Session, role_id: int) -> Role:
    role = db.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return role


@router.post(
    "",
    response_model=RoleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new role",
    description="Creates a named role (e.g. 'doctor', 'admin'). Requires the `iam:manage_roles` permission.",
    dependencies=[Depends(RequirePermission("iam:manage_roles"))],
    responses={400: {"description": "Role name already exists"}},
)
def create_role(payload: RoleCreate, db: Session = Depends(get_db)) -> Role:
    if db.query(Role).filter(Role.name == payload.name).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role already exists")
    role = Role(**payload.model_dump())
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


@router.get(
    "",
    response_model=list[RoleResponse],
    summary="List all roles",
    description="Returns every role defined in the system.",
)
def list_roles(db: Session = Depends(get_db)) -> list[Role]:
    return db.query(Role).all()


@router.get(
    "/{role_id}",
    response_model=RoleWithPermissionsResponse,
    summary="Get a role and its permissions",
    description="Returns a single role along with the list of permissions it grants.",
    responses={404: {"description": "Role not found"}},
)
def get_role(role_id: int, db: Session = Depends(get_db)) -> Role:
    return _get_role_or_404(db, role_id)


@router.patch(
    "/{role_id}",
    response_model=RoleResponse,
    summary="Update a role's name or description",
    dependencies=[Depends(RequirePermission("iam:manage_roles"))],
    responses={404: {"description": "Role not found"}},
)
def update_role(role_id: int, payload: RoleCreate, db: Session = Depends(get_db)) -> Role:
    role = _get_role_or_404(db, role_id)
    role.name = payload.name
    role.description = payload.description
    db.commit()
    db.refresh(role)
    return role


@router.delete(
    "/{role_id}",
    response_model=MessageResponse,
    summary="Delete a role",
    description="Permanently deletes a role. Users holding this role will simply lose it (link table cascades).",
    dependencies=[Depends(RequirePermission("iam:manage_roles"))],
    responses={404: {"description": "Role not found"}},
)
def delete_role(role_id: int, db: Session = Depends(get_db)) -> MessageResponse:
    role = _get_role_or_404(db, role_id)
    db.delete(role)
    db.commit()
    return MessageResponse(message=f"Role {role_id} deleted")


# =========================================================================
# Assignment: attach/detach a role to/from a user
# =========================================================================
@router.post(
    "/assign",
    response_model=MessageResponse,
    summary="Assign a role to a user",
    dependencies=[Depends(RequirePermission("iam:manage_roles"))],
    responses={404: {"description": "User or role not found"}},
)
def assign_role(payload: AssignRoleRequest, db: Session = Depends(get_db)) -> MessageResponse:
    user = db.get(User, payload.user_id)
    role = _get_role_or_404(db, payload.role_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if role not in user.roles:
        user.roles.append(role)
        db.commit()
    return MessageResponse(message=f"Role '{role.name}' assigned to user {user.id}")


@router.delete(
    "/unassign",
    response_model=MessageResponse,
    summary="Remove a role from a user",
    dependencies=[Depends(RequirePermission("iam:manage_roles"))],
    responses={404: {"description": "User or role not found"}},
)
def unassign_role(payload: AssignRoleRequest, db: Session = Depends(get_db)) -> MessageResponse:
    user = db.get(User, payload.user_id)
    role = _get_role_or_404(db, payload.role_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if role in user.roles:
        user.roles.remove(role)
        db.commit()
    return MessageResponse(message=f"Role '{role.name}' removed from user {user.id}")
