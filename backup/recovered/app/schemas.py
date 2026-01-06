from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from uuid import UUID
from datetime import datetime

class ThreatItemRef(BaseModel):
    id: UUID
    ref_type: Optional[str]
    ref_url: str

class ThreatItemOut(BaseModel):
    id: UUID
    source: str
    source_id: Optional[str]
    title: str
    summary: Optional[str]
    published_at: Optional[datetime]
    url: Optional[str]
    cve_id: Optional[str]
    cvss_v3: Optional[float]
    epss_score: Optional[float]
    is_kev: bool
    has_exploit: bool
    tags: Optional[List[str]] = []

    model_config = ConfigDict(from_attributes=True)
