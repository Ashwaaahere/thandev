"""
OIDC provider configurations for CI code-scan ingestion.

- GitHub: full implementation (issuer, JWKS, audience, claim extraction).
- Bitbucket, GitLab, CircleCI, Azure DevOps: stubs (config + TODO claim mapping);
  in prod mode they return a clear 501 until implemented.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple

import httpx
import jwt
from jwt import algorithms

logger = logging.getLogger(__name__)

# Runtime sanity check to ensure we are using PyJWT (not the incompatible 'jwt' package).
if not hasattr(jwt, "algorithms") or not hasattr(jwt.algorithms, "RSAAlgorithm"):
    raise RuntimeError(
        "Incompatible 'jwt' package detected. Expected PyJWT with algorithms.RSAAlgorithm.\n"
        "Ensure PyJWT[crypto]>=2.8.0,<3 is installed and any 'jwt' package is removed."
    )

# Supported provider slugs (path segment)
SUPPORTED_PROVIDERS = frozenset({"github", "bitbucket", "gitlab", "circleci", "azuredevops"})

_DISCOVERY_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_JWKS_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_CACHE_TTL_SECONDS = 600  # 10 minutes


class OIDCJWKSFetchError(Exception):
    """Raised when JWKS (or discovery) cannot be fetched."""


def _oidc_debug_enabled() -> bool:
    """Return True when debug logging for OIDC is enabled."""
    val = os.getenv("OIDC_DEBUG", "").strip().lower()
    return val in ("1", "true", "yes")


def _get_cached(key: str, cache: Dict[str, Tuple[float, Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    entry = cache.get(key)
    if not entry:
        return None
    ts, data = entry
    if time.time() - ts > _CACHE_TTL_SECONDS:
        cache.pop(key, None)
        return None
    return data


def _set_cached(key: str, value: Dict[str, Any], cache: Dict[str, Tuple[float, Dict[str, Any]]]) -> None:
    cache[key] = (time.time(), value)


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


def _get_github_openid_configuration() -> Dict[str, Any]:
    """
    Fetch GitHub Actions OIDC discovery document, with 10 minute in-memory cache.
    """
    discovery_url = "https://token.actions.githubusercontent.com/.well-known/openid-configuration"
    cached = _get_cached(discovery_url, _DISCOVERY_CACHE)
    if cached is not None:
        return cached

    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(discovery_url)
        resp.raise_for_status()
        cfg = resp.json()
    except Exception as e:
        if _oidc_debug_enabled():
            logger.warning(
                "GitHub OIDC discovery fetch failed: %s",
                type(e).__name__,
            )
        raise OIDCJWKSFetchError("Failed to fetch GitHub OIDC discovery document") from e

    _set_cached(discovery_url, cfg, _DISCOVERY_CACHE)
    return cfg


def _get_jwks(jwks_uri: str) -> Dict[str, Any]:
    """
    Fetch JWKS for a given URI, with 10 minute cache.
    """
    cached = _get_cached(jwks_uri, _JWKS_CACHE)
    if cached is not None:
        return cached

    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(jwks_uri)
        resp.raise_for_status()
        jwks = resp.json()
    except Exception as e:
        if _oidc_debug_enabled():
            logger.warning(
                "JWKS fetch failed: %s",
                type(e).__name__,
            )
        raise OIDCJWKSFetchError("Failed to fetch JWKS document") from e

    _set_cached(jwks_uri, jwks, _JWKS_CACHE)
    return jwks


def verify_github_oidc_token(oidc_token: str) -> Dict[str, Any]:
    """
    Verify GitHub Actions OIDC JWT and return its payload.

    - Uses issuer https://token.actions.githubusercontent.com
    - Discovers JWKS via OIDC discovery and caches for 10 minutes
    - Verifies signature using key selected by header.kid
    - Verifies issuer and exp/nbf
    - Verifies that audience contains "thandev" (supports string or list)
    """
    issuer = GITHUB_CONFIG.issuer
    kid: Optional[str] = None
    jwks_uri: Optional[str] = None

    try:
        header = jwt.get_unverified_header(oidc_token)
        kid = header.get("kid")
        if not kid:
            raise ValueError("OIDC token missing 'kid' header")

        discovery = _get_github_openid_configuration()
        jwks_uri = discovery.get("jwks_uri")
        if not isinstance(jwks_uri, str) or not jwks_uri:
            raise OIDCJWKSFetchError("GitHub discovery missing 'jwks_uri'")

        jwks = _get_jwks(jwks_uri)
        keys = jwks.get("keys") or []
        signing_key: Optional[Dict[str, Any]] = None
        for k in keys:
            if isinstance(k, dict) and k.get("kid") == kid:
                signing_key = k
                break
        if not signing_key:
            raise ValueError("No matching JWK for token 'kid'")

        public_key = algorithms.RSAAlgorithm.from_jwk(json.dumps(signing_key))

        # Let PyJWT verify signature, issuer, exp and nbf; we validate aud manually.
        payload = jwt.decode(
            oidc_token,
            public_key,
            algorithms=["RS256"],
            issuer=issuer,
            options={"verify_aud": False},
        )

        aud = payload.get("aud")
        if isinstance(aud, str):
            audiences = [aud]
        elif isinstance(aud, (list, tuple)):
            audiences = list(aud)
        else:
            raise ValueError("OIDC token 'aud' claim must be string or list")

        if "thandev" not in audiences:
            raise ValueError("OIDC token audience must contain 'thandev'")

        return payload
    except OIDCJWKSFetchError:
        # Bubble up so caller can map to 503.
        if _oidc_debug_enabled():
            logger.warning(
                "GitHub OIDC verification failed due to JWKS/discovery issue",
                extra={
                    "issuer": issuer,
                    "kid": kid,
                    "jwks_uri": jwks_uri,
                },
            )
        raise
    except Exception as e:
        if _oidc_debug_enabled():
            try:
                aud_debug = None
                try:
                    # Best-effort payload decode without verification for logging aud only.
                    unverified_payload = jwt.decode(
                        oidc_token,
                        options={"verify_signature": False},
                    )
                    aud_debug = unverified_payload.get("aud")
                except Exception:
                    aud_debug = None

                logger.warning(
                    "GitHub OIDC verification failed",
                    extra={
                        "issuer": issuer,
                        "kid": kid,
                        "jwks_uri": jwks_uri,
                        "aud": aud_debug,
                        "exc_type": type(e).__name__,
                    },
                )
            except Exception:
                # Never let debug logging break verification path.
                logger.warning("GitHub OIDC debug logging failed")
        # Map all other failures to a ValueError so API can return 401.
        raise ValueError(str(e) or "Invalid GitHub OIDC token") from e


def get_provider_config(provider: str) -> Optional[OIDCProviderConfig]:
    """Return config for provider slug (lowercase), or None if unsupported."""
    return PROVIDER_CONFIGS.get(provider.lower().strip())


def verify_oidc_token_and_extract(
    provider: str,
    oidc_token: str,
) -> Dict[str, Any]:
    """
    Verify OIDC JWT and return extracted claims (repo_full_name, ref, sha, etc.).

    - For GitHub: uses dynamic OIDC discovery + JWKS with caching.
    - For other providers: falls back to static jwks_url (if configured).
    - Raises ValueError if token invalid or provider not implemented in prod.
    - For non-implemented providers, raises with message suitable for 501 response.
    """
    provider_slug = provider.lower().strip()
    config = get_provider_config(provider_slug)
    if not config:
        raise ValueError(f"Unsupported OIDC provider: {provider}")

    if not config.implemented:
        raise NotImplementedError(
            f"OIDC provider '{provider_slug}' not enabled yet. "
            "Enable by implementing claim extraction + issuer/JWKS validation."
        )

    # GitHub uses dynamic discovery + JWKS with caching.
    if provider_slug == "github":
        payload = verify_github_oidc_token(oidc_token)
        return config.claim_extractor(dict(payload))

    # Other providers (stubs) are not implemented yet unless jwks_url is configured.
    if not config.jwks_url:
        raise NotImplementedError(
            f"OIDC provider '{provider_slug}' has no JWKS URL configured yet."
        )

    try:
        jwks_uri = config.jwks_url
        jwks = _get_jwks(jwks_uri)
        keys = jwks.get("keys") or []
        signing_key_dict: Optional[Dict[str, Any]] = None

        header = jwt.get_unverified_header(oidc_token)
        kid = header.get("kid")
        for k in keys:
            if isinstance(k, dict) and (kid is None or k.get("kid") == kid):
                signing_key_dict = k
                break
        if not signing_key_dict:
            raise ValueError("No matching JWK for token")

        public_key = algorithms.RSAAlgorithm.from_jwk(json.dumps(signing_key_dict))

        payload = jwt.decode(
            oidc_token,
            public_key,
            algorithms=["RS256"],
            audience=config.expected_audience,
            issuer=config.issuer,
        )
    except OIDCJWKSFetchError as e:
        raise ValueError(f"OIDC JWKS unavailable: {e}") from e
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
