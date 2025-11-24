#!/usr/bin/env python3
"""
Result Processing Utilities for Security Scanner
Handles deduplication, false positive filtering, prioritization, and caching
"""

import hashlib
import json
import logging
from typing import List, Dict, Any, Set
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class ResultProcessor:
    """Process scan results with deduplication, filtering, and prioritization"""
    
    def __init__(self):
        # Known false positive patterns
        self.false_positive_patterns = [
            "informational",
            "info",
            "debug",
            "test",
            "example",
            "localhost",
            "127.0.0.1",
            "self-signed",
            "expired certificate",  # Common false positive
            "weak cipher",  # Often flagged but may be acceptable
        ]
        
        # Severity priority weights
        self.severity_weights = {
            "critical": 100,
            "high": 75,
            "medium": 50,
            "low": 25,
            "info": 10
        }
    
    def generate_vulnerability_hash(self, vuln: Dict[str, Any]) -> str:
        """Generate a unique hash for a vulnerability to detect duplicates"""
        # Create a normalized representation
        key_parts = [
            vuln.get("type", ""),
            vuln.get("title", ""),
            vuln.get("endpoint", ""),
            vuln.get("port", ""),
            vuln.get("parameter", ""),
        ]
        
        # Normalize and create hash
        normalized = "|".join(str(part).lower().strip() for part in key_parts if part)
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def deduplicate_vulnerabilities(self, vulnerabilities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate vulnerabilities based on hash"""
        seen_hashes: Set[str] = set()
        deduplicated = []
        
        for vuln in vulnerabilities:
            vuln_hash = self.generate_vulnerability_hash(vuln)
            
            if vuln_hash not in seen_hashes:
                seen_hashes.add(vuln_hash)
                deduplicated.append(vuln)
            else:
                logger.debug(f"Skipping duplicate vulnerability: {vuln.get('title', 'Unknown')}")
        
        logger.info(f"Deduplicated {len(vulnerabilities)} -> {len(deduplicated)} vulnerabilities")
        return deduplicated
    
    def is_false_positive(self, vuln: Dict[str, Any]) -> bool:
        """Check if a vulnerability is likely a false positive"""
        title = vuln.get("title", "").lower()
        description = vuln.get("description", "").lower()
        severity = vuln.get("severity", "").lower()
        
        # Check against false positive patterns
        combined_text = f"{title} {description}"
        
        for pattern in self.false_positive_patterns:
            if pattern in combined_text:
                # If it's info severity and matches pattern, likely false positive
                if severity == "info":
                    return True
                # For other severities, be more conservative
                if pattern in ["test", "example", "localhost"]:
                    return True
        
        # Additional heuristics
        # Very low CVSS scores might be false positives
        cvss = vuln.get("cvss", 0)
        if cvss < 2.0 and severity in ["low", "info"]:
            return True
        
        return False
    
    def filter_false_positives(self, vulnerabilities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter out likely false positives"""
        filtered = []
        
        for vuln in vulnerabilities:
            if not self.is_false_positive(vuln):
                filtered.append(vuln)
            else:
                logger.debug(f"Filtered false positive: {vuln.get('title', 'Unknown')}")
        
        logger.info(f"Filtered {len(vulnerabilities)} -> {len(filtered)} vulnerabilities (removed {len(vulnerabilities) - len(filtered)} false positives)")
        return filtered
    
    def prioritize_vulnerabilities(self, vulnerabilities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort vulnerabilities by priority (severity, CVSS, recency)"""
        def calculate_priority(vuln: Dict[str, Any]) -> float:
            severity = vuln.get("severity", "info").lower()
            cvss = vuln.get("cvss", 0)
            
            # Base priority from severity
            priority = self.severity_weights.get(severity, 10)
            
            # Boost priority based on CVSS score
            priority += cvss * 2
            
            # Additional boosts
            if vuln.get("type") in ["SQL Injection", "XSS", "Remote Code Execution"]:
                priority += 50
            
            if vuln.get("is_kev", False):  # Known Exploited Vulnerability
                priority += 100
            
            return priority
        
        # Sort by priority (highest first)
        prioritized = sorted(vulnerabilities, key=calculate_priority, reverse=True)
        
        # Add priority score to each vulnerability
        for i, vuln in enumerate(prioritized):
            vuln["priority_score"] = calculate_priority(vuln)
            vuln["priority_rank"] = i + 1
        
        logger.info(f"Prioritized {len(prioritized)} vulnerabilities")
        return prioritized
    
    def process_results(self, vulnerabilities: List[Dict[str, Any]], 
                       ports: List[Dict[str, Any]] = None,
                       ssl_issues: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Complete result processing pipeline"""
        logger.info(f"Processing {len(vulnerabilities)} raw vulnerabilities")
        
        # Step 1: Deduplicate
        deduplicated = self.deduplicate_vulnerabilities(vulnerabilities)
        
        # Step 2: Filter false positives
        filtered = self.filter_false_positives(deduplicated)
        
        # Step 3: Prioritize
        prioritized = self.prioritize_vulnerabilities(filtered)
        
        # Process other result types
        processed_ports = ports or []
        processed_ssl = ssl_issues or []
        
        return {
            "vulnerabilities": prioritized,
            "ports": processed_ports,
            "ssl_issues": processed_ssl,
            "statistics": {
                "total_raw": len(vulnerabilities),
                "after_deduplication": len(deduplicated),
                "after_filtering": len(filtered),
                "final_count": len(prioritized),
                "false_positives_removed": len(deduplicated) - len(filtered),
                "duplicates_removed": len(vulnerabilities) - len(deduplicated)
            }
        }


class ResultCache:
    """Simple in-memory cache for scan results (for Cloud Run Jobs, consider Redis)"""
    
    def __init__(self, ttl_hours: int = 24):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl_hours = ttl_hours
    
    def _generate_cache_key(self, url: str, tier: str) -> str:
        """Generate cache key from URL and tier"""
        key_data = f"{url}:{tier}".lower().strip()
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, url: str, tier: str) -> Dict[str, Any] | None:
        """Get cached results if available and not expired"""
        cache_key = self._generate_cache_key(url, tier)
        
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            cached_time = datetime.fromisoformat(cached_data["cached_at"])
            
            # Check if cache is still valid
            if datetime.utcnow() - cached_time < timedelta(hours=self.ttl_hours):
                logger.info(f"Cache hit for {url} (tier: {tier})")
                return cached_data["results"]
            else:
                # Expired, remove from cache
                del self.cache[cache_key]
                logger.debug(f"Cache expired for {url} (tier: {tier})")
        
        return None
    
    def set(self, url: str, tier: str, results: Dict[str, Any]):
        """Cache scan results"""
        cache_key = self._generate_cache_key(url, tier)
        
        self.cache[cache_key] = {
            "results": results,
            "cached_at": datetime.utcnow().isoformat(),
            "url": url,
            "tier": tier
        }
        
        logger.info(f"Cached results for {url} (tier: {tier})")
    
    def clear(self):
        """Clear all cached results"""
        self.cache.clear()
        logger.info("Cache cleared")
    
    def clear_expired(self):
        """Remove expired cache entries"""
        now = datetime.utcnow()
        expired_keys = []
        
        for key, data in self.cache.items():
            cached_time = datetime.fromisoformat(data["cached_at"])
            if now - cached_time >= timedelta(hours=self.ttl_hours):
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            logger.info(f"Cleared {len(expired_keys)} expired cache entries")


# Global instances
result_processor = ResultProcessor()
result_cache = ResultCache(ttl_hours=24)  # Cache for 24 hours


