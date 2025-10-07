from sqlalchemy import Column, Text, DateTime, Boolean, Numeric, ARRAY, JSON, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from .db import Base

class ThreatItem(Base):
    __tablename__ = "threat_item"
    id = Column(UUID(as_uuid=True), primary_key=True)
    source = Column(Text, nullable=False)
    source_id = Column(Text)
    title = Column(Text, nullable=False)
    summary = Column(Text)
    published_at = Column(DateTime(timezone=True))
    discovered_at = Column(DateTime(timezone=True))
    url = Column(Text)
    cve_id = Column(Text)
    cwe_id = Column(Text)
    vendor = Column(Text)
    product = Column(Text)
    version_range = Column(Text)
    cvss_v2 = Column(Numeric)
    cvss_v3 = Column(Numeric)
    epss_score = Column(Numeric)
    is_kev = Column(Boolean, default=False)
    has_exploit = Column(Boolean, default=False)
    tags = Column(ARRAY(Text))
    raw = Column(JSON)

class ScanJob(Base):
    __tablename__ = "scan_jobs"
    id = Column(UUID(as_uuid=True), primary_key=True)
    user_id = Column(Text, nullable=False)
    url = Column(Text, nullable=False)
    domain = Column(Text)
    tier = Column(String(10), nullable=False)  # level0, level1, level2
    status = Column(String(20), default='pending')  # pending, running, completed, error
    created_at = Column(DateTime(timezone=True), nullable=False)
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    artifact_urls = Column(JSON)  # Array of artifact URLs
    summary = Column(JSON)  # Scan summary with vuln counts, tech stack, etc.
    preset_version = Column(String(20), default='1.0')
    execution_id = Column(Text)  # Cloud Run execution ID
