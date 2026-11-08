from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models import AuditLog, User
from app.services.cloud_ops import run_cloud_ops_diagnostics

router = APIRouter(prefix="/api/v1/admin/cloud-ops", tags=["cloud-ops"])
ADMIN = require_roles("admin")


@router.get("/diagnostics")
def get_cloud_ops_diagnostics(
    db: Session = Depends(get_db),
    admin_user: User = Depends(ADMIN),
) -> dict:
    report = run_cloud_ops_diagnostics(db)

    # Persist audit record for diagnostic execution
    db.add(
        AuditLog(
            actor_id=admin_user.id,
            action="cloud_operations_diagnostics",
            entity_type="system",
            entity_id="cloud_ops",
            before=None,
            after={
                "overall_status": report.get("overall_status"),
                "summary": report.get("summary"),
            },
        )
    )
    db.commit()

    return report
