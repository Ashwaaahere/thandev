"""
Central enforcement for scan creation: approval, entitlements, quotas, domain lock/verification.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.plans import get_plan_limits
from app.core.limits import get_effective_limits as get_effective_limits_centralized
from app.models.user import User
from app.models.tenant import Tenant
from app.models.project import Project
from app.models.scan import ScanJob, ScanLevel, ScanStatus
from app.models.entitlement import Entitlement
from app.services.domain_verification import enforce_domain_verification_for_scan, ensure_project_root_domain
from app.core.config import settings


class EffectiveLimits:
    def __init__(
        self,
        allowed_scan_levels,
        max_scans_per_day: Optional[int],
        max_concurrent_scans: Optional[int],
    ):
        self.allowed_scan_levels = allowed_scan_levels
        self.max_scans_per_day = max_scans_per_day
        self.max_concurrent_scans = max_concurrent_scans


def _load_entitlement(db: Session, tenant: Tenant, user: User) -> Optional[Entitlement]:
    ent = (
        db.query(Entitlement)
        .filter(Entitlement.tenant_id == tenant.id, Entitlement.user_id == user.id)
        .order_by(Entitlement.created_at.desc())
        .first()
    )
    if ent:
        return ent
    # tenant-wide entitlement
    ent = (
        db.query(Entitlement)
        .filter(Entitlement.tenant_id == tenant.id, Entitlement.user_id == None)
        .order_by(Entitlement.created_at.desc())
        .first()
    )
    return ent


def _effective_limits(db: Session, tenant: Tenant, user: User) -> EffectiveLimits:
    # Use centralized get_effective_limits to ensure consistency
    limits_dict = get_effective_limits_centralized(db, tenant, user)
    
    # Extract values with defaults
    allowed = limits_dict.get("allowed_scan_levels", ["basic"])
    max_day = limits_dict.get("max_scans_per_day") or limits_dict.get("max_scans_per_month")  # Support both per_day and per_month
    max_conc = limits_dict.get("max_concurrent_scans")
    
    return EffectiveLimits(allowed, max_day, max_conc)


def enforce_scan_permissions(
    db: Session,
    tenant: Tenant,
    user: User,
    project: Project,
    target_url: str,
    requested_level: ScanLevel,
) -> None:
    if not user.is_approved and not user.is_admin and not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not approved. Please contact an administrator.",
        )

    # Domain verification / lock
    is_admin = bool(user.is_admin or user.is_superuser)
    ensure_project_root_domain(project, target_url, allow_admin_override=True, is_admin=is_admin)
    enforce_domain_verification_for_scan(db, project, target_url, is_admin=is_admin)

    limits = _effective_limits(db, tenant, user)
    req_level_str = requested_level.value if hasattr(requested_level, "value") else str(requested_level)
    if req_level_str not in limits.allowed_scan_levels:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Plan does not allow '{req_level_str}' scans. Allowed: {', '.join(limits.allowed_scan_levels)}",
        )

    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if limits.max_scans_per_day:
        scans_today = (
            db.query(ScanJob)
            .join(Project, ScanJob.project_id == Project.id)
            .filter(
                Project.tenant_id == tenant.id,
                ScanJob.created_at >= day_start,
            )
            .count()
        )
        if scans_today >= limits.max_scans_per_day:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Daily scan limit reached ({limits.max_scans_per_day}).",
            )

    if limits.max_concurrent_scans:
        in_progress = (
            db.query(ScanJob)
            .join(Project, ScanJob.project_id == Project.id)
            .filter(
                Project.tenant_id == tenant.id,
                ScanJob.status.in_([ScanStatus.QUEUED, ScanStatus.RUNNING]),
            )
            .count()
        )
        if in_progress >= limits.max_concurrent_scans:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many scans in progress. Max concurrent scans: {limits.max_concurrent_scans}.",
            )

