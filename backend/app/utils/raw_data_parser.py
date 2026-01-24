"""
Robust raw data parser utility for extracting structured data from finding raw_data.

Handles:
- Dict input (return as-is)
- JSON string (single-encoded)
- Double-encoded JSON string (JSON string containing another JSON string)
- Invalid data (returns empty dict with logging)
"""
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def parse_raw_json(raw: Any) -> Dict[str, Any]:
    """
    Robustly parse raw data from various formats.
    
    Args:
        raw: Raw data in any format (dict, str, None, etc.)
        
    Returns:
        Dict with parsed data, or empty dict if parsing fails
    """
    if raw is None:
        return {}
    
    # If already a dict, return as-is
    if isinstance(raw, dict):
        return raw
    
    # If it's a string, try to parse it
    if isinstance(raw, str):
        # Try parsing as JSON
        try:
            parsed = json.loads(raw)
            
            # If result is still a string, it might be double-encoded
            if isinstance(parsed, str):
                try:
                    # Try parsing again (double-encoded case)
                    parsed = json.loads(parsed)
                    logger.debug(f"[RAW-PARSER] Detected double-encoded JSON, parsed successfully")
                except (json.JSONDecodeError, TypeError):
                    # Not valid JSON, return as string value
                    logger.warning(f"[RAW-PARSER] Double-encoded string is not valid JSON, returning as string")
                    return {"_raw_string": parsed}
            
            # Ensure we have a dict
            if isinstance(parsed, dict):
                return parsed
            else:
                logger.warning(f"[RAW-PARSER] Parsed JSON is not a dict (type={type(parsed).__name__}), returning empty dict")
                return {}
                
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"[RAW-PARSER] Failed to parse JSON string: {e}, returning empty dict")
            return {}
    
    # Unknown type, return empty dict
    logger.warning(f"[RAW-PARSER] Unknown raw data type: {type(raw).__name__}, returning empty dict")
    return {}


def extract_zap_metadata(raw: Any) -> Dict[str, Any]:
    """
    Extract ZAP-specific metadata from raw data.
    
    Args:
        raw: Raw data in any format
        
    Returns:
        Dict with:
        - riskcode: int (0-4) or None
        - confidence: int (0-3) or None
        - alert: str or None
        - cweid: str/int or None
        - wascid: int or None
        - pluginId: str or None
        - alertRef: str or None
    """
    raw_dict = parse_raw_json(raw)
    
    # Extract riskcode (normalize to int)
    riskcode = None
    riskcode_raw = raw_dict.get("riskcode")
    if riskcode_raw is not None:
        try:
            if isinstance(riskcode_raw, str):
                riskcode = int(riskcode_raw) if riskcode_raw.isdigit() else 0
            elif isinstance(riskcode_raw, (int, float)):
                riskcode = int(riskcode_raw)
            else:
                riskcode = 0
        except (ValueError, TypeError):
            riskcode = 0
    
    # Extract confidence (normalize to int)
    confidence = None
    confidence_raw = raw_dict.get("confidence")
    if confidence_raw is not None:
        try:
            if isinstance(confidence_raw, str):
                conf_lower = confidence_raw.lower()
                if conf_lower in ["low", "0"]:
                    confidence = 0
                elif conf_lower in ["medium", "1"]:
                    confidence = 1
                elif conf_lower in ["high", "2"]:
                    confidence = 2
                elif conf_lower in ["confirmed", "3", "true"]:
                    confidence = 3
                else:
                    # Try to parse as int
                    confidence = int(confidence_raw) if confidence_raw.isdigit() else 0
            elif isinstance(confidence_raw, (int, float)):
                confidence = int(confidence_raw)
            else:
                confidence = 0
        except (ValueError, TypeError):
            confidence = 0
    
    # Extract other metadata
    alert = raw_dict.get("alert") or raw_dict.get("alertName")
    cweid = raw_dict.get("cweid") or raw_dict.get("cweId")
    wascid_raw = raw_dict.get("wascid") or raw_dict.get("wascId")
    wascid = None
    if wascid_raw is not None:
        try:
            wascid = int(wascid_raw) if isinstance(wascid_raw, (int, float)) or (isinstance(wascid_raw, str) and wascid_raw.isdigit()) else None
        except (ValueError, TypeError):
            pass
    
    plugin_id = raw_dict.get("pluginId") or raw_dict.get("plugin_id")
    alert_ref = raw_dict.get("alertRef") or raw_dict.get("alert_ref")
    
    return {
        "riskcode": riskcode if riskcode is not None else 0,  # Default to 0 (INFO)
        "confidence": confidence if confidence is not None else 0,  # Default to 0 (Low)
        "alert": alert,
        "cweid": cweid,
        "wascid": wascid,
        "pluginId": plugin_id,
        "alertRef": alert_ref,
        "raw_dict": raw_dict,  # Include full dict for additional processing
    }


def normalize_cwe_id(cwe_id: Any) -> Optional[str]:
    """
    Normalize CWE ID to "CWE-<number>" string.
    Returns None if input is empty/invalid.
    """
    if cwe_id is None:
        return None
    if isinstance(cwe_id, (int, float)):
        return f"CWE-{int(cwe_id)}"
    if isinstance(cwe_id, str):
        cwe_str = cwe_id.strip()
        if not cwe_str:
            return None
        if cwe_str.upper().startswith("CWE-"):
            return cwe_str
        try:
            cwe_num = int(cwe_str)
            return f"CWE-{cwe_num}"
        except (ValueError, TypeError):
            return cwe_str
    return None

