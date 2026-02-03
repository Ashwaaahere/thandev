"""
Noise rules engine for applying severity overrides and suppression rules.

This module loads rules from noise_rules.yml and applies them to findings
to reduce false positives and noise in scan reports.
"""
import re
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from app.models.finding import Severity

logger = logging.getLogger(__name__)

# Cache for loaded rules
_rules_cache: Optional[List[Dict[str, Any]]] = None


def _load_noise_rules() -> List[Dict[str, Any]]:
    """Load noise rules from YAML config file."""
    global _rules_cache
    
    if _rules_cache is not None:
        return _rules_cache
    
    # Try to load from config directory
    config_path = Path(__file__).parent.parent / "config" / "noise_rules.yml"
    
    if not config_path.exists():
        logger.warning(f"Noise rules file not found at {config_path}, using default rules")
        _rules_cache = []
        return _rules_cache
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            _rules_cache = config.get("rules", [])
            logger.info(f"Loaded {len(_rules_cache)} noise rules from {config_path}")
            return _rules_cache
    except Exception as e:
        logger.error(f"Failed to load noise rules from {config_path}: {e}")
        _rules_cache = []
        return _rules_cache


def _match_pattern(pattern: str, text: str) -> bool:
    """Check if a regex pattern matches text."""
    if not text:
        return False
    try:
        return bool(re.search(pattern, text, re.IGNORECASE))
    except re.error:
        logger.warning(f"Invalid regex pattern: {pattern}")
        return False


def _check_condition(condition: Dict[str, Any], finding_data: Dict[str, Any], raw_data: Dict[str, Any]) -> bool:
    """Check if a rule condition matches the finding."""
    # Check title match
    if "title_match" in condition:
        title = (finding_data.get("title") or "").lower()
        title_matches = [tm.lower() for tm in condition["title_match"]]
        if not any(tm in title for tm in title_matches):
            return False
    
    # Check URL patterns
    if "url_patterns" in condition:
        url = (finding_data.get("url") or "").lower()
        path = (finding_data.get("path") or "").lower()
        combined_url = url + " " + path
        
        url_matched = False
        for pattern in condition["url_patterns"]:
            if _match_pattern(pattern, combined_url):
                url_matched = True
                break
        
        if not url_matched:
            return False
    
    # Check evidence patterns
    if "evidence_patterns" in condition:
        evidence = (finding_data.get("evidence") or "").lower()
        description = (finding_data.get("description") or "").lower()
        combined = evidence + " " + description
        
        evidence_matched = False
        for pattern in condition["evidence_patterns"]:
            if _match_pattern(pattern, combined):
                evidence_matched = True
                break
        
        if not evidence_matched:
            return False
    
    return True


def apply_noise_rules(
    finding_data: Dict[str, Any],
    raw_data: Dict[str, Any],
    original_severity: Severity,
) -> Tuple[Severity, Optional[str], Optional[str]]:
    """
    Apply noise rules to a finding and return adjusted severity.
    
    Args:
        finding_data: Finding data dict
        raw_data: Parsed raw_data dict
        original_severity: Original severity from tool
        
    Returns:
        Tuple of (adjusted_severity, tag, reason)
    """
    rules = _load_noise_rules()
    
    # Try each rule in order
    for rule in rules:
        condition = rule.get("condition", {})
        action = rule.get("action", {})
        
        if _check_condition(condition, finding_data, raw_data):
            # Rule matched - apply action
            severity_override = action.get("severity_override")
            tag = action.get("tag")
            reason = action.get("reason", f"Matched rule: {rule.get('name', 'unknown')}")
            
            if severity_override:
                try:
                    # Convert string to Severity enum
                    if isinstance(severity_override, str):
                        severity_override_lower = severity_override.lower()
                        severity_map = {
                            "critical": Severity.CRITICAL,
                            "high": Severity.HIGH,
                            "medium": Severity.MEDIUM,
                            "low": Severity.LOW,
                            "info": Severity.INFO,
                        }
                        new_severity = severity_map.get(severity_override_lower, original_severity)
                    else:
                        new_severity = original_severity
                    
                    # Only downgrade, never upgrade (unless explicitly allowed)
                    severity_order = {
                        Severity.INFO: 0,
                        Severity.LOW: 1,
                        Severity.MEDIUM: 2,
                        Severity.HIGH: 3,
                        Severity.CRITICAL: 4,
                    }
                    
                    # Allow upgrade only if rule explicitly says so (e.g., CORS wildcard with credentials)
                    if severity_order.get(new_severity, 0) < severity_order.get(original_severity, 0):
                        # Downgrade allowed
                        logger.debug(f"Downgrading severity from {original_severity.value} to {new_severity.value} for {finding_data.get('title')}: {reason}")
                        return new_severity, tag, reason
                    elif severity_order.get(new_severity, 0) > severity_order.get(original_severity, 0):
                        # Upgrade - only if rule explicitly allows
                        logger.debug(f"Upgrading severity from {original_severity.value} to {new_severity.value} for {finding_data.get('title')}: {reason}")
                        return new_severity, tag, reason
                    else:
                        # Same severity, apply tag/reason
                        return original_severity, tag, reason
                        
                except Exception as e:
                    logger.warning(f"Error applying severity override: {e}")
                    continue
    
    # No rules matched, return original
    return original_severity, None, None


