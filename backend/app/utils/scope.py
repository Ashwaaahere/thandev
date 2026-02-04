"""
Scope enforcement utilities for filtering in-scope vs out-of-scope URLs.

This module provides functions to determine if a discovered URL/asset
is within the authorized scan scope.
"""
import logging
from typing import List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def normalize_host(url: str) -> str:
    """
    Extract and normalize hostname from URL.
    
    Args:
        url: URL string
        
    Returns:
        Normalized hostname (lowercase, no port) or empty string
    """
    if not url:
        return ""
    
    try:
        parsed = urlparse(url)
        host = parsed.netloc or parsed.hostname
        if not host:
            return ""
        
        # Remove port
        if ':' in host:
            host = host.split(':')[0]
        
        return host.lower()
    except Exception as e:
        logger.debug(f"Failed to normalize host from URL '{url}': {e}")
        return ""


def is_in_scope(
    url: str,
    scan_target_host: str,
    allowed_domains: Optional[List[str]] = None,
) -> bool:
    """
    Determine if a URL is within the authorized scan scope.
    
    A URL is in-scope if:
    - Its hostname matches the scan target host exactly
    - Its hostname is a subdomain of the scan target host (e.g., sub.example.com for example.com)
    - Its hostname is in the allowed_domains list (verified tenant domains)
    
    Args:
        url: URL to check
        scan_target_host: Target hostname from scan configuration (e.g., "example.com")
        allowed_domains: Optional list of additional allowed domains (e.g., verified tenant domains)
        
    Returns:
        True if URL is in-scope, False otherwise
    """
    if not url or not scan_target_host:
        return False
    
    url_host = normalize_host(url)
    target_host = normalize_host(scan_target_host)
    
    if not url_host or not target_host:
        return False
    
    # Exact match
    if url_host == target_host:
        return True
    
    # Subdomain match (e.g., sub.example.com for example.com)
    if url_host.endswith('.' + target_host):
        return True
    
    # Check allowed domains
    if allowed_domains:
        for allowed in allowed_domains:
            allowed_normalized = normalize_host(allowed)
            if url_host == allowed_normalized or url_host.endswith('.' + allowed_normalized):
                return True
    
    return False


