"""
OIDC provider configurations for CI code-scan ingestion.

- GitHub: full implementation (issuer, JWKS, audience, claim extraction).
- Bitbucket, GitLab, CircleCI, Azure DevOps: stubs (config + TODO claim mapping);
  in prod mode they return a clear 501 until implemented.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

# Supported provider slugs (path segment)
SUPPORTED_PROVIDERS = frozenset({"github", "bitbucket", "gitlab", "circleci", "azuredevops"})


@dataclass
class OIDCProviderConfig:
    """Configuration for one CI provider's OIDC tokens."""
    provider: str
    issuer: str
    jwks_url: str
    expected_audience: str  # e.g. "thandev"
    # Extract repo identity + metadata from verified JWT payload -> dict with repo_full_name, ref, sha, etc.
    claim_extractor: Callable[[Dict[str, Any]], Dict[str, Any]]
    # True if fully implemented and safe for prod
    implemented: bool = False


def _github_claim_extractor(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Extract repo identity and metadata from GitHub Actions OIDC token payload."""
    repo_full_name = payload.get("repository")
    if not repo_full_name or not isinstance(repo_full_name, str):
        raise ValueError("GitHub OIDC token missing or invalid 'repository' claim")
    out: Dict[str, Any] = {
        "repo_full_name": repo_full_name,
        "repository_owner": payload.get("repository_owner"),
        "ref": payload.get("ref"),
        "sha": payload.get("sha"),
        "workflow": payload.get("workflow"),
        "job_workflow_ref": payload.get("job_workflow_ref"),
        "run_id": payload.get("run_id"),
        "run_number": payload.get("run_number"),
        "actor": payload.get("actor"),
    }
    return out


def _stub_claim_extractor(_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Stub for providers not yet implemented. Raises in prod."""
    raise NotImplementedError(
        "OIDC claim extraction for this provider is not implemented yet. "
        "Use CODE_SCAN_OIDC_MODE=dev for local testing with dev-local token."
    )


# Provider configs
GITHUB_CONFIG = OIDCProviderConfig(
    provider="github",
    issuer="https://token.actions.githubusercontent.com",
    jwks_url="https://token.actions.githubusercontent.com/.well-known/jwks.json",
    expected_audience="thandev",
    claim_extractor=_github_claim_extractor,
    implemented=True,
)

BITBUCKET_CONFIG = OIDCProviderConfig(
    provider="bitbucket",
    issuer="https://api.bitbucket.org/2.0/workspaces/",
    jwks_url="",  # TODO: set when Bitbucket OIDC is documented
    expected_audience="thandev",
    claim_extractor=_stub_claim_extractor,
    implemented=False,
)

GITLAB_CONFIG = OIDCProviderConfig(
    provider="gitlab",
    issuer="https://gitlab.com",
    jwks_url="",  # TODO: set when GitLab OIDC is documented
    expected_audience="thandev",
    claim_extractor=_stub_claim_extractor,
    implemented=False,
)

CIRCLECI_CONFIG = OIDCProviderConfig(
    provider="circleci",
    issuer="https://oidc.circleci.com/org/",
    jwks_url="",  # TODO: set when CircleCI OIDC is documented
    expected_audience="thandev",
    claim_extractor=_stub_claim_extractor,
    implemented=False,
)

AZUREDEVOPS_CONFIG = OIDCProviderConfig(
    provider="azuredevops",
    issuer="https://vstoken.dev.azure.com/",
    jwks_url="",  # TODO: set when Azure DevOps OIDC is documented
    expected_audience="thandev",
    claim_extractor=_stub_claim_extractor,
    implemented=False,
)

PROVIDER_CONFIGS: Dict[str, OIDCProviderConfig] = {
    "github": GITHUB_CONFIG,
    "bitbucket": BITBUCKET_CONFIG,
    "gitlab": GITLAB_CONFIG,
    "circleci": CIRCLECI_CONFIG,
    "azuredevops": AZUREDEVOPS_CONFIG,
}


def get_provider_config(provider: str) -> Optional[OIDCProviderConfig]:
    """Return config for provider slug (lowercase), or None if unsupported."""
    return PROVIDER_CONFIGS.get(provider.lower().strip())


def verify_oidc_token_and_extract(
    provider: str,
    oidc_token: str,
) -> Dict[str, Any]:
    """
    Verify OIDC JWT and return extracted claims (repo_full_name, ref, sha, etc.).

    - Uses provider's issuer, JWKS URL, and expected audience.
    - Raises ValueError if token invalid or provider not implemented in prod.
    - For non-implemented providers, raises with message suitable for 501 response.
    """
    config = get_provider_config(provider)
    if not config:
        raise ValueError(f"Unsupported OIDC provider: {provider}")

    if not config.implemented:
        raise NotImplementedError(
            f"OIDC provider '{provider}' not enabled yet. "
            "Enable by implementing claim extraction + issuer/JWKS validation."
        )

    try:
        import jwt
        from jwt import PyJWKClient
    except ImportError as e:
        raise RuntimeError(
            "PyJWT is required for OIDC verification. Install with: pip install PyJWT cryptography"
        ) from e

    if not config.jwks_url:
        raise NotImplementedError(
            f"OIDC provider '{provider}' has no JWKS URL configured yet."
        )

    try:
        jwks_client = PyJWKClient(config.jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(oidc_token)
    except Exception as e:
        logger.warning("OIDC JWKS fetch or key lookup failed: %s", e)
        raise ValueError("Invalid OIDC token or JWKS unavailable") from e

    try:
        payload = jwt.decode(
            oidc_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=config.expected_audience,
            issuer=config.issuer,
            options={"verify_aud": True, "verify_iss": True, "verify_exp": True},
        )
    except jwt.ExpiredSignatureError as e:
        raise ValueError("OIDC token has expired") from e
    except jwt.InvalidAudienceError as e:
        raise ValueError(f"OIDC token audience must be '{config.expected_audience}'") from e
    except jwt.InvalidIssuerError as e:
        raise ValueError(f"OIDC token issuer must be '{config.issuer}'") from e
    except Exception as e:
        logger.warning("OIDC token decode failed: %s", e)
        raise ValueError("Invalid OIDC token") from e

    return config.claim_extractor(dict(payload))
