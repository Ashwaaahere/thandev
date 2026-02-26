"""
Helpers for storing and reading DALFOX per-instance metadata in evidence_snippet.

Phase 1 keeps schema unchanged by using a tagged JSON envelope appended to a
human-readable snippet:

    <display text>
    __DALFOX_META__:{...json...}
"""
from __future__ import annotations

import json
from typing import Any, Dict


DALFOX_META_TAG = "__DALFOX_META__:"


def build_dalfox_evidence_snippet(display_snippet: str, meta: Dict[str, Any]) -> str:
    """
    Build a combined snippet with plain-text first, plus machine envelope.
    """
    safe_display = (display_snippet or "").strip()
    envelope = json.dumps(meta or {}, ensure_ascii=True, separators=(",", ":"))
    if safe_display:
        return f"{safe_display}\n{DALFOX_META_TAG}{envelope}"
    return f"{DALFOX_META_TAG}{envelope}"


def parse_dalfox_evidence_snippet(evidence_snippet: Any) -> Dict[str, Any]:
    """
    Parse DALFOX metadata from evidence_snippet.

    Returns:
      {
        "display_snippet": "<human text>",
        "payload_raw": ...,
        "payload_decoded": ...,
        "message": ...,
        "marker": ...,
        "instance_severity": ...,
      }
    """
    raw = "" if evidence_snippet is None else str(evidence_snippet)
    out: Dict[str, Any] = {
        "display_snippet": raw,
        "payload_raw": None,
        "payload_decoded": None,
        "message": None,
        "marker": None,
        "instance_severity": None,
    }
    if DALFOX_META_TAG not in raw:
        return out

    head, _, tail = raw.partition(DALFOX_META_TAG)
    out["display_snippet"] = head.rstrip()
    tail = tail.strip()
    if not tail:
        return out

    try:
        data = json.loads(tail)
    except Exception:
        return out

    if not isinstance(data, dict):
        return out

    out["payload_raw"] = data.get("payload_raw")
    out["payload_decoded"] = data.get("payload_decoded")
    out["message"] = data.get("message")
    out["marker"] = data.get("marker")
    out["instance_severity"] = data.get("instance_severity")
    return out

