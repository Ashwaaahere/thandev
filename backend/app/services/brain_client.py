"""
Brain service HTTP client

Calls the thandev-brain service for scan planning and report prompt generation.
"""
import logging
import httpx
from typing import Dict, Any, Optional, List
from pathlib import Path

from app.core.config import settings
import sys
from pathlib import Path

# Add packages to path
packages_path = Path(__file__).parent.parent.parent.parent / "packages"
if str(packages_path) not in sys.path:
    sys.path.insert(0, str(packages_path))

from thandev_schemas.planning import PlanScanRequest, PlanScanResponse

logger = logging.getLogger(__name__)


class BrainClient:
    """HTTP client for thandev-brain service"""
    
    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize brain client.
        
        Args:
            base_url: Base URL of brain service. If None, uses settings.BRAIN_SERVICE_URL.
        """
        self.base_url = (base_url or settings.BRAIN_SERVICE_URL).rstrip("/")
        self.timeout = settings.BRAIN_SERVICE_TIMEOUT
    
    async def create_plan(
        self,
        target_url: str,
        scan_level: str,
        org_id: Optional[str] = None,
        project_id: Optional[str] = None,
        stack_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Request a scan plan from the brain service.
        
        Args:
            target_url: Target URL to scan
            scan_level: Scan level (basic, pro, advanced)
            org_id: Organization ID (optional)
            project_id: Project ID (optional)
            stack_info: Target stack information (optional)
            
        Returns:
            PlanScanResponse as dict
            
        Raises:
            httpx.HTTPError: If request fails
            ValueError: If response is invalid
        """
        endpoint = f"{self.base_url}/v1/plan-scan"
        
        request_data = PlanScanRequest(
            target_url=target_url,
            scan_level=scan_level,
            org_id=org_id,
            project_id=project_id,
            stack_info=stack_info or {},
        )
        
        logger.info(f"Requesting plan from brain service: {endpoint}")
        logger.debug(f"Plan request: target_url={target_url}, scan_level={scan_level}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint,
                    json=request_data.model_dump(exclude_none=True),
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Validate response structure
                plan_response = PlanScanResponse(**data)
                
                logger.info(
                    f"Received plan from brain: {len(plan_response.steps)} steps, "
                    f"{plan_response.timeline.total_estimated_sec}s estimated"
                )
                
                return plan_response.model_dump()
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Brain service returned error: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Failed to connect to brain service: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling brain service: {e}", exc_info=True)
            raise
    
    async def build_report_prompt(
        self,
        scan_job_id: str,
        finding_ids: list[str],
        artifact_refs: Optional[list[Dict[str, Any]]] = None,
        org_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Request a report prompt package from the brain service.
        
        Args:
            scan_job_id: Scan job ID
            finding_ids: List of finding IDs to include
            artifact_refs: List of artifact references (optional)
            org_id: Organization ID (optional)
            project_id: Project ID (optional)
            
        Returns:
            BuildReportPromptResponse as dict
            
        Raises:
            httpx.HTTPError: If request fails
        """
        from thandev_schemas.reporting import BuildReportPromptRequest
        
        endpoint = f"{self.base_url}/v1/build-report-prompt"
        
        request_data = BuildReportPromptRequest(
            scan_job_id=scan_job_id,
            finding_ids=finding_ids,
            artifact_refs=artifact_refs or [],
            org_id=org_id,
            project_id=project_id,
        )
        
        logger.info(f"Requesting report prompt from brain service: {endpoint}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint,
                    json=request_data.model_dump(exclude_none=True),
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                
                data = response.json()
                logger.info(f"Received report prompt package from brain")
                
                return data
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Brain service returned error: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Failed to connect to brain service: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling brain service: {e}", exc_info=True)
            raise
    
    async def start_session(
        self,
        scan_job_id: str,
        target_url: str,
        scan_level: str,
        org_id: Optional[str] = None,
        project_id: Optional[str] = None,
        stack_info: Optional[Dict[str, Any]] = None,
        policy: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Start a brain-controlled scan session.
        
        PR-4E: Core calls this to start a brain-owned closed-loop scan.
        The brain will own the loop and decide steps based on results + RAG.
        
        Args:
            scan_job_id: Scan job ID from core
            target_url: Target URL to scan
            scan_level: Scan level (basic, pro, advanced)
            org_id: Organization ID (optional)
            project_id: Project ID (optional)
            stack_info: Target stack information (optional)
            policy: Scan policy (max_steps, max_runtime, etc.) (optional)
            
        Returns:
            Dict with session_id and status
            
        Raises:
            httpx.HTTPError: If request fails
        """
        endpoint = f"{self.base_url}/v1/sessions/start"
        
        payload = {
            "scan_job_id": scan_job_id,
            "target_url": target_url,
            "scan_level": scan_level,
        }
        if org_id:
            payload["org_id"] = org_id
        if project_id:
            payload["project_id"] = project_id
        if stack_info:
            payload["stack_info"] = stack_info
        if policy:
            payload["policy"] = policy
        
        logger.info(f"Starting brain session for scan_job {scan_job_id}: {endpoint}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                
                data = response.json()
                logger.info(f"Brain session started: {data.get('session_id')}")
                
                return data
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Brain service returned error: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Failed to connect to brain service: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling brain service: {e}", exc_info=True)
            raise
    
    async def get_session(
        self,
        session_id: str,
        org_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get brain session status.
        
        Args:
            session_id: Session ID
            org_id: Organization ID (optional, for filtering)
            project_id: Project ID (optional, for filtering)
            
        Returns:
            Dict with session status, or None if session not found (404)
            
        Raises:
            httpx.HTTPError: If request fails (except 404)
        """
        endpoint = f"{self.base_url}/v1/sessions/{session_id}"
        
        params = {}
        if org_id:
            params["org_id"] = org_id
        if project_id:
            params["project_id"] = project_id
        
        logger.info(f"Getting brain session status: {endpoint}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    endpoint,
                    params=params,
                )
                
                # Handle 404 gracefully - session not found is a valid state
                if response.status_code == 404:
                    logger.debug(f"Brain session {session_id} not found (404) - may have expired or never existed")
                    return None
                
                response.raise_for_status()
                
                data = response.json()
                return data
                
        except httpx.HTTPStatusError as e:
            # Only log non-404 errors as errors
            if e.response.status_code != 404:
                logger.error(f"Brain service returned error: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Failed to connect to brain service: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling brain service: {e}", exc_info=True)
            raise
    
    async def stop_session(
        self,
        session_id: str,
        org_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Stop a brain session gracefully.
        
        Args:
            session_id: Session ID to stop
            org_id: Organization ID (optional, for filtering)
            project_id: Project ID (optional, for filtering)
            
        Returns:
            Dict with stop response (session_id, status, message)
            
        Raises:
            httpx.HTTPError: If request fails
        """
        endpoint = f"{self.base_url}/v1/sessions/{session_id}/stop"
        
        params = {}
        if org_id:
            params["org_id"] = org_id
        if project_id:
            params["project_id"] = project_id
        
        logger.info(f"Stopping brain session: {endpoint}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint,
                    params=params,
                )
                
                # Handle 404 gracefully - session may have already been stopped or expired
                if response.status_code == 404:
                    logger.debug(f"Brain session {session_id} not found (404) - may have already been stopped")
                    return {
                        "session_id": session_id,
                        "status": "stopped",
                        "message": "Session not found (may have already been stopped)",
                    }
                
                response.raise_for_status()
                
                data = response.json()
                logger.info(f"Brain session {session_id} stopped: {data.get('status')}")
                return data
                
        except httpx.HTTPStatusError as e:
            # Log error but don't fail if session is already stopped
            if e.response.status_code == 404:
                logger.debug(f"Brain session {session_id} not found (404) - may have already been stopped")
                return {
                    "session_id": session_id,
                    "status": "stopped",
                    "message": "Session not found (may have already been stopped)",
                }
            logger.error(f"Brain service returned error: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Failed to connect to brain service: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling brain service: {e}", exc_info=True)
            raise
    
    async def ingest_documents(
        self,
        findings: Optional[List[Dict[str, Any]]] = None,
        artifact_summaries: Optional[List[Dict[str, Any]]] = None,
        tech_fingerprints: Optional[List[Dict[str, Any]]] = None,
        org_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Ingest documents into brain RAG store.
        
        Args:
            findings: List of finding dicts
            artifact_summaries: List of artifact summary dicts
            tech_fingerprints: List of tech fingerprint dicts
            org_id: Organization ID (optional)
            project_id: Project ID (optional)
            
        Returns:
            Dict with ingestion results
            
        Raises:
            httpx.HTTPError: If request fails
        """
        endpoint = f"{self.base_url}/v1/rag/ingest"
        
        payload = {}
        if findings:
            payload["findings"] = findings
        if artifact_summaries:
            payload["artifact_summaries"] = artifact_summaries
        if tech_fingerprints:
            payload["tech_fingerprints"] = tech_fingerprints
        if org_id:
            payload["org_id"] = org_id
        if project_id:
            payload["project_id"] = project_id
        
        logger.info(f"Ingesting documents to brain service: {endpoint}")
        logger.debug(f"Payload: {len(findings or [])} findings, {len(artifact_summaries or [])} artifacts, {len(tech_fingerprints or [])} fingerprints")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                
                data = response.json()
                logger.info(f"Ingested {data.get('total_ingested', 0)} documents into brain RAG")
                
                return data
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Brain service returned error: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Failed to connect to brain service: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling brain service: {e}", exc_info=True)
            raise
    
    async def enrich_findings(
        self,
        findings: List[Dict[str, Any]],
        org_id: Optional[str] = None,
        project_id: Optional[str] = None,
        target_url: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Call brain /v1/enrich-findings to get AI-generated impact summaries and remediation guidance.
        
        Args:
            findings: List of finding dicts with keys: id, title, description, severity, tool_name,
                     vuln_type, url, parameter, target_url, project_id, org_id, raw_data (dict)
            org_id: Organization ID (optional, for RAG filtering)
            project_id: Project ID (optional, for RAG filtering)
            target_url: Target URL (optional, for RAG filtering)
            
        Returns:
            Dict mapping finding_id -> enriched data dict with keys:
                - impact_summary: str
                - remediation_summary: str
                - remediation_steps: List[str]
                - ai_source: str (e.g., "brain_v1")
                - ai_model: str (e.g., "gpt-4o-mini")
                - confidence: float (0.0-1.0)
            
            Returns empty dict {} if brain is disabled, unreachable, or returns error.
            Does NOT raise exceptions - caller should handle empty dict as fallback signal.
        """
        if not settings.BRAIN_SERVICE_ENABLED:
            logger.debug("Brain service is disabled, skipping enrichment")
            return {}
        
        endpoint = f"{self.base_url}/v1/enrich-findings"
        
        payload = {
            "findings": findings,
        }
        if org_id:
            payload["org_id"] = org_id
        if project_id:
            payload["project_id"] = project_id
        if target_url:
            payload["target_url"] = target_url
        
        logger.info(f"Enriching {len(findings)} findings via brain service: {endpoint}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Convert response.items list to dict keyed by finding_id
                enriched_dict = {}
                for item in data.get("items", []):
                    finding_id = item.get("finding_id")
                    if finding_id:
                        enriched_dict[finding_id] = {
                            "impact_summary": item.get("impact_summary"),
                            "remediation_summary": item.get("remediation_summary"),
                            "remediation_steps": item.get("remediation_steps", []),
                            "ai_source": item.get("ai_source"),
                            "ai_model": item.get("ai_model"),
                            "confidence": item.get("confidence"),
                        }
                
                logger.info(f"Successfully enriched {len(enriched_dict)} findings")
                return enriched_dict
                
        except httpx.HTTPStatusError as e:
            logger.warning(f"Brain service returned error: {e.response.status_code} - {e.response.text}")
            return {}  # Return empty dict, don't raise
        except httpx.RequestError as e:
            logger.warning(f"Failed to connect to brain service for enrichment: {e}")
            return {}  # Return empty dict, don't raise
        except Exception as e:
            logger.warning(f"Unexpected error calling brain enrichment: {e}", exc_info=True)
            return {}  # Return empty dict, don't raise


# Singleton instance
_brain_client: Optional[BrainClient] = None


def get_brain_client() -> BrainClient:
    """
    Get or create brain client singleton.
    
    Returns:
        BrainClient instance
    """
    global _brain_client
    if _brain_client is None:
        _brain_client = BrainClient()
    return _brain_client
