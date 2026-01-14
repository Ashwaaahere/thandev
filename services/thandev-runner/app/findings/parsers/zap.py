"""
ZAP output parser - Simplified
ZAP output is already in the correct findings format, so we just load the JSON array
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def parse_zap_output(path: Path) -> List[Dict[str, Any]]:
    """
    Parse ZAP JSON output file into normalized findings.
    
    ZAP output is already in findings format - just load the JSON array.
    
    Args:
        path: Path to the ZAP JSON output file
        
    Returns:
        List of normalized finding dicts (empty list if file is empty/missing/invalid)
    """
    # #region agent log
    try:
        with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
            import json as json_lib
            import time
            f.write(json_lib.dumps({"sessionId":"zap-debug","runId":"run1","hypothesisId":"H4","location":"zap.py:13","message":"parse_zap_output entry","data":{"path":str(path),"path_exists":path.exists() if path else False},"timestamp":int(time.time()*1000)})+"\n")
    except: pass
    # #endregion
    # Check if file exists
    if not path or not path.exists():
        logger.warning(f"ZAP output file does not exist: {path}")
        # #region agent log
        try:
            with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
                import json as json_lib
                import time
                f.write(json_lib.dumps({"sessionId":"zap-debug","runId":"run1","hypothesisId":"H4","location":"zap.py:28","message":"parse_zap_output early return - file not exists","data":{"path":str(path)},"timestamp":int(time.time()*1000)})+"\n")
        except: pass
        # #endregion
        return []
    
    # Check file size
    try:
        file_size = path.stat().st_size
        if file_size == 0:
            logger.warning(f"ZAP output file is empty: {path}")
            return []
    except Exception as e:
        logger.error(f"Failed to check ZAP file size: {e}")
        return []
    
    # Read and parse file
    try:
        content = path.read_text(encoding="utf-8", errors="ignore").strip()
        
        if not content:
            logger.warning(f"ZAP output file has no content: {path}")
            return []
        
        # Parse JSON - ZAP output is a JSON array
        # #region agent log
        try:
            with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
                import json as json_lib
                import time
                f.write(json_lib.dumps({"sessionId":"zap-debug","runId":"run1","hypothesisId":"H4","location":"zap.py:49","message":"Before JSON parse","data":{"path":str(path),"content_length":len(content),"content_preview":content[:100]},"timestamp":int(time.time()*1000)})+"\n")
        except: pass
        # #endregion
        data = json.loads(content)
        
        # Must be a list
        if not isinstance(data, list):
            logger.error(f"ZAP output is not a JSON array (got {type(data)}): {path}")
            # #region agent log
            try:
                with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
                    import json as json_lib
                    import time
                    f.write(json_lib.dumps({"sessionId":"zap-debug","runId":"run1","hypothesisId":"H4","location":"zap.py:53","message":"Not a list - early return","data":{"path":str(path),"data_type":str(type(data))},"timestamp":int(time.time()*1000)})+"\n")
            except: pass
            # #endregion
            return []
        
        # If empty array, return empty list
        if len(data) == 0:
            logger.info(f"ZAP output is empty array (no findings): {path}")
            # #region agent log
            try:
                with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
                    import json as json_lib
                    import time
                    f.write(json_lib.dumps({"sessionId":"zap-debug","runId":"run1","hypothesisId":"H4","location":"zap.py:58","message":"Empty array - early return","data":{"path":str(path)},"timestamp":int(time.time()*1000)})+"\n")
            except: pass
            # #endregion
            return []
        
        # Process findings - extract unique identifiers to prevent over-deduplication
        findings = []
        for idx, finding in enumerate(data):
            if not isinstance(finding, dict):
                logger.warning(f"Skipping invalid finding at index {idx} (not a dict): {type(finding)}")
                continue
            
            # Extract detailed fields from raw ZAP alert JSON if available
            raw_data = finding.get("raw", "{}")
            zap_alert = {}
            if isinstance(raw_data, str):
                try:
                    zap_alert = json.loads(raw_data)
                except:
                    pass
            elif isinstance(raw_data, dict):
                zap_alert = raw_data
            
            # Extract unique identifiers to prevent over-deduplication:
            # - alertRef: Unique per finding instance (e.g., "10096")
            # - pluginId: ZAP rule ID
            # - param: Specific parameter where issue was found
            # These make each finding instance unique even if same vuln type
            alert_ref = zap_alert.get("alertRef", "")
            plugin_id = zap_alert.get("pluginId", "")
            param = zap_alert.get("param", "")
            evidence_detail = zap_alert.get("evidence", "")
            
            # Use alertRef as rule_id (unique per instance), fall back to pluginId
            rule_id = alert_ref or plugin_id or None
            
            # ZAP already provides the correct format, just ensure required fields
            normalized = {
                "tool_id": finding.get("tool_id", "zap"),
                "tool": "zap",  # Canonical tool name
                "title": finding.get("title") or finding.get("alert") or "Unknown ZAP Finding",
                "severity": finding.get("severity", "info"),
                "description": finding.get("description", ""),
                "evidence": finding.get("evidence") or finding.get("solution", ""),
                "url": finding.get("url", ""),
                "host": finding.get("host", ""),
                "port": finding.get("port"),
                "timestamp": finding.get("timestamp", ""),
                "raw": finding.get("raw") or json.dumps(finding),
                # Add unique identifiers for proper deduplication
                "rule_id": rule_id,  # Unique per finding instance
                "parameter": param if param else None,  # Specific parameter affected
            }
            
            # If we have detailed evidence, append it to help distinguish findings
            if evidence_detail and evidence_detail != normalized["evidence"]:
                normalized["evidence"] += f" (Evidence: {evidence_detail[:100]})"
            
            findings.append(normalized)
        
        logger.info(f"Successfully parsed {len(findings)} findings from ZAP output: {path}")
        # #region agent log
        try:
            with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
                import json as json_lib
                import time
                f.write(json_lib.dumps({"sessionId":"zap-debug","runId":"run1","hypothesisId":"H4","location":"zap.py:84","message":"parse_zap_output exit","data":{"path":str(path),"findings_count":len(findings),"first_title":findings[0].get("title","N/A")[:50] if len(findings)>0 else None},"timestamp":int(time.time()*1000)})+"\n")
        except: pass
        # #endregion
        return findings
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse ZAP JSON from {path}: {e}. Content preview: {content[:200] if 'content' in locals() else 'N/A'}")
        # #region agent log
        try:
            with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
                import json as json_lib
                import time
                f.write(json_lib.dumps({"sessionId":"zap-debug","runId":"run1","hypothesisId":"H4","location":"zap.py:87","message":"JSON decode error","data":{"path":str(path),"error":str(e),"content_preview":content[:200] if 'content' in locals() else 'N/A'},"timestamp":int(time.time()*1000)})+"\n")
        except: pass
        # #endregion
        return []
    except Exception as e:
        logger.error(f"Error parsing ZAP output from {path}: {e}", exc_info=True)
        # #region agent log
        try:
            with open("/home/ashwath/thandev/.cursor/debug.log", "a") as f:
                import json as json_lib
                import time
                f.write(json_lib.dumps({"sessionId":"zap-debug","runId":"run1","hypothesisId":"H4","location":"zap.py:91","message":"General exception in parser","data":{"path":str(path),"error":str(e)},"timestamp":int(time.time()*1000)})+"\n")
        except: pass
        # #endregion
        return []
