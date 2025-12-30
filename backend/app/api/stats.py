"""
Stats API endpoint for legacy compatibility
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(
    prefix="/stats",
    tags=["stats"],
)


@router.get("", response_class=JSONResponse)
@router.options("", response_class=JSONResponse)
async def get_stats():
    """
    Legacy stats endpoint for homepage compatibility.
    Returns basic stats structure expected by frontend.
    
    Note: This is a stub endpoint. The actual stats data may come from
    other endpoints like /api/metrics/overview or /api/exploits/stats.
    """
    return {
        "signals_today": 0,
        "exploits_today": 0,
        "vendors_today": 0,
        "checks_per_run": 0,
        "issues_prevented_7d": 0,
    }

