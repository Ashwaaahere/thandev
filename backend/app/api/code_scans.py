"""
Code Scan API: OIDC exchange, ingest, and linked-repo allowlist.

- POST /api/code-scans/oidc/exchange/{provider}: exchange OIDC token for short-lived ingest token.
- POST /api/code-scans/ingest: ingest code scan payload (Bearer ingest token).
- POST /api/code-scans/link-repo: link a repo to a project (GitHub OAuth user).
- GET /api/code-scans/linked-repos: list linked repos for a project.
"""
import json
import logging
import os
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, status, Form, UploadFile, File, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.tenant_utils import require_tenant, get_current_user
from app.core.dependencies import require_approved_user
from app.models.user import User
from app.models.tenant import Tenant
from app.models.project import Project
from app.models.linked_repo import LinkedRepo
from app.models.code_scan import CodeScan

logger = logging.getLogger(__name__)

CODE_INGEST_PREFIX = "thandev:code_ingest:"
CODE_INGEST_TTL = 600  # 10 minutes


def _redis():
    from app.services.dependency_scanner import get_redis_client
    return get_redis_client()


# ---- Schemas ----

class OIDCExchangeRequest(BaseModel):
    oidc_token: str = Field(..., description="JWT from CI OIDC or 'dev-local' for local testing")
    repo_full_name: Optional[str] = Field(None, description="Required in dev mode when using dev-local token")


class OIDCExchangeResponse(BaseModel):
    access_token: str
    expires_in: int = CODE_INGEST_TTL


class LinkRepoRequest(BaseModel):
    project_id: str = Field(..., description="Project to link")
    provider: str = Field(..., description="CI provider: github, bitbucket, gitlab, circleci, azuredevops")
    repo_full_name: str = Field(..., description="Provider-native repo identifier (e.g. owner/repo)")


class UnlinkRepoRequest(BaseModel):
    """Body for unlink (alternative to DELETE /linked-repos/{id})."""
    linked_repo_id: str = Field(..., description="Linked repo row ID to remove")


class LinkedRepoItem(BaseModel):
    id: str
    project_id: str
    provider: str
    repo_full_name: str
    is_enabled: bool
    allowed_refs: Optional[List[str]] = None
    allowed_workflows: Optional[List[str]] = None
    created_at: str
    updated_at: str


class LinkedReposResponse(BaseModel):
    items: List[LinkedRepoItem]


class CodeScanItem(BaseModel):
    id: str
    project_id: str
    scan_type: str
    provider: str
    repo_full_name: str
    ref: Optional[str]
    sha: Optional[str]
    run_id: Optional[str]
    status: str
    summary_json: Optional[Dict[str, Any]]
    meta_json: Optional[Dict[str, Any]]
    created_at: str
    completed_at: Optional[str]


class CodeScansListResponse(BaseModel):
    items: List[CodeScanItem]
    total: int


# ---- Normalized findings schemas ----

class FindingLocationOut(BaseModel):
    file_path: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    start_col: Optional[int] = None
    end_col: Optional[int] = None
    manifest_path: Optional[str] = None


class FindingDependencyOut(BaseModel):
    package: Optional[str] = None
    ecosystem: Optional[str] = None
    installed_version: Optional[str] = None
    fixed_version: Optional[str] = None
    dependency_chain: Optional[List[str]] = None


class FindingRemediationOut(BaseModel):
    recommendation: Optional[str] = None
    command: Optional[str] = None


class FindingEvidenceOut(BaseModel):
    snippet: Optional[str] = None
    snippet_start_line: Optional[int] = None
    raw: Optional[Dict[str, Any]] = None


class FindingIdentifiersOut(BaseModel):
    cve: List[str] = []
    ghsa: List[str] = []
    osv: List[str] = []
    rule_id: Optional[str] = None


class CodeFindingOut(BaseModel):
    id: str
    scan_id: str
    source_tool: str  # semgrep | gitleaks | osv | trivy
    category: str  # sast | secret | dependency | misconfig | sbom
    severity: str
    confidence: Optional[str] = None
    title: str
    summary: Optional[str] = None
    identifiers: FindingIdentifiersOut
    location: FindingLocationOut
    dependency: FindingDependencyOut
    remediation: FindingRemediationOut
    references: List[str] = []
    evidence: FindingEvidenceOut


class FindingsCountsOut(BaseModel):
    total: int
    critical: int
    high: int
    medium: int
    low: int
    info: int
    secrets: int


class FindingsListResponse(BaseModel):
    counts: FindingsCountsOut
    findings: List[CodeFindingOut]


# ---- Router ----

router = APIRouter(
    prefix="/code-scans",
    tags=["code-scans"],
)


# ---- Health (no auth; for debugging route registration) ----

@router.get("/ping")
async def code_scans_ping():
    """Return 200 so clients can verify /api/code-scans router is mounted."""
    return {"ok": True, "service": "code-scans"}


# ---- OIDC Exchange (no tenant/user auth; public endpoint called by CI) ----

@router.post("/oidc/exchange/{provider}", response_model=OIDCExchangeResponse)
async def oidc_exchange(
    provider: str,
    body: OIDCExchangeRequest,
    db: Session = Depends(get_db),
):
    """
    Exchange CI OIDC token for a short-lived ingest token.

    - dev (CODE_SCAN_OIDC_MODE=dev): accept oidc_token == "dev-local", require repo_full_name in body or allowlist lookup.
    - prod: verify JWT with provider JWKS/issuer/audience, then allowlist check.
    """
    provider_lower = provider.lower().strip()
    if provider_lower not in {"github", "bitbucket", "gitlab", "circleci", "azuredevops"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider: {provider}. Use one of: github, bitbucket, gitlab, circleci, azuredevops",
        )

    mode = (os.getenv("CODE_SCAN_OIDC_MODE") or getattr(settings, "CODE_SCAN_OIDC_MODE", "prod")).lower()

    if mode == "dev":
        if body.oidc_token != "dev-local":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="In dev mode, oidc_token must be 'dev-local'",
            )
        repo_full_name = body.repo_full_name
        if not repo_full_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="In dev mode, repo_full_name is required in the request body",
            )
        # Look up linked_repos: any project that has this provider + repo_full_name enabled
        linked = (
            db.query(LinkedRepo)
            .filter(
                LinkedRepo.provider == provider_lower,
                LinkedRepo.repo_full_name == repo_full_name,
                LinkedRepo.is_enabled == True,
            )
            .first()
        )
        if not linked:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Repo not linked in Thandev. Link this repo in the Code Scan setup for your project.",
            )
        project_id = linked.project_id
        payload_repo = repo_full_name
    else:
        # prod: verify JWT
        from app.security.oidc_providers import (
            verify_oidc_token_and_extract,
            get_provider_config,
            SUPPORTED_PROVIDERS,
            OIDCJWKSFetchError,
        )
        if provider_lower not in SUPPORTED_PROVIDERS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported provider: {provider}")
        config = get_provider_config(provider_lower)
        if not config or not config.implemented:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail=f"OIDC provider '{provider_lower}' not enabled yet. Enable by implementing claim extraction + issuer/JWKS validation.",
            )
        try:
            claims = verify_oidc_token_and_extract(provider_lower, body.oidc_token)
        except NotImplementedError as e:
            raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(e))
        except OIDCJWKSFetchError as e:
            # Upstream JWKS/discovery failure – treat as backend service issue
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"OIDC JWKS unavailable: {e}",
            )
        except ValueError as e:
            # Signature/claims/issuer/audience problems – invalid token
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"OIDC verification failed: {e}",
            )
        repo_full_name = claims.get("repo_full_name")
        if not repo_full_name:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="OIDC token missing repository identity")
        # Allowlist check
        linked = (
            db.query(LinkedRepo)
            .filter(
                LinkedRepo.provider == provider_lower,
                LinkedRepo.repo_full_name == repo_full_name,
                LinkedRepo.is_enabled == True,
            )
            .first()
        )
        if not linked:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Repo not linked in Thandev. Link this repo in the Code Scan setup for your project.",
            )
        project_id = linked.project_id
        payload_repo = repo_full_name

    # Mint opaque ingest token in Redis
    token = secrets.token_urlsafe(32)
    redis_client = _redis()
    if not redis_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Token storage unavailable (Redis not configured)",
        )
    key = f"{CODE_INGEST_PREFIX}{token}"
    value = json.dumps({"project_id": project_id, "provider": provider_lower, "repo_full_name": payload_repo})
    redis_client.setex(key, CODE_INGEST_TTL, value)
    return OIDCExchangeResponse(access_token=token, expires_in=CODE_INGEST_TTL)


@router.get("/debug-token")
async def debug_token(token: str = Query(..., description="JWT to decode without verification")):
    """
    Decode a JWT without verifying its signature.

    This endpoint is only available when OIDC_DEBUG=1 and is intended for local debugging.
    """
    if (os.getenv("OIDC_DEBUG") or "").strip().lower() not in ("1", "true", "yes"):
        # Hide existence of this endpoint when not explicitly enabled.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    try:
        import jwt  # Local import to avoid hard dependency if unused

        header = jwt.get_unverified_header(token)
        payload = jwt.decode(token, options={"verify_signature": False})
        return {"header": header, "payload": payload}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse token: {type(e).__name__}",
        ) from e


def _get_ingest_payload(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """Validate Bearer token and return Redis payload (project_id, provider, repo_full_name)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization: Bearer <ingest_token> required",
        )
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")
    redis_client = _redis()
    if not redis_client:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Token storage unavailable")
    key = f"{CODE_INGEST_PREFIX}{token}"
    raw = redis_client.get(key)
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired ingest token")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        redis_client.delete(key)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    for k in ("project_id", "provider", "repo_full_name"):
        if k not in payload:
            redis_client.delete(key)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    return payload


# ---- Ingest (Bearer ingest token only) ----

@router.post("/ingest", status_code=status.HTTP_201_CREATED)
async def ingest(
    authorization: Optional[str] = Header(None),
    repo: str = Form(..., description="MUST match repo_full_name from token"),
    provider: Optional[str] = Form(None),
    ref: Optional[str] = Form(None),
    sha: Optional[str] = Form(None),
    run_id: Optional[str] = Form(None),
    workflow: Optional[str] = Form(None),
    actor: Optional[str] = Form(None),
    run_url: Optional[str] = Form(None),
    semgrep_json: Optional[UploadFile] = File(None),
    gitleaks_json: Optional[UploadFile] = File(None),
    osv_json: Optional[UploadFile] = File(None),
    trivy_json: Optional[UploadFile] = File(None),
    sbom_json: Optional[UploadFile] = File(None),
    sarif_json: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    """
    Ingest code scan artifacts. Authorization: Bearer <opaque_ingest_token from OIDC exchange>.
    Validates repo (and optional provider) against token; creates CodeScan and stores artifacts.
    """
    payload = _get_ingest_payload(authorization)
    if repo != payload["repo_full_name"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="repo does not match token; ingestion rejected",
        )
    if provider is not None and provider.lower() != payload["provider"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="provider does not match token; ingestion rejected",
        )

    project_id = payload["project_id"]
    provider_lower = payload["provider"]
    repo_full_name = payload["repo_full_name"]

    # Ensure project exists
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Build meta from form + optional file contents (store raw JSON in meta_json for now)
    meta: Dict[str, Any] = {
        "pipeline_run_url": run_url,
        "actor": actor,
        "workflow": workflow,
    }
    artifacts: Dict[str, Any] = {}

    async def _read_json_file(upload: Optional[UploadFile]) -> Optional[Any]:
        if not upload or upload.filename == "":
            return None
        try:
            body = await upload.read()
            return json.loads(body.decode("utf-8")) if body else None
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    for name, upl in [
        ("semgrep", semgrep_json),
        ("gitleaks", gitleaks_json),
        ("osv", osv_json),
        ("trivy", trivy_json),
        ("sbom", sbom_json),
        ("sarif", sarif_json),
    ]:
        data = await _read_json_file(upl)
        if data is not None:
            artifacts[name] = data

    # If workflow only uploaded SARIF (e.g. gitleaks action outputs results.sarif), use it for gitleaks tab
    if "gitleaks" not in artifacts and "sarif" in artifacts:
        artifacts["gitleaks"] = artifacts["sarif"]

    meta["artifacts"] = artifacts

    # Summary counts (placeholder; can be refined from artifact contents later)
    summary: Dict[str, Any] = {"sources": []}
    if "semgrep" in artifacts:
        summary["sources"].append("semgrep")
    if "gitleaks" in artifacts:
        summary["sources"].append("gitleaks")
    if "osv" in artifacts or "trivy" in artifacts:
        summary["sources"].append("sca")
    if "sbom" in artifacts:
        summary["sources"].append("sbom")

    # Create CodeScan
    import uuid
    scan_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    code_scan = CodeScan(
        id=scan_id,
        project_id=project_id,
        scan_type="code",
        provider=provider_lower,
        repo_full_name=repo_full_name,
        ref=ref,
        sha=sha,
        run_id=run_id,
        status="completed",
        summary_json=summary,
        meta_json=meta,
        created_at=now,
        updated_at=now,
        completed_at=now,
    )
    db.add(code_scan)
    db.commit()
    db.refresh(code_scan)
    return {"id": code_scan.id, "status": "completed", "project_id": project_id}


# ---- Link repo & list (require GitHub OAuth user) ----

@router.post("/link-repo", status_code=status.HTTP_201_CREATED)
async def link_repo(
    body: LinkRepoRequest,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(require_approved_user),
):
    """Link a repo to a project for code scan ingestion (allowlist)."""
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    provider_lower = body.provider.lower().strip()
    if provider_lower not in {"github", "bitbucket", "gitlab", "circleci", "azuredevops"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid provider")
    project = (
        db.query(Project)
        .filter(
            Project.id == body.project_id,
            Project.tenant_id == tenant.id,
            Project.owner_id == current_user.id,
        )
        .first()
    )
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    existing = (
        db.query(LinkedRepo)
        .filter(
            LinkedRepo.project_id == body.project_id,
            LinkedRepo.provider == provider_lower,
            LinkedRepo.repo_full_name == body.repo_full_name.strip(),
        )
        .first()
    )
    if existing:
        existing.is_enabled = True
        db.commit()
        db.refresh(existing)
        return {
            "id": existing.id,
            "project_id": existing.project_id,
            "provider": existing.provider,
            "repo_full_name": existing.repo_full_name,
            "is_enabled": existing.is_enabled,
            "created_at": existing.created_at.isoformat(),
            "updated_at": existing.updated_at.isoformat(),
        }
    linked = LinkedRepo(
        project_id=body.project_id,
        provider=provider_lower,
        repo_full_name=body.repo_full_name.strip(),
        is_enabled=True,
    )
    db.add(linked)
    db.commit()
    db.refresh(linked)
    return {
        "id": linked.id,
        "project_id": linked.project_id,
        "provider": linked.provider,
        "repo_full_name": linked.repo_full_name,
        "is_enabled": linked.is_enabled,
        "created_at": linked.created_at.isoformat(),
        "updated_at": linked.updated_at.isoformat(),
    }


@router.get("/scans", response_model=CodeScansListResponse)
async def list_code_scans(
    project_id: str = Query(..., description="Project ID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(require_approved_user),
):
    """List code scans for a project (with provider badge info for UI)."""
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    project = (
        db.query(Project)
        .filter(
            Project.id == project_id,
            Project.tenant_id == tenant.id,
            Project.owner_id == current_user.id,
        )
        .first()
    )
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    q = db.query(CodeScan).filter(CodeScan.project_id == project_id)
    total = q.count()
    rows = q.order_by(CodeScan.created_at.desc()).offset(offset).limit(limit).all()
    items = [
        CodeScanItem(
            id=r.id,
            project_id=r.project_id,
            scan_type=r.scan_type or "code",
            provider=r.provider,
            repo_full_name=r.repo_full_name,
            ref=r.ref,
            sha=r.sha,
            run_id=r.run_id,
            status=r.status,
            summary_json=r.summary_json,
            meta_json=r.meta_json,
            created_at=r.created_at.isoformat(),
            completed_at=r.completed_at.isoformat() if r.completed_at else None,
        )
        for r in rows
    ]
    return CodeScansListResponse(items=items, total=total)


@router.get("/scans/{scan_id}", response_model=CodeScanItem)
async def get_code_scan(
    scan_id: str,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(require_approved_user),
):
    """
    Return details for a single code scan, including summary and meta (artifacts).
    """
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    scan = db.query(CodeScan).filter(CodeScan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Code scan not found")

    project = (
        db.query(Project)
        .filter(
            Project.id == scan.project_id,
            Project.tenant_id == tenant.id,
            Project.owner_id == current_user.id,
        )
        .first()
    )
    if not project:
        # Either project does not exist or user is not allowed to see it
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Code scan not found")

    return CodeScanItem(
        id=scan.id,
        project_id=scan.project_id,
        scan_type=scan.scan_type or "code",
        provider=scan.provider,
        repo_full_name=scan.repo_full_name,
        ref=scan.ref,
        sha=scan.sha,
        run_id=scan.run_id,
        status=scan.status,
        summary_json=scan.summary_json,
        meta_json=scan.meta_json,
        created_at=scan.created_at.isoformat(),
        completed_at=scan.completed_at.isoformat() if scan.completed_at else None,
    )


def _get_scan_and_ensure_access(
    scan_id: str,
    db: Session,
    tenant: Tenant,
    current_user: User,
) -> CodeScan:
    """Return CodeScan if exists and user has access via project. Raises 404/403 otherwise."""
    scan = db.query(CodeScan).filter(CodeScan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Code scan not found")
    project = (
        db.query(Project)
        .filter(
            Project.id == scan.project_id,
            Project.tenant_id == tenant.id,
            Project.owner_id == current_user.id,
        )
        .first()
    )
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Code scan not found")
    return scan


# In-memory cache for normalized findings per scan_id (no TTL for simplicity; can add later)
_findings_cache: Dict[str, List[Dict[str, Any]]] = {}


@router.get("/scans/{scan_id}/findings", response_model=FindingsListResponse)
async def get_scan_findings(
    scan_id: str,
    source_tool: Optional[str] = Query(None, description="Filter by tool: semgrep, gitleaks, osv, trivy"),
    category: Optional[str] = Query(None, description="Filter by category: sast, secret, dependency, misconfig"),
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(require_approved_user),
):
    """Return normalized findings for a code scan. Counts and list; optional filters."""
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    scan = _get_scan_and_ensure_access(scan_id, db, tenant, current_user)
    artifacts = (scan.meta_json or {}).get("artifacts") or {}
    from app.services.code_scan_normalizer import normalize_all_findings, get_counts
    if scan_id not in _findings_cache:
        _findings_cache[scan_id] = normalize_all_findings(artifacts, scan_id)
    findings = list(_findings_cache[scan_id])
    if source_tool:
        tool_lower = source_tool.lower().strip()
        findings = [f for f in findings if (f.get("source_tool") or "").lower() == tool_lower]
    if category:
        cat_lower = category.lower().strip()
        findings = [f for f in findings if (f.get("category") or "").lower() == cat_lower]
    all_cached = _findings_cache.get(scan_id) or []
    counts_dict = get_counts(all_cached)
    findings_out = [CodeFindingOut(**f) for f in findings]
    return FindingsListResponse(
        counts=FindingsCountsOut(**counts_dict),
        findings=findings_out,
    )


@router.get("/scans/{scan_id}/findings/{finding_id}", response_model=CodeFindingOut)
async def get_scan_finding(
    scan_id: str,
    finding_id: str,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(require_approved_user),
):
    """Return a single normalized finding by id."""
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    scan = _get_scan_and_ensure_access(scan_id, db, tenant, current_user)
    if scan_id not in _findings_cache:
        from app.services.code_scan_normalizer import normalize_all_findings
        artifacts = (scan.meta_json or {}).get("artifacts") or {}
        _findings_cache[scan_id] = normalize_all_findings(artifacts, scan_id)
    for f in _findings_cache[scan_id]:
        if f.get("id") == finding_id:
            return CodeFindingOut(**f)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found")


@router.get("/scans/{scan_id}/sbom")
async def get_scan_sbom(
    scan_id: str,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(require_approved_user),
):
    """Return SBOM components for the scan (from sbom artifact)."""
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    scan = _get_scan_and_ensure_access(scan_id, db, tenant, current_user)
    artifacts = (scan.meta_json or {}).get("artifacts") or {}
    sbom_data = artifacts.get("sbom")
    from app.services.code_scan_normalizer import get_sbom_components
    components = get_sbom_components(sbom_data)
    return {"scan_id": scan_id, "total": len(components), "components": components}


def _unlink_repo_by_id(
    linked_repo_id: str,
    db: Session,
    tenant: Tenant,
    current_user: User,
) -> None:
    """Look up linked repo by id; allow delete if project is in same tenant OR user is project owner. Raises 404/403."""
    raw_id = (linked_repo_id or "").strip()
    if not raw_id:
        logger.warning("Unlink: empty linked_repo_id")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="linked_repo_id is required")
    linked = db.query(LinkedRepo).filter(LinkedRepo.id == raw_id).first()
    if not linked:
        logger.warning(
            "Unlink: linked_repo not found by id. linked_repo_id=%r tenant_id=%s user_id=%s",
            raw_id,
            tenant.id,
            current_user.id,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linked repo not found")
    project = db.query(Project).filter(Project.id == linked.project_id).first()
    if not project:
        logger.warning("Unlink: project not found for linked_repo. project_id=%s", linked.project_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    allowed = (project.tenant_id == tenant.id) or (project.owner_id == current_user.id)
    if not allowed:
        logger.warning(
            "Unlink: forbidden. linked_repo_id=%s project_id=%s project_tenant=%s project_owner=%s request_tenant=%s user=%s",
            raw_id,
            project.id,
            project.tenant_id,
            project.owner_id,
            tenant.id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to unlink this repo",
        )
    logger.info(
        "Unlink: deleting linked_repo id=%s project_id=%s repo=%s",
        linked.id,
        linked.project_id,
        linked.repo_full_name,
    )
    db.delete(linked)
    db.commit()


@router.post("/unlink-repo")
async def unlink_repo_post(
    body: UnlinkRepoRequest,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(require_approved_user),
):
    """Remove a linked repo by id (delete row). Does not delete code scans."""
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    logger.info(
        "Unlink request: linked_repo_id=%s tenant_id=%s user_id=%s",
        body.linked_repo_id,
        tenant.id,
        current_user.id,
    )
    _unlink_repo_by_id(body.linked_repo_id, db, tenant, current_user)
    return {"ok": True}


@router.delete("/linked-repos/{linked_repo_id}")
async def unlink_repo(
    linked_repo_id: str,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(require_approved_user),
):
    """Remove a linked repo (delete row). Does not delete code scans."""
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    _unlink_repo_by_id(linked_repo_id, db, tenant, current_user)
    return {"ok": True}


@router.get("/linked-repos", response_model=LinkedReposResponse)
async def list_linked_repos(
    project_id: str = Query(..., description="Project ID"),
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(require_approved_user),
):
    """List linked repos for a project."""
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    project = (
        db.query(Project)
        .filter(
            Project.id == project_id,
            Project.tenant_id == tenant.id,
            Project.owner_id == current_user.id,
        )
        .first()
    )
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    rows = (
        db.query(LinkedRepo)
        .filter(LinkedRepo.project_id == project_id)
        .order_by(LinkedRepo.created_at.desc())
        .all()
    )
    items = [
        LinkedRepoItem(
            id=r.id,
            project_id=r.project_id,
            provider=r.provider,
            repo_full_name=r.repo_full_name,
            is_enabled=r.is_enabled,
            allowed_refs=r.allowed_refs if isinstance(r.allowed_refs, list) else None,
            allowed_workflows=r.allowed_workflows if isinstance(r.allowed_workflows, list) else None,
            created_at=r.created_at.isoformat(),
            updated_at=r.updated_at.isoformat(),
        )
        for r in rows
    ]
    return LinkedReposResponse(items=items)
