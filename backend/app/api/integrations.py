"""
GitHub Integration API endpoints
"""
import logging
import hmac
import hashlib
import os
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Header, Request, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.tenant_utils import require_tenant, get_current_user
from app.core.dependencies import require_approved_user
from app.core.config import settings
from app.models.user import User
from app.models.tenant import Tenant
from app.models.project import Project
from app.models.integration import Integration
from app.models.repo_connection import RepoConnection

router = APIRouter(
    prefix="/integrations",
    tags=["integrations"],
    dependencies=[Depends(require_approved_user)],
)
logger = logging.getLogger(__name__)


class IntegrationStatusResponse(BaseModel):
    """Response for integration status"""
    connected: bool
    provider: str
    installation_id: Optional[str] = None


class RepoInfo(BaseModel):
    """GitHub repository information"""
    id: str
    full_name: str
    default_branch: str
    private: bool


class ReposListResponse(BaseModel):
    """Response for list of available repositories"""
    repos: List[RepoInfo]


class ConnectRepoRequest(BaseModel):
    """Request to connect a repository to a project"""
    provider_repo_id: str = Field(..., description="GitHub repository ID (numeric)")
    full_name: str = Field(..., description="Repository full name (e.g., 'org/repo')")


class RepoConnectionResponse(BaseModel):
    """Response for repo connection"""
    id: str
    project_id: str
    provider: str
    provider_repo_id: str
    full_name: str
    default_branch: Optional[str]
    is_enabled: bool
    created_at: str


class RepoConnectionsListResponse(BaseModel):
    """Response for list of repo connections"""
    items: List[RepoConnectionResponse]


@router.get("/github/status", response_model=IntegrationStatusResponse)
async def get_github_status(
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Get GitHub integration status for the current user.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required"
        )
    
    integration = db.query(Integration).filter(
        Integration.user_id == current_user.id,
        Integration.provider == "github",
        Integration.revoked_at.is_(None),
    ).first()
    
    if integration:
        return IntegrationStatusResponse(
            connected=True,
            provider="github",
            installation_id=integration.installation_id,
        )
    else:
        return IntegrationStatusResponse(
            connected=False,
            provider="github",
        )


@router.post("/github/install-callback")
async def github_install_callback(
    request: Request,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Handle GitHub App installation callback.
    
    This endpoint receives the installation_id from GitHub after app installation.
    For MVP, we'll accept installation_id in the request body.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required"
        )
    
    try:
        body = await request.json()
        installation_id = body.get("installation_id")
        
        if not installation_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="installation_id is required"
            )
        
        # Check if integration already exists
        integration = db.query(Integration).filter(
            Integration.user_id == current_user.id,
            Integration.provider == "github",
        ).first()
        
        if integration:
            # Update existing integration
            integration.installation_id = str(installation_id)
            integration.revoked_at = None
            integration.access_meta = body.get("metadata", {})
        else:
            # Create new integration
            integration = Integration(
                user_id=current_user.id,
                provider="github",
                installation_id=str(installation_id),
                access_meta=body.get("metadata", {}),
            )
            db.add(integration)
        
        db.commit()
        db.refresh(integration)
        
        return {
            "status": "ok",
            "integration_id": integration.id,
            "installation_id": integration.installation_id,
        }
    except Exception as e:
        logger.error(f"Error handling GitHub install callback: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process GitHub installation: {str(e)}"
        )


@router.get("/github/repos", response_model=ReposListResponse)
async def list_github_repos(
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    List GitHub repositories available to the user's installation.
    
    For MVP, returns a placeholder list. In production, this would call
    GitHub API to list repositories accessible to the installation.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required"
        )
    
    integration = db.query(Integration).filter(
        Integration.user_id == current_user.id,
        Integration.provider == "github",
        Integration.revoked_at.is_(None),
    ).first()
    
    if not integration or not integration.installation_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub integration not found. Please install the GitHub App first."
        )
    
    # TODO: Call GitHub API to list repositories
    # For MVP, return empty list
    # In production: GET https://api.github.com/installation/repositories
    # with installation token
    
    return ReposListResponse(repos=[])


@router.post("/projects/{project_id}/repos/connect", response_model=RepoConnectionResponse)
async def connect_repo_to_project(
    project_id: str,
    request: ConnectRepoRequest,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Connect a GitHub repository to a project.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required"
        )
    
    # Verify project exists and belongs to tenant and user
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.tenant_id == tenant.id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found. The project ID '{project_id}' does not exist or you don't have permission to access it."
        )
    
    # Verify GitHub integration exists
    integration = db.query(Integration).filter(
        Integration.user_id == current_user.id,
        Integration.provider == "github",
        Integration.revoked_at.is_(None),
    ).first()
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub integration not found. Please install the GitHub App first."
        )
    
    # Check if connection already exists
    existing = db.query(RepoConnection).filter(
        RepoConnection.project_id == project_id,
        RepoConnection.provider == "github",
        RepoConnection.provider_repo_id == request.provider_repo_id,
    ).first()
    
    if existing:
        # Update existing connection
        existing.full_name = request.full_name
        existing.is_enabled = True
        db.commit()
        db.refresh(existing)
        
        return RepoConnectionResponse(
            id=existing.id,
            project_id=existing.project_id,
            provider=existing.provider,
            provider_repo_id=existing.provider_repo_id,
            full_name=existing.full_name,
            default_branch=existing.default_branch,
            is_enabled=existing.is_enabled,
            created_at=existing.created_at.isoformat(),
        )
    
    # Create new connection
    repo_connection = RepoConnection(
        project_id=project_id,
        provider="github",
        provider_repo_id=request.provider_repo_id,
        full_name=request.full_name,
        default_branch=None,  # Will be fetched from GitHub API
        is_enabled=True,
    )
    
    db.add(repo_connection)
    db.commit()
    db.refresh(repo_connection)
    
    return RepoConnectionResponse(
        id=repo_connection.id,
        project_id=repo_connection.project_id,
        provider=repo_connection.provider,
        provider_repo_id=repo_connection.provider_repo_id,
        full_name=repo_connection.full_name,
        default_branch=repo_connection.default_branch,
        is_enabled=repo_connection.is_enabled,
        created_at=repo_connection.created_at.isoformat(),
    )


@router.get("/projects/{project_id}/repos", response_model=RepoConnectionsListResponse)
async def list_project_repos(
    project_id: str,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    List repository connections for a project.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required"
        )
    
    # Verify project exists and belongs to tenant and user
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.tenant_id == tenant.id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found. The project ID '{project_id}' does not exist or you don't have permission to access it."
        )
    
    # Get repo connections
    connections = db.query(RepoConnection).filter(
        RepoConnection.project_id == project_id
    ).order_by(RepoConnection.created_at).all()
    
    return RepoConnectionsListResponse(
        items=[
            RepoConnectionResponse(
                id=conn.id,
                project_id=conn.project_id,
                provider=conn.provider,
                provider_repo_id=conn.provider_repo_id,
                full_name=conn.full_name,
                default_branch=conn.default_branch,
                is_enabled=conn.is_enabled,
                created_at=conn.created_at.isoformat(),
            )
            for conn in connections
        ]
    )


@router.post("/projects/{project_id}/repos/{repo_connection_id}/disable")
async def disable_repo_connection(
    project_id: str,
    repo_connection_id: str,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Disable a repository connection (soft disable, doesn't delete).
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Thandev-User-Id header is required"
        )
    
    # Verify project exists and belongs to tenant and user
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.tenant_id == tenant.id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found. The project ID '{project_id}' does not exist or you don't have permission to access it."
        )
    
    # Get repo connection
    repo_connection = db.query(RepoConnection).filter(
        RepoConnection.id == repo_connection_id,
        RepoConnection.project_id == project_id,
    ).first()
    
    if not repo_connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repo connection not found. The repo_connection_id '{repo_connection_id}' does not exist or doesn't belong to this project."
        )
    
    repo_connection.is_enabled = False
    db.commit()
    
    return {"status": "ok", "repo_connection_id": repo_connection_id, "is_enabled": False}


@router.get("/github/installation-token")
async def get_github_installation_token(
    installation_id: str = Query(..., description="GitHub App installation ID"),
    db: Session = Depends(get_db),
):
    """
    Get a short-lived GitHub installation token for repository access.
    
    This endpoint is called by the runner service to get an installation token
    for downloading repository archives. The token is short-lived (1 hour).
    
    Note: In production, this should require service authentication (RUNNER_API_TOKEN).
    For MVP, we'll allow it with basic validation.
    """
    import httpx
    
    # Verify installation exists
    integration = db.query(Integration).filter(
        Integration.installation_id == installation_id,
        Integration.provider == "github",
        Integration.revoked_at.is_(None),
    ).first()
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"GitHub installation not found: {installation_id}"
        )
    
    # Get GitHub App credentials from environment
    github_app_id = os.getenv("GITHUB_APP_ID")
    github_app_private_key = os.getenv("GITHUB_APP_PRIVATE_KEY")
    
    if not github_app_id or not github_app_private_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub App credentials not configured"
        )
    
    # Generate JWT for GitHub App authentication
    import jwt
    import time
    
    now = int(time.time())
    jwt_payload = {
        "iat": now - 60,  # Issued at (1 minute ago to account for clock skew)
        "exp": now + 600,  # Expires in 10 minutes
        "iss": github_app_id,  # GitHub App ID
    }
    
    try:
        # Load private key
        if github_app_private_key.startswith("-----BEGIN"):
            private_key = github_app_private_key
        else:
            # Assume it's base64 encoded
            import base64
            private_key = base64.b64decode(github_app_private_key).decode('utf-8')
        
        # Generate JWT
        app_token = jwt.encode(jwt_payload, private_key, algorithm="RS256")
        
        # Exchange JWT for installation token
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"https://api.github.com/app/installations/{installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {app_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
            response.raise_for_status()
            token_data = response.json()
            
            return {
                "token": token_data["token"],
                "expires_at": token_data["expires_at"],
            }
    except Exception as e:
        logger.error(f"Failed to get GitHub installation token: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get installation token: {str(e)}"
        )
