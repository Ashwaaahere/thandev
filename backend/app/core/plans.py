"""
Plan configuration and limits
Defines subscription plan tiers and their limits
"""
from enum import Enum
from typing import Dict, List, TypedDict


class PlanName(str, Enum):
    """Subscription plan names"""
    FREE = "free"
    INDIVIDUAL = "individual"
    TEAM = "team"


class PlanLimits(TypedDict):
    """Plan limits structure"""
    max_projects: int
    max_scans_per_month: int
    max_concurrent_scans: int
    allowed_scan_levels: List[str]


# Central plan configuration
# All limits are enforced on the backend based on tenant.plan
PLAN_CONFIG: Dict[PlanName, PlanLimits] = {
    PlanName.FREE: {
        "max_projects": 1,
        "max_scans_per_month": 20,
        "max_concurrent_scans": 1,
        "allowed_scan_levels": ["basic"],
    },
    PlanName.INDIVIDUAL: {
        "max_projects": 5,
        "max_scans_per_month": 200,
        "max_concurrent_scans": 2,
        "allowed_scan_levels": ["basic", "pro"],
    },
    PlanName.TEAM: {
        "max_projects": 20,
        "max_scans_per_month": 2000,
        "max_concurrent_scans": 5,
        "allowed_scan_levels": ["basic", "pro", "advanced"],
    },
}


def get_plan_limits(tenant) -> PlanLimits:
    """
    Returns the effective limits for this tenant.
    
    Maps the tenant's plan (PlanTier enum) to our PlanName enum and returns limits.
    Later we could allow per-tenant overrides using DB columns.
    
    Args:
        tenant: Tenant model instance with a 'plan' attribute (PlanTier enum)
        
    Returns:
        PlanLimits dictionary with the tenant's plan limits
        
    Mapping:
        PlanTier.FREE -> PlanName.FREE
        PlanTier.BASIC -> PlanName.INDIVIDUAL
        PlanTier.PRO -> PlanName.TEAM
        PlanTier.ENTERPRISE -> PlanName.TEAM
    """
    from app.models.tenant import PlanTier
    
    # Handle both enum and string plan values
    plan_value = tenant.plan.value if hasattr(tenant.plan, 'value') else str(tenant.plan)
    
    # Map PlanTier enum values to PlanName enum values
    plan_mapping = {
        PlanTier.FREE.value: PlanName.FREE,
        PlanTier.BASIC.value: PlanName.INDIVIDUAL,
        PlanTier.PRO.value: PlanName.TEAM,
        PlanTier.ENTERPRISE.value: PlanName.TEAM,
    }
    
    # Get the mapped plan name, default to FREE if unknown
    plan_name = plan_mapping.get(plan_value, PlanName.FREE)
    
    return PLAN_CONFIG[plan_name]

