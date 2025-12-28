"""
Domain verification service: token management, DNS checks, enforcement helpers.
"""
import uuid
import datetime
from typing import Optional, Tuple

import dns.resolver

from app.core.domain_utils import registrable_domain_from_url, registrable_domain_from_host
from app.models.domain_verification import DomainVerification, DomainVerificationStatus
from app.models.allowed_domain import AllowedDomain
import sqlalchemy as sa
from app.models.project import Project
from app.core.config import settings
from fastapi import HTTPException, status


def _now_utc() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def generate_token() -> str:
    return uuid.uuid4().hex


def build_record_name(domain: str) -> str:
    return f"_thandev.{domain}"


def normalize_domain_from_url(url: str) -> Optional[str]:
    return registrable_domain_from_url(url)


def normalize_domain_from_host(host: str) -> Optional[str]:
    return registrable_domain_from_host(host)


def get_or_create_verification(db, project: Project, domain: str) -> DomainVerification:
    import logging
    logger = logging.getLogger(__name__)
    
    dv = (
        db.query(DomainVerification)
        .filter(DomainVerification.project_id == project.id, DomainVerification.domain == domain)
        .order_by(DomainVerification.created_at.desc())
        .first()
    )
    if dv:
        logger.info(f"Found existing verification for {domain}: id={dv.id}, status={dv.status}")
        return dv
    
    # Create new verification with lowercase status
    # CRITICAL: Use .value to get lowercase string, and ensure it's actually lowercase
    status_value = DomainVerificationStatus.PENDING.value  # This is "pending" (lowercase)
    # Double-check it's lowercase (defensive programming)
    if status_value != status_value.lower():
        logger.error(f"ERROR: status_value is not lowercase! Got: '{status_value}'")
        status_value = status_value.lower()
    
    token = generate_token()
    
    logger.info(f"Creating new verification for {domain}: status='{status_value}' (type: {type(status_value)}), token={token[:10]}...")
    
    # Create the object - TypeDecorator should convert this to lowercase
    dv = DomainVerification(
        project_id=project.id,
        tenant_id=project.tenant_id,
        domain=domain,
        status=status_value,  # This should be "pending" (lowercase string)
        token=token,
    )
    
    # Log what we're about to insert
    logger.info(f"DomainVerification object created: status attribute = '{dv.status}' (type: {type(dv.status)})")
    db.add(dv)
    try:
        db.commit()
        db.refresh(dv)
        logger.info(f"Successfully created verification: id={dv.id}, status={dv.status}")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to commit verification: {e}", exc_info=True)
        raise
    return dv


def rotate_token(db, dv: DomainVerification) -> DomainVerification:
    dv.token = generate_token()
    dv.status = DomainVerificationStatus.PENDING.value  # Use .value for lowercase string
    dv.verified_at = None
    dv.last_checked_at = None
    dv.last_error = None
    db.commit()
    db.refresh(dv)
    return dv


def mark_expired_if_needed(db, dv: DomainVerification) -> DomainVerification:
    if dv.expires_at and dv.expires_at < _now_utc():
        dv.status = DomainVerificationStatus.EXPIRED.value  # Use .value for lowercase string
        db.commit()
        db.refresh(dv)
    return dv


def verify_dns_token(db, dv: DomainVerification, timeout: int = 5, tries: int = 2) -> DomainVerification:
    dv = mark_expired_if_needed(db, dv)
    # Compare against value since DB stores string
    if dv.status == DomainVerificationStatus.EXPIRED.value or dv.status == DomainVerificationStatus.EXPIRED:
        return dv

    record_name = build_record_name(dv.domain)
    resolver = dns.resolver.Resolver()
    resolver.lifetime = timeout
    resolver.timeout = timeout

    matched = False
    last_error = None
    for _ in range(tries):
        try:
            answers = resolver.resolve(record_name, "TXT")
            for rdata in answers:
                for txt_string in rdata.strings:
                    try:
                        candidate = txt_string.decode("utf-8")
                    except Exception:
                        candidate = str(txt_string)
                    if candidate.strip() == dv.token:
                        matched = True
                        break
                if matched:
                    break
            if matched:
                break
        except Exception as e:
            last_error = str(e)
            continue

    dv.last_checked_at = _now_utc()
    if matched:
        dv.status = DomainVerificationStatus.VERIFIED.value  # Use .value for lowercase string
        dv.verified_at = dv.last_checked_at
        dv.last_error = None
    else:
        # Keep status as PENDING if not matched (don't set to FAILED immediately)
        # User can retry by checking again
        dv.last_error = last_error or "TXT record not found or token mismatch"

    db.commit()
    db.refresh(dv)
    return dv


def ensure_project_root_domain(project: Project, target_url: str, allow_admin_override: bool = False, is_admin: bool = False) -> Tuple[str, bool]:
    """
    Ensure project.root_domain is set and locked.
    Returns (root_domain, was_set_now).
    If root_domain exists and does not match new domain, raise unless admin override allowed and is_admin.
    """
    registrable = normalize_domain_from_url(target_url)
    if not registrable:
        raise ValueError("Unable to determine registrable domain from target_url")

    if not project.root_domain:
        project.root_domain = registrable
        return registrable, True

    if project.root_domain != registrable:
        if allow_admin_override and is_admin:
            project.root_domain = registrable
            return registrable, True
        raise PermissionError("Project root_domain is locked and does not match target_url")

    return registrable, False


def enforce_domain_verification_for_scan(
    db,
    project: Project,
    target_url: str,
    is_admin: bool = False,
    user_id: str | None = None,
):
    """
    Enforce:
    - registrable_domain(target_url) matches project.root_domain
    - domain is verified unless disabled/allowlisted
    """
    registrable = normalize_domain_from_url(target_url)
    if not registrable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid target_url: unable to determine registrable domain",
        )

    # Admin bypass: admins can scan any domain without DV
    if is_admin:
        return

    # Bypass flags
    if settings.DOMAIN_VERIFICATION_DISABLED:
        return
    raw_allowlist = getattr(settings, "ALLOWED_SCAN_DOMAINS", "") or ""
    allowlist = [d.strip().lower() for d in raw_allowlist.split(",") if d.strip()]
    if registrable in allowlist or (project.root_domain and project.root_domain.lower() in allowlist):
        return
    # DB allowlist (enabled, global or tenant-scoped)
    allowed = (
        db.query(AllowedDomain)
        .filter(
            AllowedDomain.enabled == True,  # noqa: E712
            AllowedDomain.domain == registrable,
            sa.or_(AllowedDomain.scope == "global", AllowedDomain.tenant_id == project.tenant_id),
        )
        .first()
    )
    if allowed:
        return

    # Domain lock check (after allowlist bypass)
    if project.root_domain and project.root_domain != registrable and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="DOMAIN_NOT_ALLOWED: target_url must match project root_domain.",
        )

    # Require verification
    dv = (
        db.query(DomainVerification)
        .filter(DomainVerification.project_id == project.id, DomainVerification.domain == registrable)
        .order_by(DomainVerification.created_at.desc())
        .first()
    )
    # Compare against value since DB stores string
    if not dv or (dv.status != DomainVerificationStatus.VERIFIED.value and dv.status != DomainVerificationStatus.VERIFIED):
        # Return structured error response
        error_detail = {
            "code": "DOMAIN_NOT_VERIFIED",
            "root_domain": registrable,
            "message": "Verify domain ownership before scanning.",
        }
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_detail,
        )

