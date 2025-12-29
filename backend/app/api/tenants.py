"""
Tenants API router
Temporary admin endpoints for managing tenant plans
"""
import uuid
import os
from fastapi import APIRouter, Depends, HTTPException, status, Query, Header
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from app.core.database import get_db
from app.core.tenant_utils import require_tenant, validate_external_id, get_current_user
from app.core.config import settings
from app.core.plans import get_plan_limits, PlanName
from app.models.tenant import Tenant, PlanTier
from app.models.user import User
from app.models.project import Project
from app.models.scan import ScanJob, ScanStatus
from app.models.entitlement import Entitlement
from app.schemas.tenant import TenantPlanInfo, TenantPlanUsage, PlanLimits, TenantCreate, TenantResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/current", response_model=TenantPlanInfo)
async def get_current_tenant_info(
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Get current tenant's plan information with limits and usage.
    
    Returns:
        TenantPlanInfo with plan, limits, and current usage statistics
    Requires X-Thandev-Tenant-Id or X-Thandev-User-Id header.
    """
    try:
        # Get effective limits (considers entitlements)
        from app.core.limits import get_effective_limits
        from app.models.entitlement import Entitlement
        from sqlalchemy import or_
        
        limits_dict = get_effective_limits(db, tenant, current_user)
        
        # Check for entitlement plan_name first (user-scoped, then tenant-wide)
        plan_name = None
        ent = None
        if current_user:
            ent = (
                db.query(Entitlement)
                .filter(Entitlement.tenant_id == tenant.id, Entitlement.user_id == current_user.id)
                .order_by(Entitlement.created_at.desc())
                .first()
            )
        
        if not ent:
            ent = (
                db.query(Entitlement)
                .filter(Entitlement.tenant_id == tenant.id, Entitlement.user_id.is_(None))
                .order_by(Entitlement.created_at.desc())
                .first()
            )
        
        if ent and ent.plan_name:
            # Use entitlement's plan_name if available
            plan_name = ent.plan_name
        else:
            # Fallback to mapping tenant.plan (PlanTier) to PlanName for response
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
        # 1. Projects count - use verified projects count to match dashboard/list
        # For usage display, count verified projects (matches what user sees)
        from app.core.project_utils import get_verified_projects_count
        try:
            projects_count = get_verified_projects_count(db, tenant, current_user, include_all_for_admin=False)
        except Exception as e:
            logger.error(f"Error counting projects in tenant info: {e}", exc_info=True)
            # Fallback to simple count if verified count fails
            projects_count = (
                db.query(Project)
                .filter(Project.tenant_id == tenant.id, Project.owner_id == current_user.id)
                .count()
            )
        
        # 2. Scans this month (UTC)
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Use func.count to avoid loading all columns (including scan_level which may not exist in DB)
        scans_this_month = (
            db.query(func.count(ScanJob.id))
            .join(Project)
            .filter(Project.tenant_id == tenant.id)
            .filter(ScanJob.created_at >= month_start)
            .scalar()
        ) or 0
        
        # 3. Concurrent scans (queued or running)
        # Use func.count to avoid loading all columns
        concurrent_scans = (
            db.query(func.count(ScanJob.id))
            .join(Project)
            .filter(Project.tenant_id == tenant.id)
            .filter(ScanJob.status.in_([ScanStatus.QUEUED, ScanStatus.RUNNING]))
            .scalar()
        ) or 0
        
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
    except Exception as e:
        logger.error(f"Error in get_current_tenant_info: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch tenant plan information: {str(e)}",
        )


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
def create_tenant(
    payload: TenantCreate,
    db: Session = Depends(get_db),
    x_thandev_admin_token: Optional[str] = Header(None, alias="X-Thandev-Admin-Token"),
):
    """
    Create a new tenant.
    
    For local/dev/test: No authentication required.
    For production: Requires X-Thandev-Admin-Token header (set via THANDEV_ADMIN_TOKEN env var).
    
    Args:
        payload: Tenant creation data (id optional, will be generated if not provided)
        x_thandev_admin_token: Admin token for production (optional in dev/test)
        
    Returns:
        Created tenant information
    """
    env_lower = settings.ENVIRONMENT.strip().lower()
    is_production = env_lower == "production"
    
    # In production, require admin token
    if is_production:
        admin_token = os.getenv("THANDEV_ADMIN_TOKEN", "")
        if not x_thandev_admin_token or x_thandev_admin_token != admin_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin token required for tenant creation in production"
            )
    
    # Validate or generate tenant ID
    if payload.id:
        tenant_id = validate_external_id(payload.id, "tenant_id")
    else:
        tenant_id = str(uuid.uuid4())
    
    # Check if tenant already exists
    existing = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tenant with id '{tenant_id}' already exists"
        )
    
    # Validate plan
    plan_mapping = {
        "free": PlanTier.FREE,
        "basic": PlanTier.BASIC,
        "pro": PlanTier.PRO,
        "enterprise": PlanTier.ENTERPRISE,
    }
    plan_tier = plan_mapping.get(payload.plan.lower())
    if not plan_tier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan: {payload.plan}. Must be one of: free, basic, pro, enterprise"
        )
    
    # Create tenant
    tenant = Tenant(
        id=tenant_id,
        name=payload.name,
        plan=plan_tier,
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    
    return TenantResponse.model_validate(tenant)


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

