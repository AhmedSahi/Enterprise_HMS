"""
Permission management endpoints (RBAC).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.dependencies import RequirePermission
from src.models.IAM import Permission, Role
from src.schemas.IAM import AssignPermissionRequest, MessageResponse, PermissionCreate, PermissionResponse

router = APIRouter(prefix="/permissions", tags=["Permissions"])


def _get_permission_or_404(db: Session, permission_id: int) -> Permission:
    permission = db.get(Permission, permission_id)
    if permission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found")
    return permission


@router.post(
    "",
    response_model=PermissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new permission",
    description="Creates a fine-grained permission code (e.g. 'bloodbank:approve'). Requires `iam:manage_permissions`.",
    dependencies=[Depends(RequirePermission("iam:manage_permissions"))],
    responses={400: {"description": "Permission code already exists"}},
)
def create_permission(payload: PermissionCreate, db: Session = Depends(get_db)) -> Permission:
    if db.query(Permission).filter(Permission.code == payload.code).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permission code already exists")
    permission = Permission(**payload.model_dump())
    db.add(permission)
    db.commit()
    db.refresh(permission)
    return permission


@router.get(
    "",
    response_model=list[PermissionResponse],
    summary="List all permissions",
    description="Returns every permission code defined in the system.",
)
def list_permissions(db: Session = Depends(get_db)) -> list[Permission]:
    return db.query(Permission).all()


@router.get(
    "/{permission_id}",
    response_model=PermissionResponse,
    summary="Get a single permission",
    responses={404: {"description": "Permission not found"}},
)
def get_permission(permission_id: int, db: Session = Depends(get_db)) -> Permission:
    return _get_permission_or_404(db, permission_id)


@router.delete(
    "/{permission_id}",
    response_model=MessageResponse,
    summary="Delete a permission",
    description="Permanently deletes a permission code. Roles holding it will simply lose it (link table cascades).",
    dependencies=[Depends(RequirePermission("iam:manage_permissions"))],
    responses={404: {"description": "Permission not found"}},
)
def delete_permission(permission_id: int, db: Session = Depends(get_db)) -> MessageResponse:
    permission = _get_permission_or_404(db, permission_id)
    db.delete(permission)
    db.commit()
    return MessageResponse(message=f"Permission {permission_id} deleted")


# =========================================================================
# Assignment: attach/detach a permission to/from a role
# =========================================================================
@router.post(
    "/assign",
    response_model=MessageResponse,
    summary="Grant a permission to a role",
    dependencies=[Depends(RequirePermission("iam:manage_permissions"))],
    responses={404: {"description": "Role or permission not found"}},
)
def assign_permission(payload: AssignPermissionRequest, db: Session = Depends(get_db)) -> MessageResponse:
    role = db.get(Role, payload.role_id)
    permission = _get_permission_or_404(db, payload.permission_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    if permission not in role.permissions:
        role.permissions.append(permission)
        db.commit()
    return MessageResponse(message=f"Permission '{permission.code}' granted to role '{role.name}'")


@router.delete(
    "/unassign",
    response_model=MessageResponse,
    summary="Revoke a permission from a role",
    dependencies=[Depends(RequirePermission("iam:manage_permissions"))],
    responses={404: {"description": "Role or permission not found"}},
)
def unassign_permission(payload: AssignPermissionRequest, db: Session = Depends(get_db)) -> MessageResponse:
    role = db.get(Role, payload.role_id)
    permission = _get_permission_or_404(db, payload.permission_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    if permission in role.permissions:
        role.permissions.remove(permission)
        db.commit()
    return MessageResponse(message=f"Permission '{permission.code}' revoked from role '{role.name}'")
