from sqlalchemy import Column, Text, DateTime, Boolean, Numeric, ARRAY, JSON
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
