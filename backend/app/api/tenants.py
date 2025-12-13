"""
Tenants API router
Temporary admin endpoints for managing tenant plans
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Dict, Any

from app.core.database import get_db
from app.core.tenant_utils import require_tenant
from app.core.plans import get_plan_limits, PlanName
from app.models.tenant import Tenant
from app.models.project import Project
from app.models.scan import ScanJob, ScanStatus
from app.schemas.tenant import TenantPlanInfo, TenantPlanUsage, PlanLimits

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/current", response_model=TenantPlanInfo)
async def get_current_tenant_info(
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
):
    """
    Get current tenant's plan information with limits and usage.
    
    Returns:
        TenantPlanInfo with plan, limits, and current usage statistics
    Requires X-Thandev-Tenant-Id or X-Thandev-User-Id header.
    """
    
    # Get plan limits
    limits_dict = get_plan_limits(tenant)
    
    # Map tenant.plan (PlanTier) to PlanName for response
    from app.models.tenant import PlanTier
    
    plan_value = tenant.plan.value if hasattr(tenant.plan, 'value') else str(tenant.plan)
    plan_mapping = {
        PlanTier.FREE.value: PlanName.FREE.value,
        PlanTier.BASIC.value: PlanName.INDIVIDUAL.value,
        PlanTier.PRO.value: PlanName.TEAM.value,
        PlanTier.ENTERPRISE.value: PlanName.TEAM.value,
    }
    plan_name = plan_mapping.get(plan_value, PlanName.FREE.value)
    
    # Calculate usage
    # 1. Projects count
    projects_count = (
        db.query(Project)
        .filter(Project.tenant_id == tenant.id)
        .count()
    )
    
    # 2. Scans this month (UTC)
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    scans_this_month = (
        db.query(ScanJob)
        .join(Project)
        .filter(Project.tenant_id == tenant.id)
        .filter(ScanJob.created_at >= month_start)
        .count()
    )
    
    # 3. Concurrent scans (queued or running)
    concurrent_scans = (
        db.query(ScanJob)
        .join(Project)
        .filter(Project.tenant_id == tenant.id)
        .filter(ScanJob.status.in_([ScanStatus.QUEUED, ScanStatus.RUNNING]))
        .count()
    )
    
    # Build usage object
    usage = TenantPlanUsage(
        projects_count=projects_count,
        projects_max=limits_dict["max_projects"],
        scans_this_month=scans_this_month,
        scans_monthly_max=limits_dict["max_scans_per_month"],
        concurrent_scans=concurrent_scans,
        concurrent_scans_max=limits_dict["max_concurrent_scans"],
    )
    
    # Build limits object
    limits = PlanLimits(
        max_projects=limits_dict["max_projects"],
        max_scans_per_month=limits_dict["max_scans_per_month"],
        max_concurrent_scans=limits_dict["max_concurrent_scans"],
        allowed_scan_levels=limits_dict["allowed_scan_levels"],
    )
    
    return TenantPlanInfo(
        id=tenant.id,
        name=tenant.name,
        plan=plan_name,
        limits=limits,
        usage=usage,
    )


@router.post("/{tenant_id}/change_plan")
async def change_plan(
    tenant_id: str,
    new_plan: PlanName = Query(..., description="New plan name (free, individual, team)"),
    db: Session = Depends(get_db),
    # TODO: Add admin authentication
    # current_user: User = Depends(get_current_admin_user),
):
    """
    Change a tenant's subscription plan.
    
    TEMP: This is a dev/admin-only endpoint for switching plans.
    Later we can secure it with proper admin authentication or hook in billing.
    
    Args:
        tenant_id: ID of the tenant to update
        new_plan: New plan name (free, individual, team)
        
    Returns:
        Updated tenant information with new plan
    """
    from app.models.tenant import PlanTier
    
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant with id '{tenant_id}' not found"
        )
    
    # Map PlanName to PlanTier enum
    plan_mapping = {
        PlanName.FREE.value: "free",
        PlanName.INDIVIDUAL.value: "basic",  # Map individual -> basic
        PlanName.TEAM.value: "pro",  # Map team -> pro
    }
    
    # Get the PlanTier enum value
    plan_tier_value = plan_mapping.get(new_plan.value)
    if not plan_tier_value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan: {new_plan.value}"
        )
    
    try:
        tenant.plan = PlanTier(plan_tier_value)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan tier: {plan_tier_value}"
        )
    
    db.commit()
    db.refresh(tenant)
    
    return {
        "id": tenant.id,
        "plan": tenant.plan.value,
    }

