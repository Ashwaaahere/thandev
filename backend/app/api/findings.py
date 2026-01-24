"""
Finding detail endpoint
"""
import logging
from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload

from app.core.database import get_db
from app.core.tenant_utils import require_tenant
from app.core.dependencies import get_current_user
from app.models.finding import Finding
from app.models.scan import ScanJob
from app.models.project import Project
from app.models.user import User
from app.schemas.finding import FindingDetailResponse
from app.utils.finding_response_builder import extract_location_from_raw_data, get_impact_summary, get_remediation_data
from app.utils.raw_data_parser import parse_raw_json, extract_zap_metadata, normalize_cwe_id
from app.core.severity import zap_to_severity

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/findings",
    tags=["findings"],
)


@router.get("/{finding_id}", response_model=FindingDetailResponse)
async def get_finding_detail(
    finding_id: str,
    db: Session = Depends(get_db),
    tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed information about a specific finding.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    # Load finding with relationships
    finding = (
        db.query(Finding)
        .options(joinedload(Finding.scan_job).joinedload(ScanJob.project))
        .filter(Finding.id == finding_id)
        .first()
    )
    
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Finding {finding_id} not found"
        )
    
    # Verify finding belongs to tenant and user via project
    if not finding.scan_job or not finding.scan_job.project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finding not found"
        )
    
    project = finding.scan_job.project
    if project.tenant_id != tenant.id or project.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this finding"
        )
    
    # Extract location from raw_data if needed
    location_data = extract_location_from_raw_data(finding)
    url = location_data.get("url") or finding.url
    http_method = location_data.get("http_method") or finding.http_method
    parameter = location_data.get("parameter") or finding.parameter
    
    # Get impact summary
    impact_summary = get_impact_summary(finding)
    
    # Get remediation data
    remediation_data = get_remediation_data(finding)
    
    # Extract categories from raw_data if available
    categories = None
    if finding.raw_data:
        try:
            import json
            raw_data_dict = json.loads(finding.raw_data) if isinstance(finding.raw_data, str) else finding.raw_data
            if isinstance(raw_data_dict, dict) and "categories" in raw_data_dict:
                categories = raw_data_dict["categories"]
        except (json.JSONDecodeError, TypeError):
            pass
    
    # Parse raw_data for detail view
    raw_data_dict = None
    if finding.raw_data:
        try:
            import json
            raw_data_dict = json.loads(finding.raw_data) if isinstance(finding.raw_data, str) else finding.raw_data
        except (json.JSONDecodeError, TypeError):
            raw_data_dict = {"raw": finding.raw_data}

    # Backfill CWE + severity for ZAP findings if missing
    cwe_id = finding.cwe_id
    tool_name = (finding.tool_name or finding.tool or "").lower()
    if not cwe_id and tool_name == "zap" and finding.raw_data:
        raw_dict = parse_raw_json(finding.raw_data)
        if raw_dict:
            zap_meta = extract_zap_metadata(raw_dict)
            cwe_id = normalize_cwe_id(zap_meta.get("cweid"))
            severity_value = finding.severity.value if hasattr(finding.severity, 'value') else str(finding.severity)
            if severity_value.lower() == "info":
                computed_severity, _ = zap_to_severity(
                    zap_meta.get("riskcode", 0),
                    zap_meta.get("confidence", 0),
                    zap_meta.get("alert") or finding.title,
                    zap_meta.get("raw_dict", raw_dict),
                )
                finding_severity_value = computed_severity.value
            else:
                finding_severity_value = severity_value
        else:
            finding_severity_value = finding.severity.value if hasattr(finding.severity, 'value') else str(finding.severity)
    else:
        finding_severity_value = finding.severity.value if hasattr(finding.severity, 'value') else str(finding.severity)
    
    # Get target URL from project
    target_url = project.target_url if project else None
    
    return FindingDetailResponse(
        id=finding.id,
        scan_id=finding.scan_job_id,
        project_id=project.id,
        project_name=project.name if project else "Unknown",
        target_url=target_url or "",
        severity=finding_severity_value,
        status=finding.status.value if hasattr(finding.status, 'value') else str(finding.status),
        title=finding.title,
        description=finding.description,
        cve_id=finding.cve_id,
        cwe_id=cwe_id,
        cvss_score=finding.cvss_score,
        # ZAP-specific metadata
        wasc_id=finding.wasc_id if hasattr(finding, 'wasc_id') else None,
        plugin_id=finding.plugin_id if hasattr(finding, 'plugin_id') else None,
        alert_ref=finding.alert_ref if hasattr(finding, 'alert_ref') else None,
        zap_confidence=finding.zap_confidence if hasattr(finding, 'zap_confidence') else None,
        zap_riskcode=finding.zap_riskcode if hasattr(finding, 'zap_riskcode') else None,
        tool=finding.tool_name or finding.tool,
        categories=categories,
        vuln_type=finding.vuln_type,
        http_method=http_method,
        parameter=parameter,
        url=url,
        path=finding.path,
        evidence=finding.evidence,
        needs_verification=finding.needs_verification if hasattr(finding, 'needs_verification') else None,
        first_seen_at=finding.first_seen_at,
        last_seen_at=finding.last_seen_at,
        not_seen_in_latest_scan=finding.not_seen_in_latest_scan if hasattr(finding, 'not_seen_in_latest_scan') else None,
        found_count=finding.found_count if hasattr(finding, 'found_count') else None,
        remediation_summary=remediation_data["remediation_summary"],
        remediation_steps=finding.remediation_steps if hasattr(finding, 'remediation_steps') else None,
        default_remediation_steps=remediation_data["default_remediation_steps"],
        impact_summary=impact_summary,
        ai_source=finding.ai_source if hasattr(finding, 'ai_source') else None,
        ai_model=finding.ai_model if hasattr(finding, 'ai_model') else None,
        ai_confidence=finding.ai_confidence if hasattr(finding, 'ai_confidence') else None,
        raw_data=raw_data_dict,
    )

