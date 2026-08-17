"""
Audit log endpoints — read-only. Entries are written internally by other
endpoints (login, signup, etc.), never created directly through the API.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.dependencies import RequirePermission
from src.models.IAM import AuditLog
from src.schemas.IAM import AuditLogResponse

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get(
    "",
    response_model=list[AuditLogResponse],
    summary="List audit log entries",
    description=(
        "Returns audit trail entries, most recent first. Optionally filter by `user_id` "
        "or `action`. Requires the `iam:view_audit_logs` permission."
    ),
    dependencies=[Depends(RequirePermission("iam:view_audit_logs"))],
)
def list_audit_logs(
    user_id: int | None = Query(default=None, description="Filter by the user who performed the action"),
    action: str | None = Query(default=None, description="Filter by action name, e.g. 'user_login'"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[AuditLog]:
    query = db.query(AuditLog)
    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)
    if action is not None:
        query = query.filter(AuditLog.action == action)
    return query.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit).all()


@router.get(
    "/{log_id}",
    response_model=AuditLogResponse,
    summary="Get a single audit log entry",
    dependencies=[Depends(RequirePermission("iam:view_audit_logs"))],
    responses={404: {"description": "Audit log entry not found"}},
)
def get_audit_log(log_id: int, db: Session = Depends(get_db)) -> AuditLog:
    log = db.get(AuditLog, log_id)
    if log is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit log entry not found")
    return log
