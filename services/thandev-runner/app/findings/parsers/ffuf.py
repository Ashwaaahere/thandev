"""
ffuf output parser
Parses ffuf JSON output into normalized findings (content discovery)
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def parse_ffuf_output(path: Path, max_findings: int = 200) -> List[Dict[str, Any]]:
    """
    Parse ffuf JSON output into normalized findings.

    ffuf is a content discovery tool; we represent discovered endpoints as INFO findings so
    they appear in the UI and can be used by other workflows.
    """
    if not path.exists() or path.stat().st_size == 0:
        logger.info("ffuf output file is empty or missing for %s; treating as no findings", path)
        return []

    try:
        raw = path.read_text(encoding="utf-8", errors="ignore").strip()
        if not raw:
            return []

        # ffuf -of json produces a single JSON object
        data = json.loads(raw)
        if not isinstance(data, dict):
            return []

        results = data.get("results") or []
        if not isinstance(results, list):
            return []

        findings: List[Dict[str, Any]] = []
        for r in results[:max_findings]:
            if not isinstance(r, dict):
                continue
            url = r.get("url") or ""
            status = r.get("status")
            length = r.get("length")

            title = "Discovered content"
            if status is not None:
                title = f"Discovered content (HTTP {status})"

            evidence_parts = []
            if url:
                evidence_parts.append(f"url={url}")
            if status is not None:
                evidence_parts.append(f"status={status}")
            if length is not None:
                evidence_parts.append(f"length={length}")

            findings.append(
                {
                    "tool_id": "ffuf",
                    "title": title,
                    "severity": "info",
                    "description": "Endpoint discovered via content discovery (ffuf). Review for hidden panels, backups, or exposed resources.",
                    "evidence": ", ".join(evidence_parts) if evidence_parts else "ffuf discovery result",
                    "url": url,
                    "raw": r,
                }
            )

        return findings
    except Exception as e:
        logger.warning("Failed to parse ffuf output %s: %s", path, e)
        return []



