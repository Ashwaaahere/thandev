"""
Domain utilities for registrable-domain extraction and validation.
"""
from typing import Optional
from urllib.parse import urlparse

from publicsuffix2 import get_sld


def extract_hostname(url: str) -> Optional[str]:
    """Return lowercase hostname from a URL string."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        return host.lower() if host else None
    except Exception:
        return None


def registrable_domain_from_url(url: str) -> Optional[str]:
    """
    Reduce a URL to its registrable domain (eTLD+1) using PSL.
    Example: a.b.example.co.uk -> example.co.uk
    """
    host = extract_hostname(url)
    if not host:
        return None
    return registrable_domain_from_host(host)


def registrable_domain_from_host(host: str) -> Optional[str]:
    """Reduce hostname to registrable domain (eTLD+1)."""
    if not host:
        return None
    try:
        host_l = host.lower()
        rd = get_sld(host_l)
        if rd and rd == host_l.split(".")[-1]:
            rd = host_l  # fallback for public-suffix-only like demo.test
        return rd or host_l
    except Exception:
        return host.lower()

