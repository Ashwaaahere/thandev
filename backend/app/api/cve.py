"""
CVE API router - Proxy for NVD API to avoid CORS issues
"""
import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Path
from fastapi.responses import JSONResponse

from app.core.dependencies import require_approved_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/cve",
    tags=["cve"],
    dependencies=[Depends(require_approved_user)],
)


@router.get("/{cve_id}")
async def get_cve_details(cve_id: str = Path(..., description="CVE ID (e.g., CVE-2015-9251)")):
    """
    Proxy endpoint to fetch CVE details from NVD API.
    
    This endpoint proxies requests to the NVD API to avoid CORS issues
    when calling from the frontend.
    
    Args:
        cve_id: CVE identifier (e.g., "CVE-2015-9251")
        
    Returns:
        NVD API response with CVE details
    """
    # Validate CVE ID format
    cve_id_upper = cve_id.upper().strip()
    if not cve_id_upper.startswith("CVE-") or len(cve_id_upper) < 9:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid CVE ID format: {cve_id}. Expected format: CVE-YYYY-NNNN"
        )
    
    # Build NVD API URL
    nvd_url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve_id_upper}"
    
    try:
        # Fetch from NVD API with timeout
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                nvd_url,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "thandev-backend/1.0",
                },
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Return the NVD response as-is
            return JSONResponse(content=data)
            
    except httpx.TimeoutException:
        logger.warning(f"NVD API timeout for CVE {cve_id_upper}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Timeout fetching CVE details from NVD API for {cve_id_upper}"
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"NVD API error for CVE {cve_id_upper}: {e.response.status_code}")
        if e.response.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"CVE {cve_id_upper} not found in NVD database"
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"NVD API returned error: {e.response.status_code}"
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching CVE {cve_id_upper} from NVD: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch CVE details: {str(e)}"
        )
