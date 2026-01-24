"""
Reference endpoints for CWE, WASC, and other security references.
"""
import json
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/reference",
    tags=["reference"],
    # No auth required - CWE data is public
)

# In-memory cache for CWE data
_cwe_data_cache: Optional[Dict[str, Any]] = None


def load_cwe_data() -> Dict[str, Any]:
    """Load CWE data from JSON file, with caching."""
    global _cwe_data_cache
    
    if _cwe_data_cache is not None:
        return _cwe_data_cache
    
    # Get path to cwe_min.json
    data_dir = Path(__file__).parent.parent / "data"
    cwe_file = data_dir / "cwe_min.json"
    
    if not cwe_file.exists():
        logger.warning(f"CWE data file not found at {cwe_file}, returning empty dataset")
        _cwe_data_cache = {}
        return _cwe_data_cache
    
    try:
        with open(cwe_file, 'r', encoding='utf-8') as f:
            _cwe_data_cache = json.load(f)
        logger.info(f"Loaded {len(_cwe_data_cache)} CWE entries from {cwe_file}")
        return _cwe_data_cache
    except Exception as e:
        logger.error(f"Error loading CWE data: {e}", exc_info=True)
        _cwe_data_cache = {}
        return _cwe_data_cache


class CWEResponse(BaseModel):
    """Response model for CWE reference endpoint."""
    id: int
    title: Optional[str] = None
    summary: Optional[str] = None
    why_it_matters: Optional[str] = None
    common_impacts: Optional[list[str]] = None
    basic_mitigations: Optional[list[str]] = None
    links: Dict[str, str]


def validate_cwe_id(cwe_id: str) -> int:
    """
    Validate and normalize CWE ID.
    
    Args:
        cwe_id: CWE ID as string (e.g., "1021", "CWE-1021")
        
    Returns:
        Integer CWE ID
        
    Raises:
        HTTPException: If CWE ID is invalid
    """
    # Remove "CWE-" prefix if present
    cwe_id_clean = cwe_id.upper().replace("CWE-", "").strip()
    
    try:
        cwe_id_int = int(cwe_id_clean)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid CWE ID format: {cwe_id}. Expected numeric value (e.g., '1021' or 'CWE-1021')"
        )
    
    # Validate range (1-9999 is reasonable for CWE IDs)
    if cwe_id_int < 1 or cwe_id_int > 9999:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CWE ID out of valid range: {cwe_id_int}. Expected 1-9999"
        )
    
    return cwe_id_int


def build_cwe_links(cwe_id: int) -> Dict[str, str]:
    """Build external links for a CWE ID."""
    cwe_id_str = str(cwe_id)
    return {
        "mitre": f"https://cwe.mitre.org/data/definitions/{cwe_id_str}.html",
        "nvd_search": f"https://nvd.nist.gov/vuln/search/results?cwe_id=CWE-{cwe_id_str}"
    }


@router.get("/cwe/{cwe_id}", response_model=CWEResponse)
async def get_cwe_reference(cwe_id: str):
    """
    Get CWE reference information.
    
    Returns local dataset information if available, otherwise returns
    a minimal response with external links only.
    """
    # Validate CWE ID
    cwe_id_int = validate_cwe_id(cwe_id)
    
    # Load CWE data
    cwe_data = load_cwe_data()
    
    # Look up CWE in dataset (key is string)
    cwe_key = str(cwe_id_int)
    cwe_entry = cwe_data.get(cwe_key)
    
    # Build links
    links = build_cwe_links(cwe_id_int)
    
    if cwe_entry:
        # Return full dataset entry
        return CWEResponse(
            id=cwe_id_int,
            title=cwe_entry.get("title"),
            summary=cwe_entry.get("summary"),
            why_it_matters=cwe_entry.get("why_it_matters"),
            common_impacts=cwe_entry.get("common_impacts", []),
            basic_mitigations=cwe_entry.get("basic_mitigations", []),
            links=links
        )
    else:
        # Return minimal response with links only
        logger.debug(f"CWE {cwe_id_int} not found in local dataset, returning minimal response")
        return CWEResponse(
            id=cwe_id_int,
            title=None,
            summary=None,
            why_it_matters=None,
            common_impacts=None,
            basic_mitigations=None,
            links=links
        )


@router.get("/cwe/{cwe_id}/links")
async def get_cwe_links(cwe_id: str):
    """Get just the external links for a CWE ID."""
    cwe_id_int = validate_cwe_id(cwe_id)
    return build_cwe_links(cwe_id_int)

